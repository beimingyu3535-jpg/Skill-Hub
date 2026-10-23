"""动作流生成、暂存和回读编排。"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from core.approve_trigger import enrich_approve_trigger_node
from core.compile_workflow_draft import compile_workflow_draft
from core.condition_service import _build_condition_childrens, _designer_contract_check
from core.draft_to_real import convert as convert_draft_to_real
from core.frontend_check import frontend_check
from core.platform_client import make_client, save_workflow_draft
from core.preflight_service import (
    _get_form_fields_full,
    _preflight_context,
    _register_workflow_detail_meta,
    _step_form_ref,
    _sync_auto_mappings_to_draft,
    _sync_form_references_to_draft,
    _sync_fixed_people_to_draft,
    _sync_biz_fields_to_draft,
    _sync_event_resources_to_draft,
)


def _readback_repair_policy(read_back: Any) -> dict[str, Any]:
    """给回读差异提供保守的后续处理策略。"""
    if not isinstance(read_back, dict) or read_back.get("ok"):
        return {"eligible": False, "maxAttempts": 0, "reason": "回读无待修复差异"}
    if read_back.get("error"):
        return {
            "eligible": False,
            "maxAttempts": 0,
            "reason": "暂存快照读取失败，无法据此安全修改设计",
        }
    return {
        "eligible": False,
        "maxAttempts": 1,
        "reason": "检测到语义差异，但当前没有登记可安全执行的自动修复器；请报告差异后停止",
    }

def normalize_generated_name(name: Any, default: str = "动作流") -> str:
    raw = str(name or default).strip() or default
    return raw if raw.startswith("AI-") else f"AI-{raw}"


def _application_init_context(plan: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    """按当前场景构造 application/save 的 module 与 appSources。

    部分租户仅在 ``moudle=workflow`` 且携带流程来源时创建版本记录；空
    ``appSources`` 虽可在旧租户创建容器，却会在 versionList/saveStashSnapshot
    阶段报“动作流不存在”。这里完全由当前 plan 的真实引用构造，不能复用旧 ID。
    """
    event = plan.get("event", {}) if isinstance(plan, dict) else {}
    params = event.get("params", {}) if isinstance(event, dict) else {}
    workflow_path = params.get("workflowPath", {}) if isinstance(params, dict) else {}
    if isinstance(workflow_path, list):
        workflow_path = workflow_path[0] if workflow_path else {}
    workflow_id = str(workflow_path.get("id", "")) if isinstance(workflow_path, dict) else ""
    if not workflow_id or str(event.get("type") or "") != "ApproveTrigger":
        return "esb", []

    sources: list[dict[str, str]] = [{
        "module": "approve", "businessObject": "workflowPath", "businessValue": workflow_id,
    }]
    seen: set[tuple[str, str]] = set()
    for step in plan.get("actions", []) or []:
        if not isinstance(step, dict) or str(step.get("type") or "") not in {
                "ActionEbAdd", "ActionEbUpdate", "ActionEbDelete", "EnquiryForm"}:
            continue
        action_params = step.get("params", {})
        target = action_params.get("targetForm") or action_params.get("dataSource") if isinstance(action_params, dict) else {}
        if not isinstance(target, dict):
            continue
        app_id = str(target.get("groupId") or target.get("appId") or "")
        if not app_id or ("ebuilder", app_id) in seen:
            continue
        seen.add(("ebuilder", app_id))
        sources.append({"module": "ebuilder", "businessObject": "AppType", "businessValue": app_id})
    return "workflow", sources

def _load_plan(payload: dict[str, Any]) -> dict[str, Any]:
    plan = payload.get("plan")
    if plan is None and "planFile" in payload:
        plan = json.loads(Path(payload["planFile"]).read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("plan must be an object or planFile must point to a JSON object")
    return plan

def _attempt_fallback_save(plan: dict, draft: dict | None, client, app_id: str,
                           workflow_url: str, payload: dict, design: dict | None,
                           reason: str, errors: list[str]) -> dict | None:
    """保存失败后尽力保留可打开的骨架暂存。"""
    app_name = normalize_generated_name(payload.get("appName"), "生成的动作流")
    candidates: list[tuple[str, dict]] = []
    if isinstance(design, dict):
        candidates.append(("原设计", design))
    if isinstance(draft, dict):
        try:
            relaxed = convert_draft_to_real(draft, app_id, "", "", lenient=True)
            relaxed.pop("_lenient_warnings", None)
            candidates.append(("宽松转换(剔除失败字段)", relaxed))
        except Exception:
            pass
    for label, cand in candidates:
        try:
            saved = save_workflow_draft(
                cand, client=client, app_name=app_name,
                app_description=str(payload.get("appDescription", "")),
                verify_readback=bool(payload.get("verifyReadback", True)),
            )
        except Exception:
            continue
        if saved.get("ok"):
            return {
                "valid": False,
                "saved": True,
                "fallbackSaved": True,
                "fallbackReason": reason,
                "appId": saved.get("appId", ""),
                "sceneId": saved.get("sceneId", ""),
                "workflowUrl": saved.get("workflowUrl", ""),
                "errors": errors,
                "message": f"保底预览版已保存（{label}，请在设计器里补充）。原因: {reason}",
                "checkResponse": saved.get("checkResponse"),
                "readBack": saved.get("readBack"),
                "readBackVerified": bool((saved.get("readBack") or {}).get("ok", False)),
                "repairPolicy": _readback_repair_policy(saved.get("readBack")),
            }
    return None

def _find_enquiry_count_conditions(steps: list[Any], prefix: str = "actions") -> list[str]:
    """找出使用 EnquiryForm 计数输出的条件，供生成前诊断使用。

    计数是查询节点的运行时输出，必须绑定为 ``response.count`` 且来源为
    EnquiryForm，不能降级或伪装为流程字段。该结构已在真实租户正式保存并回读。
    """
    paths: list[str] = []
    for index, step in enumerate(steps or []):
        if not isinstance(step, dict) or step.get("type") != "Condition":
            continue
        raw_branches = step.get("branches")
        if not isinstance(raw_branches, list):
            raw_branches = (step.get("params") or {}).get("branches", []) \
                if isinstance(step.get("params"), dict) else []
        for branch_index, branch in enumerate(raw_branches or []):
            if not isinstance(branch, dict):
                continue
            condition = branch.get("condition") or {}
            left = condition.get("left") if isinstance(condition, dict) else {}
            key = str((left or {}).get("key") or (left or {}).get("paramKey") or "") \
                if isinstance(left, dict) else ""
            if key in {"count", "response.count", "Response.response.count"}:
                paths.append(f"{prefix}[{index}].branches[{branch_index}]")
    return paths

def _finish_generate_after_check(design: dict, plan: dict, client, app_id: str,
                                 workflow_url: str, payload: dict, out_path: Any,
                                 preflight: dict, struct_warnings: list[str]) -> dict:
    """结构自检通过后的后半程: Condition 两步法 → 保存 → 回读 → 绑定流程节点 → 组装 result."""
    # ── Condition 两步法: saveCondition 拿 server ID ──
    cond_resolved, cond_failures = _resolve_condition_ids(design, plan, client)
    cond_note = f"（{cond_resolved} 个条件分支已自动配置）" if cond_resolved > 0 else ""
    if cond_failures:
        # 条件未全部解析成功: 中止保存, 避免带假 conditionId 保存
        # （平台预检时 conditionDetail 会被清空，且不会明确报错）。
        return {
            "valid": False,
            "appId": app_id,
            "workflowUrl": workflow_url,
            "errors": cond_failures,
            "message": "条件分支自动配置失败，未调用暂存",
        }

    saved = save_workflow_draft(
        design,
        client=client,
        app_name=normalize_generated_name(payload.get("appName"), "生成的动作流"),
        app_description=str(payload.get("appDescription", "")),
        # 只暂存: saveStashSnapshot + getStashSnapshot 严格回读，不提供正式保存分支。
        verify_readback=bool(payload.get("verifyReadback", True)),
    )
    if out_path:
        Path(out_path).write_text(json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8")
    read_back = saved.get("readBack")
    readback_ok = not isinstance(read_back, dict) or bool(read_back.get("ok", False))

    #  **不再调用 save_add_action_list 绑定流程节点触发** —
    # submitted→发起节点, approve_passed→审批节点, 均自动注册);
    # ②绑定会把 basisValueFormula.source 重写为流程注册 id (同流程 app 同一值),
    # 保留 SKIP_TRIGGER_BIND=1 语义兼容 (默认即跳过).
    bind_msg = ""

    warn_note = f"; 自检警告: {'; '.join(struct_warnings)}" if struct_warnings else ""
    return {
        # 暂存成功即生成成功；回读用于诊断平台是否改写了设计，不能把已暂存
        # 的动作流错误标成失败。
        "valid": bool(saved.get("ok")),
        "saved": bool(saved.get("ok")),
        "output": out_path,
        "appId": saved.get("appId", ""),
        "sceneId": saved.get("sceneId", ""),
        "workflowUrl": saved.get("workflowUrl", ""),
        "message": saved.get("msg", "") + bind_msg + cond_note + warn_note,
        "checkResponse": saved.get("checkResponse"),
        "readBack": read_back,
        "readBackVerified": readback_ok,
        "repairPolicy": _readback_repair_policy(read_back),
        "contextStore": preflight["contextStore"],
        "autoMappings": preflight.get("autoMappings", []),
        "autoResources": preflight.get("autoResources", []),
    }

def _resolve_condition_ids(design: dict, plan: dict, client) -> tuple[int, list[str]]:
    """对 design 中每个 Condition 节点调 ESB saveCondition, 用 server 返回的
    conditionDataJson 覆盖 conditionDetail.

    Returns:
        (成功解析数, 失败原因列表)。失败数 > 0 时调用方必须中止保存——
        否则 Condition 节点带着本地假 conditionId 暂存，平台预检时
        conditionDetail 会被清空(静默出错)。
    """
    event = plan.get("event", {})
    if not isinstance(event, dict):
        return 0, []
    # (组件契约) 或顶层 workflowId (SKILL.md 示例)。只认顶层 workflowId 时,
    # 用 params 格式的 plan 会静默跳过 saveCondition 两步法 → Condition 带
    # 假 conditionId 暂存 → 平台预检清空 conditionDetail（回读 data 空）。
    wf_id = str(event.get("workflowId", ""))
    if not wf_id:
        _ev_params = event.get("params", {})
        if isinstance(_ev_params, dict):
            _wp = _ev_params.get("workflowPath", {})
            if isinstance(_wp, dict):
                wf_id = str(_wp.get("id", ""))
    if not wf_id:
        return 0, []
    # sourceId: 优先用 approveNode.id, 回退到 wf_id
    params = event.get("params", {})
    source_id = ""
    if isinstance(params, dict):
        node = params.get("approveNode", {})
        if isinstance(node, dict):
            source_id = str(node.get("id", ""))
    if not source_id:
        source_id = wf_id

    # 预取 ESB conditionFieldBrowser 真实可见字段 (source=8, design-time),
    # 构造 name → formId 映射, 注入到 _build_condition_detail 走的 meta
    # 路径, 让 converter 用 "{formId}.{fieldId}" 格式 (非 workflowId).
    visible_form_ids: dict[str, str] = {}
    try:
        vitems = client.get_condition_visible_fields(wf_id, source_id, source=8)
        for f in vitems if isinstance(vitems, list) else []:
            if isinstance(f, dict):
                name = str(f.get("name", "")).strip()
                formid = str(f.get("formId", "")).strip()
                if name and formid:
                    visible_form_ids[name] = formid
    except Exception:
        pass

    # 把 visible_form_ids 注入 design 顶层 (draft_to_real.convert 读 meta 时取)
    if visible_form_ids:
        design["_visible_form_ids"] = visible_form_ids

    plan_actions = plan.get("actions", [])
    # 默认条件引用流程触发器上下文；EnquiryForm.count 则必须引用紧邻查询节点。
    # 否则 saveCondition 虽会返回 200，但前端在 cacheContext 找不到 count，显示为空。
    event_node = design.get("event") or {}
    default_upstream_w_id = str(event_node.get("wId") or event_node.get("id") or "")
    resolved = 0
    failures: list[str] = []
    for i, action in enumerate(design.get("actions", [])):
        if action.get("type") != "Condition":
            continue
        plan_action = plan_actions[i] if i < len(plan_actions) else {}
        upstream_w_id = default_upstream_w_id
        if _find_enquiry_count_conditions([plan_action]):
            # 计数输出由最近的 EnquiryForm 节点产生，而不是由流程触发器产生。
            for previous in reversed(design.get("actions", [])[:i]):
                if isinstance(previous, dict) and previous.get("type") == "EnquiryForm":
                    upstream_w_id = str(previous.get("wId") or previous.get("id") or "")
                    break
            if not upstream_w_id:
                failures.append(
                    f"actions[{i}](Condition): response.count 条件前没有 EnquiryForm 查询节点"
                )
                continue
        childrens = _build_condition_childrens(plan_action, wf_id, source_id, upstream_w_id, client)

        # Step 1: ESB getConditionSet (GET) → mapBaseId
        map_base_id = client.esb_get_condition_set()
        if not map_base_id:
            failures.append(f"actions[{i}](Condition): getConditionSet 未返回 mapBaseId")
            continue

        # Step 2: ESB saveCondition (POST) → conditionId/conditionDataJson
        sc = client.esb_save_condition(wf_id, source_id, map_base_id,
                                       childrens, f"AI_COND_{i}")
        sc_data = sc.get("data", {})
        server_cdj = sc_data.get("conditionDataJson", "")
        server_cid = str(sc_data.get("conditionId", ""))
        if not server_cdj or not server_cid:
            failures.append(
                f"actions[{i}](Condition): ESB saveCondition 失败 "
                f"(code={sc.get('code')}, msg={str(sc.get('msg',''))[:80]})"
            )
            continue

        # Step 3: 覆盖 conditionDetail (mapBaseId = conditionKey, 前端约定)
        d = action.get("data", {})
        old_detail = d.get("conditionDetail", {})
        d["conditionId"] = server_cid
        d["conditionDetail"] = {
            "conditionId": server_cid,
            "conditionCn": sc_data.get("conditionCn", old_detail.get("conditionCn", "")),
            "mapBaseId": str(sc_data.get("conditionKey", map_base_id)),
            "mapId": str(sc_data.get("mapId", "")),
            "sourceIds": old_detail.get("sourceIds", []),
            "conditionDataJson": server_cdj,
        }
        resolved += 1
    return resolved, failures

def _run_generate(payload: dict) -> dict:
    """单场景生成主流程：编译、预检、转换、检查、暂存与回读。"""
    deadline = time.monotonic() + 180.0

    def _check_deadline(stage: str) -> None:
        if time.monotonic() > deadline:
            raise RuntimeError(f"场景时间预算超时(180s)@{stage}")

    # 查询阶段 (未创建 app, 重试安全): enrich_approve_trigger_node 调 workflow-nodes
    for _attempt in range(2):
        try:
            plan = _load_plan(payload)
            plan = enrich_approve_trigger_node(plan)
            break
        except Exception:
            if _attempt == 0:
                continue
            raise
    _check_deadline("compile")
    enrich_errors = plan.pop("_enrich_errors", [])
    compilation = compile_workflow_draft(plan)
    if enrich_errors:
        # 触发器节点不存在 → 强制中止, 避免静默生成错节点
        result = {
            "valid": False,
            "errors": enrich_errors,
            "message": "触发器节点解析失败: " + "; ".join(enrich_errors),
        }
    elif _find_enquiry_count_conditions(plan.get("actions") or []):
        # 已用真实 EnquiryForm 上下文（response.count，paramType=int）及设计器同源
        # saveCondition 端点验证：后端仍要求左侧为 workflow formField，查询输出会
        # 报 `formField is null`。不得以空叶子或默认“不为空”冒充该分支。
        # 因此在创建应用前明确拒绝，直到平台提供可保存的查询输出条件结构。
        count_paths = _find_enquiry_count_conditions(plan.get("actions") or [])
        result = {
            "valid": False,
            "saved": False,
            "errors": [
                f"{', '.join(count_paths)}: 当前平台 saveCondition 仅接受表单字段左值；"
                "EnquiryForm.response.count 返回 formField is null，不能生成可用条件分支。"
            ],
            "message": "查询计数条件当前不受平台 Condition 支持，未创建动作流，避免生成空白条件。",
        }
    elif not compilation["valid"]:
        compile_errors = compilation.get("errors", [])
        fallback_result = None
        try:
            safe_plan = {"event": plan.get("event", {}), "actions": [{"type": "Output", "params": {}}]}
            safe_compilation = compile_workflow_draft(safe_plan)
            safe_draft = safe_compilation.get("draft") if safe_compilation.get("valid") else None
            if isinstance(safe_draft, dict):
                client = make_client()
                app_name = normalize_generated_name(payload.get("appName"), "生成的动作流")
                created = client.create_application(app_name, str(payload.get("appDescription", "")))
                created_data = created.get("data", {}) if isinstance(created, dict) else {}
                app_id = str(created_data.get("id", "")) if isinstance(created_data, dict) else ""
                if isinstance(created, dict) and created.get("code") == 200 and app_id:
                    workflow_url = f"{client.base_url}/sp/esb/efdesigner?application={app_id}"
                    fallback_result = _attempt_fallback_save(
                        safe_plan, safe_draft, client, app_id, workflow_url, payload,
                        None, "语义计划编译失败，已保留真实触发器骨架", compile_errors,
                    )
        except Exception:
            fallback_result = None
        result = fallback_result or {"valid": False, "saved": False, **compilation}
    else:
        draft = compilation["draft"]
        out_path = payload.get("output")
        if payload.get("previewOnly"):
            # previewOnly 也查询 workflow-fields,登记字段 id 映射
            # (平台数据 paramKey 必须用 "{workflowId}.{fieldId}" 数字格式)
            try:
                client = make_client()
                ev = plan.get("event", {}) if isinstance(plan, dict) else {}
                # previewOnly 也必须预取目标表单的完整字段元数据；否则
                # _build_filter_input 无法按 componentKey/type 生成条件，
                # 预览会在正式 generate 能通过的同一计划上误报“字段不在表单”。
                def hydrate_preview_fields(steps: list[Any]) -> None:
                    for step in steps or []:
                        if not isinstance(step, dict):
                            continue
                        if step.get("type") in {
                                "ActionEbAdd", "ActionEbUpdate", "ActionEbDelete", "EnquiryForm",
                                "TimeBatchTrigger", "EventFormData", "DateTrigger"}:
                            tf = _step_form_ref(step)
                            if tf and tf.get("id"):
                                _get_form_fields_full(str(tf["id"]), client, tf)
                        if step.get("type") == "Condition":
                            for branch in step.get("branches") or []:
                                if isinstance(branch, dict):
                                    hydrate_preview_fields(branch.get("actions") or [])

                hydrate_preview_fields([ev])
                hydrate_preview_fields(plan.get("actions") or [])
                #  previewOnly 与正式路径一致 — 注册流程明细表
                # 依据值名退回 plan label / main allName 退回明细表 id, 预览与正式不一致).
                try:
                    _register_workflow_detail_meta(ev, client)
                except Exception:
                    pass
                wf_id = str(ev.get("workflowId", "") or (
                    ev.get("params", {}).get("workflowPath", {})
                    if isinstance(ev.get("params"), dict)
                    else {}).get("id", ""))
                if wf_id:
                    fid = _FORM_ID_CACHE.get(wf_id, "")
                    if not fid:
                        for s in plan.get("actions", []):
                            tp = s.get("params", {}).get("targetForm", {}) if isinstance(s.get("params"), dict) else {}
                            if isinstance(tp, dict) and tp.get("id"):
                                fid = str(tp["id"])
                                break
                    if fid:
                        _FORM_ID_CACHE[wf_id] = fid
                        wf_fields = client.get_workflow_fields(wf_id, fid)
                        if isinstance(wf_fields, dict) and isinstance(wf_fields.get("data"), list):
                            from core.runtime_metadata import register_workflow_field_ids
                            register_workflow_field_ids(wf_id, wf_fields["data"])
            except Exception:
                pass
            design = convert_draft_to_real(
                draft,
                str(payload.get("appId", "")),
                str(payload.get("sceneId", "")),
                "",
            )
            if out_path:
                Path(out_path).write_text(json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8")
            result = {
                "valid": True,
                "draft": draft,
                "design": design,
                "output": out_path,
            }
        else:
            # Grill 决策(清理中间件):
            #   - 查询上下文阶段不创建应用 — getComponentContext 不校验
            #     currentApplication, 验证占位值 '0' 正常返回. 应用创建推迟到
            #     "第一次需要暂存"时（预检通过后）。
            #   - 只回收本次新建且最终未暂存成功的应用；用户传入的 appId 不回收。
            client = make_client()
            requested_app_id = str(payload.get("appId", "")).strip()
            app_id = ""
            app_scene_id = ""
            new_app_created = False
            if requested_app_id:
                versions = client.get_version_list(requested_app_id)
                if versions.get("code") == 200 and isinstance(versions.get("data"), dict):
                    app_id = requested_app_id  # 复用已有应用(更新场景), 绝不回收
                    app_scene_id = str(versions["data"].get("activeVersion", "") or "")
                else:
                    requested_app_id = ""  # 传入的 appId 无效, 按新建处理
            app_name = normalize_generated_name(payload.get("appName"), "生成的动作流")
            app_desc = str(payload.get("appDescription", ""))
            app_module, app_sources = _application_init_context(plan)

            def _ensure_app() -> str:
                """第一次需要保存时创建应用; 成功返回 app_id, 失败返回 ''."""
                nonlocal app_id, app_scene_id, new_app_created
                if app_id:
                    return app_id
                try:
                    created = client.create_application(
                        app_name, app_desc,
                        org_id=client.resolve_application_org_id(),
                        module=app_module, app_sources=app_sources)
                except Exception:
                    created = {}
                created_data = created.get("data", {}) if isinstance(created, dict) else {}
                if isinstance(created, dict) and created.get("code") == 200 \
                        and isinstance(created_data, dict) and created_data.get("id"):
                    app_id = str(created_data["id"])
                    # 新建接口同步返回 activeVersion。部分租户的 versionList 会在
                    # 随后短时间内返回 500，必须保留该版本号供暂存接口定位应用。
                    app_scene_id = str(created_data.get("activeVersion", "") or "")
                    new_app_created = True
                else:
                    app_id = ""
                return app_id

            # preflight 查询上下文: 占位 currentApplication (不创建应用)
            _check_deadline("preflight")
            preflight = _preflight_context(plan, app_id or "0", client)
            workflow_url = f"{client.base_url}/sp/esb/efdesigner?application={app_id}" if app_id else ""
            if not preflight["valid"]:
                requires_confirmation = any(
                    "confirmTypeMismatch=true" in str(error)
                    for error in preflight.get("errors", [])
                )
                if requires_confirmation:
                    # 类型不兼容的显式映射不是技术失败，必须暂停向规则；
                    # 不创建应用，避免把可疑数据写入平台。
                    result = {
                        "valid": False,
                        "needsUserConfirmation": True,
                        "errors": preflight["errors"],
                        "contextStore": preflight["contextStore"],
                        "autoMappings": preflight.get("autoMappings", []),
                        "autoResources": preflight.get("autoResources", []),
                        "message": "检测到字段类型不兼容的显式映射，已暂停；请向用户确认后重试。",
                    }
                    return result
                # 预检失败时直接报错返回，不创建或暂存动作流。
                result = {
                    "valid": False,
                    "errors": preflight["errors"],
                    "contextStore": preflight["contextStore"],
                    "message": "上下文预检未通过，未创建应用、未保存保底；请修正语义计划后重试",
                }
            else:
                # 预检通过 → 真正保存前才创建应用
                if not app_id:
                    _ensure_app()
                if not app_id:
                    result = {
                        "valid": False,
                        "errors": ["failed to initialize actionflow"],
                        "warnings": [],
                    }
                else:
                    workflow_url = f"{client.base_url}/sp/esb/efdesigner?application={app_id}"
                    # 同步 preflight 注入的 _bizFields (新建流程目标表单字段) 到 draft,
                    # 供 convert 阶段生成 ApproveCreate.fields
                    _sync_biz_fields_to_draft(draft, plan)
                    # 同步 preflight 自动映射补全的 plan mapping 到 draft
                    _sync_auto_mappings_to_draft(draft, plan)
                    # 同步预检按当前租户补齐的表单名称/text；转换器消费 draft，
                    # 不同步会把 groupId/id 的半成品渲染为“选择表单”。
                    _sync_form_references_to_draft(draft, plan)
                    _sync_event_resources_to_draft(draft, plan)
                    _sync_fixed_people_to_draft(draft, plan)
                    _check_deadline("convert")
                    design = convert_draft_to_real(draft, app_id, app_scene_id, "")

                    # ── 前端检查 (完全复刻设计器前端 checkData + items required) ──
                    # 的 required 字段; 与画布保存前拦截的错误完全一致。
                    frontend_errors, frontend_warnings = frontend_check(design)
                    if frontend_errors:
                        base_result = {
                            "valid": False,
                            "appId": app_id,
                            "workflowUrl": workflow_url,
                            "errors": frontend_errors,
                            "warnings": frontend_warnings,
                            "message": "前端检查未通过，未调用暂存（复刻设计器 checkData/required 规则）",
                        }
                        fb = _attempt_fallback_save(
                            plan, draft, client, app_id, workflow_url, payload,
                            design, "前端必填检查未通过", frontend_errors)
                        result = fb if fb else base_result
                    else:
                        # ── 设计器契约自检: UI 显示层字段 (groupId/objType/paramKey/condition) ──
                        contract_errors, contract_warnings = _designer_contract_check(design)
                        frontend_warnings = (frontend_warnings or []) + contract_warnings
                        if contract_errors:
                            base_result = {
                                "valid": False,
                                "appId": app_id,
                                "workflowUrl": workflow_url,
                                "errors": contract_errors,
                                "warnings": frontend_warnings,
                                "message": "设计器契约自检未通过，未调用暂存（防止 UI 显示错位）",
                            }
                            fb = _attempt_fallback_save(
                                plan, draft, client, app_id, workflow_url, payload,
                                design, "设计器契约自检未通过", contract_errors)
                            result = fb if fb else base_result
                        else:
                            _check_deadline("save")
                            result = _finish_generate_after_check(
                                design, plan, client, app_id, workflow_url,
                                payload, out_path, preflight, frontend_warnings,
                            )
                            if (isinstance(result, dict) and not result.get("valid")
                                    and not result.get("saved") and not result.get("fallbackSaved")):
                                fb = _attempt_fallback_save(
                                    plan, draft, client, app_id, workflow_url, payload,
                                    design, str(result.get("message", "保存未通过")),
                                    result.get("errors", []))
                                if fb:
                                    result = fb

            # 新建失败应用自动回收 (软删 addRecycle).
            # 只回收"本次新建且最终没有任何内容落库"的应用; 用户传入的 appId 不回收.
            if new_app_created and isinstance(result, dict) \
                    and not result.get("saved") and app_id:
                try:
                    client.recycle_application(app_id)
                    result["recycledAppId"] = app_id
                    result["message"] = f"{(result.get('message') or '')}；失败应用已自动回收(软删,可在回收站恢复)"
                except Exception as _rec_exc:
                    result.setdefault("warnings", []).append(
                        f"失败应用 {app_id} 自动回收失败({_rec_exc})，请手动在平台删除")

            # 规范: "新建 app + 删旧 app"自动化 —
            # 本次**保存成功(saved=True)**后自动软删旧版, 不再依赖宿主手动回收.
            # 失败不回收旧版；recycleAppId == 本次 app_id 时跳过防误删.
            recycle_app_id = str(payload.get("recycleAppId", "")).strip()
            if recycle_app_id and recycle_app_id != app_id and isinstance(result, dict) \
                    and result.get("saved"):
                try:
                    client.recycle_application(recycle_app_id)
                    result["recycledAppId"] = recycle_app_id
                    result["message"] = f"{(result.get('message') or '')}；旧版应用已回收(软删,可在回收站恢复)"
                except Exception as _old_rec_exc:
                    result.setdefault("warnings", []).append(
                        f"旧版应用 {recycle_app_id} 回收失败({_old_rec_exc})，请手动在平台删除")

    return result

def _run_generate_multi(payload: dict) -> dict:
    """一次给多个场景, 逐个独立生成 (每个场景独立 appId), 单场景失败不影响其他.

    payload.scenarios = [{name?, appName?, appDescription?, plan, appId?, previewOnly?}, ...]
    每个元素是单个 generate 的 payload; plan 为必填.
    返回汇总结果: {valid, count, ok, failed, results: [...单场景 result...]}.
    单场景 result 含 appId/workflowUrl/valid/saved/message/errors；失败项没有 workflowUrl。

     鲁棒性:
    - stream=True 时每个场景完成后立即 print 一行 NDJSON {"type":"scenario",...}(flush),
      最后汇总 {"type":"summary",...} — 宿主即使进程超时 kill 也能读到已完成场景行.
    - 场景异常(含 180s 预算超时 RuntimeError)标记 ⏱️, 不中断批量.
    """
    scenarios = payload.get("scenarios")
    stream = bool(payload.get("stream", False))
    if not isinstance(scenarios, list) or not scenarios:
        return {
            "valid": False,
            "errors": ["generate-multi.scenarios 必须是非空数组: [{name?, plan:{...}}, ...]"],
        }
    results: list[dict] = []
    ok = 0
    for i, sc in enumerate(scenarios):
        sc_plan = None
        if isinstance(sc, dict):
            sc_plan = sc.get("plan")
            # 支持 planFile: 从 JSON 文件读 plan, 绕开 shell 引号转义
            if sc_plan is None and sc.get("planFile"):
                try:
                    sc_plan = json.loads(Path(sc["planFile"]).read_text(encoding="utf-8"))
                except Exception as _pf_exc:
                    r = {
                        "index": i,
                        "name": str(sc.get("name", "")),
                        "valid": False,
                        "skipped": True,
                        "errors": [f"planFile 读取失败: {_pf_exc}"],
                    }
                    results.append(r)
                    continue
        if not isinstance(sc_plan, dict):
            r = {
                "index": i,
                "name": str(sc.get("name", "")) if isinstance(sc, dict) else "",
                "valid": False,
                "skipped": True,
                "errors": ["缺少 plan 或 planFile (每个场景必须带 plan 对象或 planFile 路径)"],
            }
        else:
            sc_payload = {k: v for k, v in sc.items() if k != "plan"}
            sc_payload["plan"] = sc_plan
            sc_payload.setdefault("appName", f"AI-动作流{i + 1}")
            try:
                r = _run_generate(sc_payload)
            except Exception as exc:  # 单场景异常(含超时)不中断批量
                r = {
                    "valid": False,
                    "skipped": True,
                    "timeout": "时间预算超时" in str(exc),
                    "errors": [f"生成异常: {exc}"],
                }
            if not isinstance(r, dict):
                r = {"valid": False, "errors": [f"异常返回: {r}"]}
        r.setdefault("index", i)
        r.setdefault("name", str(sc.get("name") or sc_payload.get("appName") or f"场景{i + 1}"))
        results.append(r)
        if r.get("valid") or r.get("fallbackSaved"):
            ok += 1
        if stream:
            line = {"type": "scenario", **{k: r.get(k) for k in
                    ("index", "name", "appId", "workflowUrl", "valid", "saved",
                     "fallbackSaved", "timeout", "skipped", "message", "errors")}}
            print(json.dumps(line, ensure_ascii=False), flush=True)
    failed = len(results) - ok
    summary = {
        "valid": True,
        "count": len(results),
        "ok": ok,
        "failed": failed,
        "results": results,
        "message": f"完成 {len(results)} 个场景: {ok} 成功/保底, {failed} 失败",
    }
    if stream:
        line = {"type": "summary", **{k: summary[k] for k in
                ("valid", "count", "ok", "failed", "message")}}
        print(json.dumps(line, ensure_ascii=False), flush=True)
        # stream 模式汇总行已实时输出, 不把 results 数组再打一遍 (main 只打印 summary)
        summary.pop("results", None)
        summary["_streamed"] = True  # 通知 main 跳过重复打印
    return summary
