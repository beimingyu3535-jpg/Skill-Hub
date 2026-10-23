"""Actionflow Skill 的命令行入口，只负责参数解析和命令分发。"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.build_workflow_draft import build_workflow_draft, normalize_semantic_plan
from core.component_registry import adapt_updates, get_component_contracts, search_component_catalog
from core.compile_workflow_draft import compile_workflow_draft
from core.context_provider import ContextStore, get_component_context
from core.context_data_builder import build_component_context_data
from core.draft_to_real import convert as convert_draft_to_real, map_draft_data
from core.generation_service import _run_generate, _run_generate_multi, normalize_generated_name
from core.preflight_service import (
    flatten_form_fields_response,
)
from core.platform_client import make_client
from core.sequential_workflow_builder import fill_node_context
from core.validate import validate_workflow_draft

def print_usage() -> None:
    print("Usage: python scripts/actionflow_skill.py <command> '<json>'")
    print("See SKILL.md for supported workflows and command examples.")

def load_json_arg(raw: str) -> dict[str, Any]:
    if raw.startswith("@"):
        return json.loads(Path(raw[1:]).read_text(encoding="utf-8"))
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("input JSON must be an object")
    return parsed

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 3:
        print_usage()
        return 1

    command = sys.argv[1]
    try:
        payload = load_json_arg(sys.argv[2])
        client = None

        if command == "component-search":
            query = payload.get("query")
            if not isinstance(query, str):
                raise ValueError("query must be a string")
            node_role = payload.get("nodeRole")
            if node_role is not None and not isinstance(node_role, str):
                raise ValueError("nodeRole must be a string when supplied")
            result = search_component_catalog(query, node_role=node_role, limit=int(payload.get("limit", 8)))
        elif command == "describe":
            single_type = payload.get("type")
            types = payload.get("types", [single_type] if isinstance(single_type, str) else [])
            if not isinstance(types, list) or not all(isinstance(item, str) for item in types):
                raise ValueError("types must be an array of component type strings")
            if not types:
                raise ValueError("describe requires type or types")
            result = get_component_contracts(types)
        elif command == "workflow-browser-schema":
            result = make_client().get_workflow_browser_schema()
        elif command == "workflow-search":
            result = make_client().search_workflows(str(payload.get("searchValue", "")))
        elif command == "workflow-browser-list":
            # browser/data 是流程选择器的可靠来源；服务端可能忽略 searchKey，
            # 因而这里统一在已分页拉取的结果上本地按名称过滤。
            search_value = str(payload.get("searchValue", "")).strip()
            rows = make_client().list_workflows_browser(
                page_size=int(payload.get("pageSize", 500)), search_key=""
            )
            if search_value:
                folded = search_value.casefold()
                rows = [row for row in rows if folded in str(row.get("name", "")).casefold()]
            result = {"code": 200, "data": rows}
        elif command == "workflow-list":
            result = make_client().list_workflows(
                current=int(payload.get("current", 1)),
                page_size=int(payload.get("pageSize", 30)),
            )
        elif command == "recipient-search":
            result = make_client().search_recipients(
                str(payload.get("searchValue", "")),
                current=int(payload.get("current", 1)),
                page_size=int(payload.get("pageSize", 30)),
                company_id=str(payload.get("companyId", "")),
            )
        elif command == "workflow-nodes":
            result = make_client().list_workflow_nodes(
                str(payload["workflowId"]), str(payload.get("searchValue", ""))
            )
        elif command == "workflow-fields":
            target_table_id = payload.get("targetTableId", payload.get("objId"))
            if not target_table_id:
                raise ValueError("workflow-fields requires targetTableId (the selected e-builder form ID)")
            result = make_client().get_workflow_fields(str(payload["workflowId"]), str(target_table_id))
        elif command == "workflow-context-fields":
            workflow_id = str(payload.get("workflowId", "")).strip()
            if not workflow_id:
                raise ValueError("workflow-context-fields requires workflowId")
            workflow_name = str(payload.get("workflowName", "")).strip()
            data = build_component_context_data(
                "ApproveTrigger",
                {
                    "workflowPath": {
                        "id": workflow_id,
                        "name": workflow_name,
                        "workflowtype": "-1",
                        "bridgeService": "ebuilder",
                    },
                    "triggerTiming": str(payload.get("triggerTiming", "submitted")),
                },
                workflow_id,
                event_node_id="event_1",
                data_mapper=map_draft_data,
            )
            context_result = get_component_context("ApproveTrigger", data, ContextStore())
            fields: list[dict[str, Any]] = []
            for value in context_result.get("context", {}).values():
                if isinstance(value, dict) and value.get("type") == "context_group":
                    for field in value.get("fields", []):
                        if isinstance(field, dict):
                            fields.append(field)
            result = {"workflowId": workflow_id, "fields": fields}
            if bool(payload.get("includeContext", False)):
                result["context"] = context_result.get("context", {})
        elif command == "form-applications":
            result = make_client().list_apps()
        elif command == "form-list":
            result = make_client().list_forms(str(payload["groupId"]))
        elif command == "form-fields":
            resp = make_client().get_form_fields(str(payload["tableId"]), str(payload["appId"]))
            result = {
                "code": resp.get("code") if isinstance(resp, dict) else None,
                "msg": resp.get("msg", "") if isinstance(resp, dict) else "",
                "data": flatten_form_fields_response(resp),
            }
        elif command == "meeting-fields":
            # 与 MeetingCreate 前端 getData/getCustomFormData 完全同源：两次只读接口
            # 返回 SetForm 弹窗的 fields/items/options，而非推断或上下文近似值。
            client = make_client()
            base_resp = client.get_meeting_fields()
            custom_resp = client.get_custom_meeting_fields()
            result = {
                "code": base_resp.get("code") if isinstance(base_resp, dict) else None,
                "msg": base_resp.get("msg", "") if isinstance(base_resp, dict) else "",
                "meetingFields": base_resp.get("data") if isinstance(base_resp, dict) else None,
                "customMeetingFields": custom_resp.get("data") if isinstance(custom_resp, dict) else None,
                "source": "MeetingCreate front-end getMeetingField/getCustomMeetingField",
            }
        elif command == "init-actionflow":
            client = make_client()
            created = client.create_application(
                normalize_generated_name(payload.get("appName"), "生成的动作流"),
                str(payload.get("appDescription", "")),
                org_id=client.resolve_application_org_id(),
            )
            data = created.get("data", {}) if isinstance(created, dict) else {}
            app_id = str(data.get("id", "")) if isinstance(data, dict) else ""
            if created.get("code") != 200 or not app_id:
                raise ValueError(f"failed to initialize actionflow: {created}")
            versions = client.get_version_list(app_id)
            version_data = versions.get("data", {}) if isinstance(versions, dict) else {}
            active_version = str(version_data.get("activeVersion", "")) if isinstance(version_data, dict) else ""
            result = {
                "appId": app_id,
                "sceneId": active_version,
                "workflowUrl": f"{client.base_url}/sp/esb/efdesigner?application={app_id}",
                "message": "actionflow initialized",
            }
        elif command == "adapt-assignments":
            result = adapt_updates(payload.get("updates"))
        elif command == "prepare-context":
            result = {
                "type": str(payload["type"]),
                "data": build_component_context_data(
                    str(payload["type"]),
                    payload.get("params", {}),
                    str(payload["currentApplication"]),
                    event_node_id=str(payload.get("eventNodeId", "")),
                    data_mapper=map_draft_data,
                ),
            }
        elif command in {"component-context", "context"}:
            component_type = str(payload["type"])
            data = payload.get("data")
            if not isinstance(data, dict):
                raise ValueError("data must be a complete front-end node data object")
            store = ContextStore(payload.get("store", {}))
            result = get_component_context(component_type, data, store)
            context = result.get("context", {})
            if isinstance(context, dict):
                store.merge(context, component_type)
            result["contextStore"] = store.as_dict()
        elif command == "fill-node":
            result = fill_node_context(payload)
        elif command == "normalize":
            result = normalize_semantic_plan(payload)
        elif command == "compile":
            result = compile_workflow_draft(payload)
        elif command == "build":
            result = build_workflow_draft(payload)
        elif command == "validate":
            result = validate_workflow_draft(payload)
        elif command == "to-real":
            draft = payload.get("draft")
            if not isinstance(draft, dict):
                raise ValueError("to-real.draft must be a WorkflowDraft object")
            validation = validate_workflow_draft(draft)
            result = validation if not validation["valid"] else {
                "valid": True,
                "design": convert_draft_to_real(
                    draft, str(payload.get("appId", "")), str(payload.get("sceneId", "")), ""
                ),
                "warnings": validation["warnings"],
            }
        elif command == "generate":
            result = _run_generate(payload)
        elif command == "generate-multi":
            result = _run_generate_multi(payload)
        elif command in {"stash-readback", "readback"}:
            app_id = str(payload.get("appId", "")).strip()
            version_id = str(payload.get("versionId", payload.get("sceneId", ""))).strip()
            if not app_id or not version_id:
                raise ValueError("stash-readback requires appId and versionId (or sceneId)")
            response = make_client().get_stash_snapshot(app_id, version_id)
            if not isinstance(response, dict) or response.get("code") != 200:
                result = {
                    "ok": False,
                    "appId": app_id,
                    "versionId": version_id,
                    "response": response,
                }
            else:
                result = {
                    "ok": True,
                    "appId": app_id,
                    "versionId": version_id,
                    "design": response.get("data", {}),
                }
        elif command == "env-list":
            from core.platform_client import env_list as _env_list
            result = {"environments": _env_list()}
        elif command == "env-current":
            from core.platform_client import env_current as _env_cur
            result = {"current": _env_cur()}
        elif command == "env-switch":
            from core.platform_client import env_switch as _env_sw
            name = str(payload.get("name", "")).strip()
            if not name:
                result = {"ok": False, "error": "缺少 name 参数"}
            else:
                ok = _env_sw(name)
                result = {"ok": ok, "name": name, "error": "" if ok else f"环境 '{name}' 不存在"}
        elif command == "env-add":
            from core.platform_client import env_add as _env_add, env_switch as _env_sw2
            name = str(payload.get("name", "")).strip()
            base_url = str(payload.get("baseUrl", "")).strip()
            eteam_sid = str(payload.get("eteamSid", "")).strip()
            if not name or not base_url or not eteam_sid:
                result = {"ok": False, "error": "缺少 name/baseUrl/eteamSid 参数"}
            else:
                _env_add(
                    name, base_url, eteam_sid,
                    company_id=str(payload.get("companyId", "")).strip(),
                    use_system_proxy=str(payload.get("useSystemProxy", "")).strip().casefold()
                    in {"1", "true", "yes", "on"},
                )
                _env_sw2(name)  # 新增后自动切换
                result = {"ok": True, "name": name, "switched": True}
        elif command == "env-delete":
            from core.platform_client import env_delete as _env_del
            name = str(payload.get("name", "")).strip()
            if not name:
                result = {"ok": False, "error": "缺少 name 参数"}
            else:
                ok = _env_del(name)
                result = {"ok": ok, "name": name, "error": "" if ok else "删除失败"}
        else:
            print_usage()
            return 1
    except Exception as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)], "warnings": []}, ensure_ascii=False))
        return 1

    if not (isinstance(result, dict) and result.pop("_streamed", False)):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
