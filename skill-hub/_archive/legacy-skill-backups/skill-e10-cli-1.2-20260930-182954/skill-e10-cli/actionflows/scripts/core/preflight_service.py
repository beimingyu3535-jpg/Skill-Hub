"""表单元数据解析、映射补全与生成前校验。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from core.context_preflight import _query_node_context
from core.context_provider import ContextStore, ContextUnavailableError, PlatformContextProvider
from core.runtime_metadata import (
    _TARGET_FORM_FIELDS,
    _TARGET_DETAIL_FIELDS,
    _WORKFLOW_DETAIL_FIELDS,
    _WORKFLOW_DETAIL_NAMES,
    _WORKFLOW_FIELD_IDS,
    register_target_form_fields,
    register_workflow_context_fields,
    register_workflow_field_ids,
)
from core.field_mapping import auto_map_fields, component_group as _component_group, lcs_len

_WORKFLOW_NODES_CACHE: dict[str, list] = {}
# 进程内缓存: workflowId → workflow-fields 的 targetTableId (避免每次 list_apps/list_forms)
_FORM_ID_CACHE: dict[str, str] = {}
# 进程内缓存: formId → {groupId, groupName, name} (targetForm 补全用, 10 分钟 TTL)
_FORM_INDEX_CACHE: dict[str, dict[str, str]] = {}
_FORM_INDEX_TS: float = 0.0
_FORM_INDEX_TTL: float = 600.0
# ESB Condition 字段浏览器缓存 (source=8, design-time 真实可见字段)
# 替代 workflow-fields API 作为字段名→id 映射的权威源.
# key: (workflowId, sourceId), value: list[{id, name, formId, ...}]
_VISIBLE_FIELDS_CACHE: dict[tuple[str, str], list[dict]] = {}
# 进程内缓存: formId → {fieldId: componentKey} (mapping 类型校验用, 表单字段 schema 不变)
_FORM_FIELD_TYPE_CACHE: dict[str, dict[str, str]] = {}
# 进程内缓存: formId → [完整字段 dict] (自动映射用, 含 id/showName/componentKey/paramType)
_FORM_FIELDS_CACHE: dict[str, list[dict]] = {}


def _fill_required_trigger_operator(plan: dict[str, Any], client) -> list[dict[str, str]]:
    """为必填的表单定时触发器补一个当前租户真实操作人。

    这不是伪造默认值：只在用户未提供操作人时读取人员浏览器，写入其原始
    ``id/name``。选择结果随本次生成返回，便于用户替换。无法查询时保持缺失，
    由前端校验阻止暂存。
    """
    event = plan.get("event") if isinstance(plan, dict) else None
    if not isinstance(event, dict) or event.get("type") not in {"DateTrigger", "TimeBatchTrigger"}:
        return []
    params = event.setdefault("params", {})
    if not isinstance(params, dict) or params.get("operator"):
        return []
    response = client.search_recipients(page_size=30)
    rows = ((response or {}).get("data") or {}).get("data") or []
    candidates = [row for row in rows if isinstance(row, dict) and row.get("id")
                  and str(row.get("statusCode", "normal")) == "normal"]
    if not candidates:
        return []
    # 浏览器顺序就是当前租户可选人员顺序；按 id 二次排序使结果可复现。
    chosen = sorted(candidates, key=lambda row: str(row["id"]))[0]
    value = {"id": str(chosen["id"]), "name": str(chosen.get("name") or chosen.get("content") or "")}
    params["operator"] = value
    record = {
        "path": "event.params.operator",
        "resourceType": "user_assignment",
        "value": value,
        "reason": "操作人必填但需求未指定；从当前租户人员浏览器选择真实可用人员",
    }
    plan.setdefault("_autoResources", []).append(record)
    return [record]


def _walk_plan_steps(value: Any):
    """Yield action/event-shaped plan nodes, including nested branch actions."""
    if isinstance(value, dict):
        if isinstance(value.get("type"), str) and isinstance(value.get("params"), dict):
            yield value
        for child in value.values():
            yield from _walk_plan_steps(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_plan_steps(child)


def _is_browser_person(value: Any) -> bool:
    """A display label alone is not a MeetingCreate Browser value."""
    return isinstance(value, dict) and bool(value.get("id")) and bool(
        value.get("originTargetType") or value.get("mainId") or value.get("userid")
    )


def _resolve_fixed_people(plan: dict[str, Any], client) -> list[dict[str, Any]]:
    """Expand explicit fixed people to exact current-tenant Browser objects.

    Browser metadata is presentation data as well as an execution reference:
    a hand-written ``{id, name}`` may stash, but loses avatar/department and
    can render as a raw ID.  Resolve it before every component mapper so fixed
    user values retain the exact Browser object returned by this tenant.
    """
    records: list[dict[str, Any]] = []
    component_people = {
        "MeetingCreate": ("caller", "contacter", "hrmMembers"),
        "ScheduleCreate": ("creatorUser", "manager", "participants", "sharedUsers"),
        "ApproveCreate": ("operator",),
    }
    for step in _walk_plan_steps(plan.get("actions", [])):
        component_type = str(step.get("type") or "")
        person_keys = component_people.get(component_type, ())
        if not person_keys:
            continue
        params = step.get("params") or {}
        fields = params.get("meetingFields")
        containers: list[tuple[str, dict[str, Any]]] = [("meetingFields", fields)] if isinstance(fields, dict) else []
        containers.append(("params", params))
        for container_name, container in containers:
            for key in person_keys:
                raw = container.get(key)
                if raw is None:
                    continue
                values = raw if isinstance(raw, list) else [raw]
                if values and all(_is_browser_person(item) for item in values):
                    continue
                if not values or not all(isinstance(item, dict) and item.get("id") for item in values):
                    continue
                resolved: list[dict[str, Any]] = []
                for item in values:
                    query = str(item.get("name") or item.get("id"))
                    response = client.search_recipients(query, page_size=30)
                    rows = ((response or {}).get("data") or {}).get("data") or []
                    match = next((row for row in rows if isinstance(row, dict) and str(row.get("id")) == str(item["id"])), None)
                    if match is None:
                        raise ValueError(
                            f"MeetingCreate.{key} 的人员 id={item['id']} 不在当前租户人员浏览器中，无法生成可回显的 Browser 对象"
                        )
                    resolved.append(match)
                container[key] = resolved if isinstance(raw, list) else resolved[0]
                records.append({
                    "path": f"{component_type}.{container_name}.{key}",
                    "resourceType": "user_browser",
                    "value": [{"id": str(item["id"]), "name": str(item.get("name") or item.get("content") or "")} for item in resolved],
                    "reason": "固定人员已从当前租户人员浏览器补全为真实对象，保留头像、部门等设计器展示字段",
                })
    if records:
        plan.setdefault("_autoResources", []).extend(records)
    return records


# Backward-compatible internal name for external integrations/tests.
_resolve_meeting_people = _resolve_fixed_people


def _step_form_ref(step: dict) -> dict | None:
    """组件表单引用: 兼容 params.dataSource/targetForm 与 event/step 顶层写法 (2026-08-07).

    TimeBatchTrigger/DateTrigger/EventFormData 的 dataSource 可写在 event 顶层
    (语义 plan) 或 event.params (编译后), 统一取.
    """
    params = step.get("params") or {}
    ref = params.get("targetForm") or params.get("dataSource")
    if not isinstance(ref, dict):
        ref = step.get("dataSource") or step.get("targetForm")
    return ref if isinstance(ref, dict) else None


def _get_form_fields_full(form_id: str, client, tf: dict | None = None) -> list[dict]:
    """查 form-fields 返回完整字段列表 (id/showName/componentKey/paramType), 进程缓存."""
    if form_id in _FORM_FIELDS_CACHE:
        register_target_form_fields(form_id, _FORM_FIELDS_CACHE[form_id])
        return _FORM_FIELDS_CACHE[form_id]
    fields: list[dict] = []
    try:
        app_id = str((tf or {}).get("groupId") or "")
        resp = client.get_form_fields(form_id, app_id)
        raw = resp.get("data", []) if isinstance(resp, dict) else []
        rows: list[Any] = []
        if isinstance(raw, dict):
            # ⚠️ 2026-08-05 23:2x: 解析 detail 结构 (含明细表子字段) → 登记
            # _TARGET_DETAIL_FIELDS[formId][detailTableId] = {fieldId: {name, showName, componentKey}}
            # 供 detail 映射自动按名补全使用. 之前 detail 对象(无 id) 被
            # register_target_form_fields 过滤, 明细表子字段从未进入字段缓存.
            for dt in (raw.get("detail") or []):
                if not isinstance(dt, dict) or not dt.get("detailTableId"):
                    continue
                dt_fields: dict[str, dict] = {}
                for f in (dt.get("fields") or []):
                    if not isinstance(f, dict) or not f.get("id"):
                        continue
                    dt_fields[str(f["id"])] = {
                        "name": str(f.get("showName") or f.get("name") or ""),
                        "showName": str(f.get("showName") or f.get("name") or ""),
                        "componentKey": str(f.get("componentKey") or ""),
                        "type": str(f.get("type") or ""),
                    }
                if dt_fields:
                    _TARGET_DETAIL_FIELDS.setdefault(str(form_id), {})[str(dt["detailTableId"])] = dt_fields
            rows.extend(raw.get("main") or [])
            for dt in (raw.get("detail") or []):
                if isinstance(dt, dict):
                    rows.extend(dt.get("fields") or [])
        elif isinstance(raw, list):
            rows = raw
        for f in rows:
            if not isinstance(f, dict) or not f.get("id"):
                continue
            normalized = dict(f)
            normalized.update({
                "id": str(f["id"]),
                "showName": str(f.get("showName") or f.get("name") or ""),
                "name": str(f.get("name") or f.get("showName") or ""),
                "componentKey": str(f.get("componentKey") or ""),
                "paramType": str(f.get("paramType") or f.get("type") or "").lower(),
                "type": str(f.get("type") or f.get("paramType") or "String"),
            })
            fields.append(normalized)
    except Exception:
        pass
    _FORM_FIELDS_CACHE[form_id] = fields
    register_target_form_fields(form_id, fields)
    return fields


def flatten_form_fields_response(resp: Any) -> list[dict[str, str]]:
    """将 getEbField 的主表/明细表响应展开为给模型使用的真实字段列表。

    明细表在 API 中通常是 ``{detailTableId, fields:[...]}``，不能把表对象本身
    当字段输出；否则调用者只会看到空 id，后续映射只能猜字段。
    """
    data = resp.get("data", {}) if isinstance(resp, dict) else {}
    output: list[dict[str, str]] = []

    def append_field(field: Any, *, scope: str, detail_table_id: str = "") -> None:
        if not isinstance(field, dict):
            return
        field_id = str(field.get("id", field.get("fieldId", "")))
        if not field_id:
            return
        output.append({
            "id": field_id,
            "name": str(field.get("showName", field.get("name", ""))),
            "showName": str(field.get("showName", field.get("name", ""))),
            "type": str(field.get("type", "")),
            "componentKey": str(field.get("componentKey", "")),
            "dataKey": str(field.get("dataKey", "")),
            "scope": scope,
            "detailTableId": detail_table_id,
        })

    if isinstance(data, list):
        for field in data:
            append_field(field, scope="main")
    elif isinstance(data, dict):
        for field in data.get("main", []) or []:
            append_field(field, scope="main")
        for detail in data.get("detail", []) or []:
            if not isinstance(detail, dict):
                continue
            detail_id = str(detail.get("detailTableId", detail.get("id", "")))
            for field in detail.get("fields", []) or []:
                append_field(field, scope="detail", detail_table_id=detail_id)
    return output

# ── mapping 字段类型兼容分组 (2026-08-04 人工检验: TextArea 源误映射 Text 目标) ──
# 源/目标字段的 componentKey 必须落在同一组, 否则拦截报错.
_COMPONENT_GROUPS: dict[str, set[str]] = {
    "single_text": {"Text", "Email", "Phone", "Mobile", "IDCard"},
    "multi_text": {"TextArea"},          # 多行文本独立成组: Text↔TextArea 不允许互映射
    "number": {"NumberComponent", "Money", "Monitor", "Raty", "ProgressBar"},
    "date": {"DateComponent", "TimeComponent"},
    "select": {"Select", "RadioBox", "CheckBox", "ImageRadioBox", "ImageCheckBox"},
    "other": {"RelateBrowser", "TreeSelect", "FileComponent", "ImageComponent",
              "Location", "PositionComponent", "SignatureComponent", "Attachment", "File", "Image"},
}
_GROUP_LABEL: dict[str, str] = {
    "single_text": "单行文本", "multi_text": "多行文本", "number": "数字",
    "date": "日期", "select": "选择类", "other": "其他",
}


def _auto_map_missing_mappings(plan: dict[str, Any], client,
                               event_source_fields: list[dict]) -> int:
    """用户完全未指定 mapping 时，按名称+类型一对一自动补全并记录理由。

    显式 mapping（包括覆盖表映射）绝不改写、不补追加；ActionEbUpdate 的常量/updates
    同样视为用户明确限定。ApproveCreate 使用 getWfField 已注入的 _bizFields。
    """
    added = 0
    if not event_source_fields:
        return 0

    auto_records = plan.setdefault("_autoMappings", [])

    def record_auto(path: str, auto: dict[str, str], target_fields: list[dict], *, object_values: bool) -> dict:
        target_by_id = {str(field.get("id") or ""): field for field in target_fields if isinstance(field, dict)}
        source_by_name = {str(field.get("showName") or ""): field for field in event_source_fields}
        result: dict[str, Any] = {}
        for source_name, target_id in auto.items():
            source = source_by_name.get(source_name, {})
            target = target_by_id.get(str(target_id), {})
            source_type = str(source.get("componentKey") or "")
            target_type = str(target.get("componentKey") or "")
            exact = source_name == str(target.get("showName") or "")
            reason = "字段名完全一致且类型兼容" if exact else "字段名相似且类型兼容"
            result[source_name] = ({"target": str(target_id), "label": source_name}
                                   if object_values else str(target_id))
            auto_records.append({
                "path": path, "source": source_name, "target": str(target_id),
                "targetName": str(target.get("showName") or ""),
                "sourceType": source_type, "targetType": target_type, "reason": reason,
            })
        return result

    def walk_steps(steps: list[Any], prefix: str = "actions") -> None:
        nonlocal added
        for index, step in enumerate(steps or []):
            if not isinstance(step, dict):
                continue
            path = f"{prefix}[{index}]"
            if step.get("type") in ("ActionEbAdd", "ActionEbUpdate"):
                params = step.get("params") or {}
                tf = params.get("targetForm")
                mapping = params.get("mapping")
                if not isinstance(tf, dict) or not tf.get("id"):
                    continue
                if mapping:
                    continue  # 用户已指定, 不动
                # ⚠️ 2026-08-06 17:30: ActionEbUpdate 用户已给 constants/updates 时,
                # 说明明确指定了更新字段 (如场景6 只更新合同状态), 不应再自动映射 —
                # 否则流程同名主表字段被自动塞进 setting.main, 额外更新了用户没要求的字段.
                if step.get("type") == "ActionEbUpdate" and (
                        params.get("constants") or params.get("updates")):
                    continue
                target_fields = _get_form_fields_full(str(tf["id"]), client, tf)
                if not target_fields:
                    continue
                auto = auto_map_fields(target_fields, event_source_fields)
                if auto:
                    # 自动映射的 key 是源字段名(中文); 转换器经 workflow_field_id 转字段 id.
                    # 新环境 get_workflow_fields 只返回 1 字段, 缓存不可靠 → 用 component-context
                    # 返回的 paramKey({workflowId}.{fieldId}) 补注册, 否则中文 paramKey 设计器标"已删除".
                    # ⚠️ paramKey 可能带 ".subcompany" 前缀(子表/分部字段), 必须按 workflow_id 分组注册,
                    # 否则最后一个 subcompany 字段会把整个 wf_map 写错键 (2026-08-04 修复).
                    by_wf: dict[str, dict[str, str]] = {}
                    for sf in event_source_fields:
                        pk = str(sf.get("paramKey") or "")
                        if "." in pk and sf.get("showName"):
                            # 数组字段 paramKey 带 "[]" 后缀 (arrs=true, 如 附件/所属部门),
                            # 必须原样保留 — 丢了设计器匹配不上标"已删除" (2026-08-04 修复).
                            head, _, tail = pk.rpartition(".")
                            by_wf.setdefault(head, {})[str(sf["showName"])] = tail
                    for wf_id, wf_map in by_wf.items():
                        if wf_id and wf_map:
                            _WORKFLOW_FIELD_IDS.setdefault(wf_id, {}).update(wf_map)
                    params["mapping"] = record_auto(path, auto, target_fields, object_values=False)
                    added += len(auto)
            elif step.get("type") == "ApproveCreate":
                params = step.get("params") or {}
                mapping = params.get("mapping")
                biz_fields = params.get("_bizFields") or {}
                target_fields = biz_fields.get("main") if isinstance(biz_fields, dict) else []
                if mapping or not isinstance(target_fields, list) or not target_fields:
                    continue
                auto = auto_map_fields(target_fields, event_source_fields)
                if auto:
                    params["mapping"] = record_auto(path, auto, target_fields, object_values=True)
                    added += len(auto)
            if step.get("type") == "Condition":
                for branch in step.get("branches") or []:
                    if isinstance(branch, dict):
                        walk_steps(branch.get("actions"), f"{path}.branches")

    walk_steps(plan.get("actions"))
    return added


def _find_tf_group(plan: dict[str, Any], form_id: str) -> str:
    """在 plan 的 targetForm/dataSource 里查找 form_id 对应的 groupId (无则空串)."""
    def search(steps: list[dict[str, Any]]) -> str:
        for step in steps or []:
            if not isinstance(step, dict):
                continue
            params = step.get("params") or {}
            if isinstance(params, dict):
                if step.get("type") in {"ActionEbAdd", "ActionEbUpdate", "ActionEbDelete"}:
                    tf = params.get("targetForm")
                    if isinstance(tf, dict) and str(tf.get("id", "")) == str(form_id):
                        return str(tf.get("groupId", ""))
                if step.get("type") in {"EventFormData", "TimeBatchTrigger", "DateTrigger", "EnquiryForm"}:
                    ds = _step_form_ref(step)
                    if ds and str(ds.get("id", "")) == str(form_id):
                        return str(ds.get("groupId", ""))
                if step.get("type") == "Condition":
                    for branch in step.get("branches", []) or []:
                        if isinstance(branch, dict):
                            g = search(branch.get("actions", []))
                            if g:
                                return g
        return ""
    return search(plan.get("actions", []))


def _resolve_target_forms(plan: dict[str, Any], client) -> list[str]:
    """回填 plan 里 targetForm 缺失的 groupId(表单所属应用)/name.

    数据真实性铁律的落实: plan 提到表单时必须补全真实信息, 不能生成 groupId=-1
    (设计器会显示"表单都没选"). 流程:
      1. form-applications 列出全部 e-builder 应用
      2. 并发 form-list 列出各应用表单, 按 id 匹配 targetForm
      3. 匹配到 → 回填 targetForm.groupId=appId, groupName=appName
    返回无法解析的表单 id 列表(调用方决定是否报错).
    """
    # Accept both the Skill reference shape (groupId/id/name/text) and the
    # common API shape (appId/tableId). After this point all callers operate
    # on the designer-compatible keys, including nested Condition branches.
    def normalize_ref(ref: Any) -> None:
        if not isinstance(ref, dict):
            return
        if not ref.get("id") and ref.get("tableId"):
            ref["id"] = str(ref["tableId"])
        if not ref.get("groupId") and ref.get("appId"):
            ref["groupId"] = str(ref["appId"])

    def normalize_steps(steps: list[dict[str, Any]]) -> None:
        for step in steps or []:
            if not isinstance(step, dict):
                continue
            params = step.get("params") or {}
            if isinstance(params, dict):
                normalize_ref(params.get("targetForm"))
                normalize_ref(params.get("dataSource"))
            if step.get("type") == "Condition":
                for branch in step.get("branches", []) or []:
                    if isinstance(branch, dict):
                        normalize_steps(branch.get("actions", []))

    event = plan.get("event") if isinstance(plan, dict) else None
    if isinstance(event, dict):
        event_params = event.get("params") or {}
        if isinstance(event_params, dict):
            normalize_ref(event_params.get("targetForm"))
            normalize_ref(event_params.get("dataSource"))
    normalize_steps(plan.get("actions", []))
    unresolved: list[str] = []

    def collect(steps: list[dict[str, Any]]) -> None:
        for step in steps or []:
            if isinstance(step, dict):
                if step.get("type") in {"ActionEbAdd", "ActionEbUpdate", "ActionEbDelete"}:
                    params = step.get("params", {})
                    if isinstance(params, dict):
                        tf = params.get("targetForm")
                        if isinstance(tf, dict) and tf.get("id"):
                            if not tf.get("groupId") or not tf.get("name") or not tf.get("text") \
                                    or not tf.get("groupName"):
                                unresolved.append(str(tf["id"]))
                if step.get("type") == "Condition":
                    for branch in step.get("branches", []) or []:
                        if isinstance(branch, dict):
                            collect(branch.get("actions", []))
                if step.get("type") in {"EventFormData", "TimeBatchTrigger", "DateTrigger", "EnquiryForm"}:
                    params = step.get("params", {})
                    if isinstance(params, dict):
                        ds = params.get("dataSource") or params.get("targetForm")
                        if isinstance(ds, dict) and ds.get("id"):
                            if not ds.get("groupId") or not ds.get("name") or not ds.get("text") \
                                    or not ds.get("groupName"):
                                unresolved.append(str(ds["id"]))

    if isinstance(event, dict):
        event_params = event.get("params") or {}
        if isinstance(event_params, dict):
            event_source = event_params.get("targetForm") or event_params.get("dataSource")
            if isinstance(event_source, dict) and event_source.get("id"):
                if not event_source.get("groupId") or not event_source.get("name") or not event_source.get("text") \
                        or not event_source.get("groupName"):
                    unresolved.append(str(event_source["id"]))

    collect(plan.get("actions", []))
    if not unresolved:
        return []

    # ⚠️ 2026-08-06 修复: 优先用 plan 已给的 groupId 单应用查询表单(秒级),
    # 不要再触发 393 个应用全量索引(30s+, 进程会被超时静默杀掉)。
    # 只有 groupId 缺失时才回退全量索引(有 10 分钟进程级缓存)。
    import time as _time
    now = _time.time()
    global _FORM_INDEX_CACHE, _FORM_INDEX_TS
    app_names: dict[str, str] | None = None

    def application_name(group_id: str) -> str:
        """Resolve an e-builder application display name only when needed."""
        nonlocal app_names
        if app_names is None:
            app_names = {}
            try:
                apps = client.list_apps()
                for app in apps.get("data", []) if isinstance(apps, dict) else []:
                    if isinstance(app, dict) and app.get("id"):
                        app_names[str(app["id"])] = str(app.get("name") or "")
            except Exception:
                pass
        return app_names.get(group_id, "")

    def group_forms(group_id: str) -> dict[str, dict[str, str]]:
        """查询单个应用下的表单, 建立 {formId: {groupId, groupName, name}}."""
        idx: dict[str, dict[str, str]] = {}
        try:
            forms = client.list_forms(group_id)
            forms_data = forms.get("data", []) if isinstance(forms, dict) else []
            for f in forms_data:
                if isinstance(f, dict) and f.get("id"):
                    idx[str(f["id"])] = {
                        "groupId": group_id,
                        "groupName": application_name(group_id),
                        "name": str(f.get("name", "")),
                    }
        except Exception:
            return idx
        return idx

    # 收集 plan 中已带 groupId 的表单 (targetForm / dataSource), 直接单应用查询
    group_ids: set[str] = set()

    def collect_groups(steps: list[dict[str, Any]]) -> None:
        for step in steps or []:
            if not isinstance(step, dict):
                continue
            params = step.get("params") or {}
            if isinstance(params, dict):
                if step.get("type") in {"ActionEbAdd", "ActionEbUpdate", "ActionEbDelete"}:
                    tf = params.get("targetForm")
                    if isinstance(tf, dict) and tf.get("groupId"):
                        group_ids.add(str(tf["groupId"]))
                if step.get("type") in {"EventFormData", "TimeBatchTrigger", "DateTrigger", "EnquiryForm"}:
                    ds = params.get("dataSource") or params.get("targetForm")
                    if isinstance(ds, dict) and ds.get("groupId"):
                        group_ids.add(str(ds["groupId"]))
                if step.get("type") == "Condition":
                    for branch in step.get("branches", []) or []:
                        if isinstance(branch, dict):
                            collect_groups(branch.get("actions", []))

    collect_groups(plan.get("actions", []))
    if isinstance(event, dict):
        event_params = event.get("params") or {}
        if isinstance(event_params, dict):
            event_source = event_params.get("targetForm") or event_params.get("dataSource")
            if isinstance(event_source, dict) and event_source.get("groupId"):
                group_ids.add(str(event_source["groupId"]))

    form_index: dict[str, dict[str, str]] = {}
    unresolved_no_group: list[str] = []
    # plan 中带 groupId 的表单 → 单应用查 (快路径)
    for gid in group_ids:
        form_index.update(group_forms(gid))
    for fid in unresolved:
        info = form_index.get(fid)
        if not info:
            # 没有 plan 的 groupId 提供 → 记录, 走全量索引回退
            tf_info = _find_tf_group(plan, fid)
            if tf_info:
                form_index.update(group_forms(tf_info))
                info = form_index.get(fid)
        if not info:
            unresolved_no_group.append(fid)

    # 仍然缺失 → 回退全量索引 (393 应用并发, 进程内 10 分钟缓存)
    if unresolved_no_group:
        if now - _FORM_INDEX_TS > _FORM_INDEX_TTL or not _FORM_INDEX_CACHE:
            full_index: dict[str, dict[str, str]] = {}

            def index_app(app: dict[str, Any]) -> None:
                if not isinstance(app, dict):
                    return
                app_id = str(app.get("id", ""))
                if not app_id:
                    return
                try:
                    forms = client.list_forms(app_id)
                    forms_data = forms.get("data", []) if isinstance(forms, dict) else []
                    for f in forms_data:
                        if isinstance(f, dict) and f.get("id"):
                            full_index[str(f["id"])] = {
                                "groupId": app_id,
                                "groupName": str(app.get("name", "")),
                                "name": str(f.get("name", "")),
                            }
                except Exception:
                    return

            try:
                apps = client.list_apps()
                apps_data = apps.get("data", []) if isinstance(apps, dict) else []
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=16) as pool:
                    list(pool.map(index_app, apps_data))
                _FORM_INDEX_CACHE = full_index
                _FORM_INDEX_TS = now
                form_index.update(full_index)
            except Exception:
                pass

    still_missing: list[str] = []
    for fid in unresolved:
        info = form_index.get(fid)
        if not info:
            still_missing.append(fid)
            continue

        def patch(steps: list[dict[str, Any]]) -> None:
            for step in steps or []:
                if isinstance(step, dict):
                    if step.get("type") in {"ActionEbAdd", "ActionEbUpdate", "ActionEbDelete"}:
                        params = step.get("params", {})
                        if isinstance(params, dict):
                            tf = params.get("targetForm")
                            if isinstance(tf, dict) and str(tf.get("id", "")) == fid:
                                tf["groupId"] = info["groupId"]
                                # An empty string is not a resolved display value.  The
                                # designer renders targetForm by text/groupName, so replace
                                # blanks returned by an earlier partial normalization too.
                                if not str(tf.get("name") or "").strip():
                                    tf["name"] = info["name"]
                                if not str(tf.get("text") or "").strip():
                                    tf["text"] = info["name"]
                                if not str(tf.get("groupName") or "").strip():
                                    tf["groupName"] = info["groupName"]
                    if step.get("type") in {"EventFormData", "TimeBatchTrigger", "DateTrigger", "EnquiryForm"}:
                        params = step.get("params", {})
                        if isinstance(params, dict):
                            ds = params.get("dataSource") or params.get("targetForm")
                            if isinstance(ds, dict) and str(ds.get("id", "")) == fid:
                                ds["groupId"] = info["groupId"]
                                if not str(ds.get("name") or "").strip():
                                    ds["name"] = info["name"]
                                if not str(ds.get("text") or "").strip():
                                    ds["text"] = info["name"]
                                if not str(ds.get("groupName") or "").strip():
                                    ds["groupName"] = info["groupName"]
                    if step.get("type") == "Condition":
                        for branch in step.get("branches", []) or []:
                            if isinstance(branch, dict):
                                patch(branch.get("actions", []))
        patch(plan.get("actions", []))
        if isinstance(event, dict):
            event_params = event.get("params") or {}
            if isinstance(event_params, dict):
                event_source = event_params.get("targetForm") or event_params.get("dataSource")
                if isinstance(event_source, dict) and str(event_source.get("id", "")) == fid:
                    event_source["groupId"] = info["groupId"]
                    if not str(event_source.get("name") or "").strip():
                        event_source["name"] = info["name"]
                    if not str(event_source.get("text") or "").strip():
                        event_source["text"] = info["name"]
                    if not str(event_source.get("groupName") or "").strip():
                        event_source["groupName"] = info["groupName"]
    return still_missing


def _check_mapping_types(plan: dict[str, Any], store: ContextStore,
                         client, errors: list[str],
                         event_field_types: dict[str, str] | None = None,
                         warnings: list[str] | None = None) -> None:
    """mapping 源/目标字段类型兼容校验 (2026-08-04 人工检验新增).

    背景: 组装 plan 时若只按字段名不核对 componentKey，可能将 TextArea
    映射到 Text；设计器虽能保存但语义错误。
    此校验把"类型匹配"从模型自觉变为编译器强制: 源/目标 componentKey 必须同组
    (multi_text 独立成组, Text↔TextArea 拦截).

    数据来源:
      - 源字段类型: event_field_types (event 组件 context 查询后立即提取, 含
        componentKey; 不可用 store 的 FormData —— 后续 ActionEbAdd 的 context
        同名覆盖 FormData 分组, 流程字段类型会丢失) + store 补充
      - 目标字段类型: 实时查 form-fields (get_form_fields), 进程内缓存
    查不到类型时跳过 (不误报, 如明细表字段/form-fields 返回空的情况).
    """
    # 1) 源字段类型索引: showName → componentKey (优先 event 触发器提取的)
    src_index: dict[str, str] = dict(event_field_types or {})
    for _k, val in store._store.items():
        if isinstance(val, dict) and val.get("type") == "context_group":
            for f in val.get("fields") or []:
                if isinstance(f, dict) and f.get("showName") and f.get("componentKey"):
                    src_index.setdefault(str(f["showName"]), str(f["componentKey"]))

    # 2) 目标表单字段类型索引 (formId → {fieldId: componentKey})
    def target_index(tf: Any) -> dict[str, str]:
        if not isinstance(tf, dict) or not tf.get("id"):
            return {}
        fid = str(tf["id"])
        if fid in _FORM_FIELD_TYPE_CACHE:
            return _FORM_FIELD_TYPE_CACHE[fid]
        idx: dict[str, str] = {}
        try:
            app_id = str(tf.get("groupId") or "")
            resp = client.get_form_fields(fid, app_id)
            raw = resp.get("data", []) if isinstance(resp, dict) else []
            # getEbField 返回 {main:[...], detail:[...]} (dict) 或扁平 list
            rows: list[Any] = []
            if isinstance(raw, dict):
                for scope in ("main", "detail"):
                    rows.extend(raw.get(scope) or [])
            elif isinstance(raw, list):
                rows = raw
            for f in rows:
                if isinstance(f, dict) and f.get("id") and f.get("componentKey"):
                    idx[str(f["id"])] = str(f["componentKey"])
        except Exception:
            pass
        _FORM_FIELD_TYPE_CACHE[fid] = idx
        return idx

    def check_mapping(mapping: Any, tf: Any, where: str, *, target_fields: list[dict] | None = None,
                      confirmed: bool = False) -> None:
        if not isinstance(mapping, dict):
            return
        tidx = ({str(field.get("id")): str(field.get("componentKey") or "")
                 for field in target_fields or [] if isinstance(field, dict) and field.get("id")}
                if target_fields is not None else target_index(tf))
        for src_name, tgt in mapping.items():
            # ⚠️ 2026-08-07: mapping value 支持对象 {target,label} (用于 ApproveCreate
            # 让 assign.name=label 显示中文, 而非纯字符串映射时 label=数字 paramKey).
            tgt_id = str(tgt.get("target") or tgt.get("fieldId") or "") if isinstance(tgt, dict) else str(tgt)
            tgt_disp = str(tgt.get("label") or tgt_id) if isinstance(tgt, dict) else tgt_id
            src_ck = src_index.get(str(src_name), "")
            tgt_ck = tidx.get(tgt_id, "")
            sg = _component_group(src_ck)
            tg = _component_group(tgt_ck)
            if not sg or not tg or sg == tg:
                continue
            message = (f"{where}: mapping 字段类型不匹配 — 源「{src_name}」({src_ck})是"
                       f"{_GROUP_LABEL.get(sg, sg)}, 目标字段 {tgt_disp}({tgt_ck})是"
                       f"{_GROUP_LABEL.get(tg, tg)}.")
            if confirmed:
                warnings.append(message + " 用户已确认，继续生成。")
            else:
                errors.append(message + " 已暂停生成；请向用户确认后，在该动作 params 传 confirmTypeMismatch=true。")

    def walk_steps(steps: list[Any], prefix: str) -> None:
        for i, step in enumerate(steps or []):
            p = f"{prefix}[{i}]"
            if not isinstance(step, dict):
                continue
            params = step.get("params") or {}
            tf = params.get("targetForm") if isinstance(params, dict) else None
            if step.get("type") in ("ActionEbAdd", "ActionEbUpdate"):
                check_mapping(params.get("mapping"), tf, f"{p}.mapping",
                              confirmed=bool(params.get("confirmTypeMismatch", False)))
                for di, det in enumerate(params.get("detail") or []):
                    if isinstance(det, dict):
                        # 明细字段不在 targetForm 字段索引里, tidx 查不到会跳过;
                        # 明细表类型校验需 detailTableId 字段查询, 暂不实现.
                        check_mapping(det.get("mapping"), tf, f"{p}.detail[{di}].mapping",
                                      confirmed=bool(params.get("confirmTypeMismatch", False)))
            if step.get("type") == "ApproveCreate":
                biz_fields = params.get("_bizFields") or {}
                main_fields = biz_fields.get("main") if isinstance(biz_fields, dict) else []
                check_mapping(params.get("mapping"), None, f"{p}.mapping", target_fields=main_fields,
                              confirmed=bool(params.get("confirmTypeMismatch", False)))
            if step.get("type") == "Condition":
                for bi, branch in enumerate(step.get("branches") or []):
                    if isinstance(branch, dict):
                        walk_steps(branch.get("actions"), f"{p}.branches[{bi}].actions")

    walk_steps(plan.get("actions"), "actions")


def _check_mapping_identity(plan: dict[str, Any], client, errors: list[str],
                            event_context_fields: list[dict[str, Any]]) -> None:
    """阻止“ID 存在、类型相同，但业务字段取错”的动态赋值。

    类型校验不能区分两个同为关联字段的业务字段。这里同时用本次上下文的
    ``paramKey -> showName`` 和目标表单实时字段名做语义身份检查。名称明显无关
    的映射必须由调用方显式 ``confirmSemanticMismatch=true`` 才能继续；不能悄悄
    暂存一个设计器可显示、但业务含义错误的动作流。
    """
    source_by_key: dict[str, str] = {}
    source_by_name: dict[str, str] = {}
    for field in event_context_fields:
        if not isinstance(field, dict):
            continue
        label = str(field.get("showName") or field.get("paramName") or "")
        key = str(field.get("paramKey") or "")
        if label and key:
            source_by_key[key] = label
            source_by_name.setdefault(label, label)

    # 平台系统字段没有可比的业务名称；它们由 paramKey 表达固定语义。
    system_suffixes = (".requestId", ".rowId", ".id", ".creator", ".createTime", ".updateTime")

    def normalized(value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum())

    def compatible(source: str, target: str) -> bool:
        left, right = normalized(source), normalized(target)
        if not left or not right:
            return True
        if left == right or left in right or right in left:
            return True
        # 中文字段按字符重叠判断；“付款类型 → 款项类型”共享“款/型”，而
        # “付款条件 → 关联合同”没有任何重叠。类型仍由 _check_mapping_types 负责。
        return lcs_len(left, right) * 2 >= min(len(left), len(right))

    def target_fields_for(params: dict[str, Any]) -> dict[str, dict]:
        tf = params.get("targetForm")
        if not isinstance(tf, dict) or not tf.get("id"):
            return {}
        # 直接取接口原始 showName。_get_form_fields_full 会经旧兼容路径转码，
        # 在 Windows 本地 shell 中中文可能失真，不能用于语义比较。
        try:
            response = client.get_form_fields(str(tf["id"]), str(tf.get("groupId") or ""))
            fields = flatten_form_fields_response(response)
        except Exception:
            fields = _get_form_fields_full(str(tf["id"]), client, tf)
        return {str(field.get("id")): field for field in fields
                if isinstance(field, dict) and field.get("id")}

    def check_mapping(mapping: Any, params: dict[str, Any], where: str) -> None:
        if not isinstance(mapping, dict):
            return
        targets = target_fields_for(params)
        if not targets:
            return
        confirmed = bool(params.get("confirmSemanticMismatch", False))
        for source_key, target_ref in mapping.items():
            if isinstance(target_ref, dict) and target_ref.get("systemValue"):
                continue
            target_id = str(target_ref.get("target") or target_ref.get("fieldId") or "") if isinstance(target_ref, dict) else str(target_ref)
            source_param_key = str(target_ref.get("paramKey") or source_key) if isinstance(target_ref, dict) else str(source_key)
            if source_param_key.endswith(system_suffixes):
                continue
            source_label = source_by_key.get(source_param_key) or source_by_name.get(str(source_key), "")
            target_field = targets.get(target_id) or {}
            target_label = str((target_field.get("fieldConfig") or {}).get("title")
                               or target_field.get("showName") or "")
            if not source_label or not target_label or compatible(source_label, target_label):
                continue
            message = (f"{where}: mapping 语义不一致 — 目标「{target_label}」引用了来源「{source_label}」"
                       f"({source_param_key})。请重新选择来源字段；如确为业务明确映射，"
                       "请在该动作 params 设置 confirmSemanticMismatch=true。")
            if not confirmed:
                errors.append(message)

    def walk(steps: list[Any], prefix: str = "actions") -> None:
        for index, step in enumerate(steps or []):
            if not isinstance(step, dict):
                continue
            params = step.get("params") or {}
            path = f"{prefix}[{index}]"
            if step.get("type") in ("ActionEbAdd", "ActionEbUpdate") and isinstance(params, dict):
                check_mapping(params.get("mapping"), params, f"{path}.mapping")
            if step.get("type") == "Condition":
                for branch_index, branch in enumerate(step.get("branches") or []):
                    if isinstance(branch, dict):
                        walk(branch.get("actions") or [], f"{path}.branches[{branch_index}].actions")

    walk(plan.get("actions") or [])


def _register_workflow_detail_meta(event: dict, client) -> None:
    """注册流程明细表**子字段**(_WORKFLOW_DETAIL_FIELDS) 与**真实名称**(_WORKFLOW_DETAIL_NAMES).

    数据源: ApproveTrigger 组件上下文 FormData 组 — 明细表本身条目 paramKey
    '{wfId}.{subFormId}[]' (showName 即真实明细表名, 如 "付款条件"/"采购订单明细"),
    子字段 paramKey '{wfId}.{subFormId}[].{子字段id}'.

    预注册到缓存后, 依据值 basisValueFormula/bassisValue 的 parentName 系列与 main 字段
    allName 能取到**实时真实明细表名**(带流程名前缀), 不依赖 plan 手写 label (曾写错
    "付款条件明细"≠真实"付款条件"). 主表多选字段(采购人员[]/部门选择[])与 ApprovalData
    系统数组(arriveInfo[])不做明细表.

    ⚠️ preflight 与 previewOnly 共用 — previewOnly 分支不跑 _preflight_context, 之前
    previewOnly 生成结果与正式不一致 (依据值名退回 plan label / allName 退回明细表 id).
    """
    _WF_DETAIL = _WORKFLOW_DETAIL_FIELDS
    _WF_DETAIL_NAMES = _WORKFLOW_DETAIL_NAMES
    wf_id = str(event.get("workflowId", "") or "")
    if not wf_id:
        _evp = event.get("params") if isinstance(event.get("params"), dict) else {}
        wf_id = str((_evp.get("workflowPath") or {}).get("id", "") or "")
    if not wf_id or event.get("type") != "ApproveTrigger":
        return
    try:
        r = client.get_component_context("ApproveTrigger", {
            "workflowPath": [{
                "bridgeService": "ebuilder",
                "name": str(event.get("workflowName") or ""),
                "id": wf_id, "workflowtype": "-1",
            }],
            "module": "workflow", "triggerType": "singleApprove",
            "currentApplication": wf_id, "applicationId": wf_id, "type": "ApproveTrigger",
        })
    except Exception:
        return
    for g in r.get("data", []) or []:
        if not isinstance(g, dict) or g.get("primaryKey") != "FormData":
            continue
        for f in (g.get("tableData") or g.get("fields") or []):
            if not isinstance(f, dict):
                continue
            _pk = str(f.get("paramKey") or "")
            _nm = str(f.get("showName") or "")
            if not _nm:
                continue
            if "[]. " in _pk or "[]." in _pk:
                # 明细子字段 → _WORKFLOW_DETAIL_FIELDS[wfId][subFormId][name] = paramKey
                _sf = _pk.rsplit("[]", 1)[0].rsplit(".", 1)[-1]
                if _sf:
                    _WF_DETAIL.setdefault(wf_id, {}).setdefault(_sf, {})[_nm] = _pk
            elif _pk.endswith("[]"):
                # 明细表本身条目 → 名字先登记, 最后清理无子字段的
                _sf = _pk.rsplit(".", 1)[-1].rstrip("[]")
                if _sf.isdigit():
                    _WF_DETAIL_NAMES.setdefault(wf_id, {})[_sf] = _nm
        break
    # 只保留有子字段的明细表 (排除主表多选: 数字 id 但无 []. 子字段)
    for _sf in list(_WF_DETAIL_NAMES.get(wf_id, {})):
        if not _WF_DETAIL.get(wf_id, {}).get(_sf):
            _WF_DETAIL_NAMES.get(wf_id, {}).pop(_sf, None)


def _preflight_context(plan: dict[str, Any], app_id: str, client) -> dict[str, Any]:
    """按拓扑顺序查询真实上下文，禁止未解析引用进入保存阶段。"""
    store = ContextStore()
    provider = PlatformContextProvider(client)
    errors: list[str] = []
    warnings: list[str] = []
    event = plan.get("event", {})
    if not isinstance(event, dict):
        return {"valid": False, "errors": ["event must be an object"], "contextStore": {}}

    _fill_required_trigger_operator(plan, client)
    _resolve_fixed_people(plan, client)

    # 回填 targetForm 缺失的 groupId/name (表单所属应用), 防止生成 groupId=-1
    try:
        unresolved_forms = _resolve_target_forms(plan, client)
        for fid in unresolved_forms:
            errors.append(
                f"targetForm.id='{fid}' 未在平台表单中找到, 无法确定所属应用(groupId). "
                f"请用 form-applications + form-list 确认表单真实存在."
            )
    except Exception:
        pass

    # ConditionSet 的操作符和右值控件由目标字段 componentKey/type 决定。
    # 无论是否存在 mapping，都要在转换前查询并登记实时字段元数据。
    def hydrate_filter_fields(steps: list[Any]) -> None:
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
                        hydrate_filter_fields(branch.get("actions") or [])

    # EventFormData / TimeBatchTrigger / DateTrigger 本身是 event，也可能包含 ConditionSet。
    hydrate_filter_fields([event])
    hydrate_filter_fields(plan.get("actions") or [])

    # 更新动作若无法拿到目标表字段，平台会在 saveDesign 阶段直接 500。
    # 在这里硬拦截，避免保底版误把空字段更新包装成可用结果。
    def validate_update_fields(steps: list[Any], prefix: str = "actions") -> None:
        for index, step in enumerate(steps or []):
            if not isinstance(step, dict):
                continue
            path = f"{prefix}[{index}]"
            if step.get("type") == "ActionEbUpdate":
                target = _step_form_ref(step) or {}
                form_id = str(target.get("id") or "")
                fields = _TARGET_FORM_FIELDS.get(form_id, {}) if form_id else {}
                if not fields:
                    errors.append(
                        f"{path}.targetForm: 未取得目标表单字段，拒绝保存更新动作；"
                        "请确认 form-fields 能返回该表单的字段定义。"
                    )
                    continue
                params = step.get("params") or {}
                for key in ("mapping", "constants"):
                    values = params.get(key) or {}
                    targets = values.values() if key == "mapping" and isinstance(values, dict) \
                        else values.keys() if key == "constants" and isinstance(values, dict) else []
                    for target_id in targets:
                        # mapping 的 value 支持 `+<fieldId>` / `-<fieldId>` 表示累加/扣减；
                        # 这是操作符前缀，不是字段 ID 的一部分。校验必须先剥离，
                        # 否则场景12等合法累加映射会被误判为目标字段不存在。
                        normalized_target_id = str(target_id)
                        if normalized_target_id[:1] in {"+", "-"}:
                            normalized_target_id = normalized_target_id[1:]
                        if isinstance(target_id, dict):
                            normalized_target_id = str(
                                target_id.get("target") or target_id.get("fieldId") or ""
                            )
                            if normalized_target_id[:1] in {"+", "-"}:
                                normalized_target_id = normalized_target_id[1:]
                        if normalized_target_id not in fields:
                            errors.append(
                                f"{path}.params.{key}: 目标字段 '{target_id}' 不属于表单 '{form_id}'。"
                            )
            if step.get("type") == "Condition":
                for branch_index, branch in enumerate(step.get("branches") or []):
                    if isinstance(branch, dict):
                        validate_update_fields(
                            branch.get("actions") or [], f"{path}.branches[{branch_index}].actions"
                        )

    validate_update_fields(plan.get("actions") or [])

    try:
        event_result = _query_node_context(
            event, app_id=app_id, event_node_id="event_1", store=store,
            provider=provider, path="event",
        )
        errors.extend(event_result["errors"])

        # 2026-08-04: 在 event context 被后续 action 覆盖前, 提取流程字段类型
        # (showName → componentKey) 供 mapping 类型校验用. 后续 ActionEbAdd 的
        # component-context 返回同名的 FormData 分组会覆盖 store, 类型信息丢失.
        event_field_types: dict[str, str] = {}
        event_source_fields: list[dict[str, Any]] = []
        # 完整字段集专供动态引用解析。自动映射按显示名去重，但流程主表和
        # 明细表可有同名字段（如“负责人”“付款状态”）；若复用去重结果，明细
        # paramKey 会丢失，赋值芯片只能显示数字 ID。
        event_context_fields: list[dict[str, Any]] = []
        seen_pk: dict[str, int] = {}
        for _k, _v in (event_result.get("context") or {}).items():
            if isinstance(_v, dict) and _v.get("type") == "context_group":
                for _f in _v.get("fields") or []:
                    if not isinstance(_f, dict):
                        continue
                    if _f.get("showName") and _f.get("componentKey"):
                        event_field_types[str(_f["showName"])] = str(_f["componentKey"])
                    if _f.get("showName"):
                        pk = str(_f.get("paramKey") or "")
                        event_context_fields.append(dict(_f))
                        # ⚠️ 2026-08-06 15:40: ApprovalData 组 (流程数据) 字段如 requestId
                        # 没有 componentKey — 之前被过滤 → _WORKFLOW_CONTEXT_FIELDS 缺流程
                        # 数据字段 → type=3 直连 frontId (真实数字 id) 查不到 → 前端把引用
                        # 错归到「表单数据」组 → 参数路径显示数字 paramKey 而非 "采购合同报备.流程ID".
                        # 无 componentKey 的字段也保留 (paramType 兜底), 供 frontId 查询.
                        # 数组字段(paramKey 带 "[]" 后缀, 如 附件/所属部门)与普通字段
                        # 同 showName 出现两遍; 保留带 "[]" 版本 (设计器契约要求),
                        # 避免后写的不带 [] 版本覆盖 (2026-08-04 修复).
                        idx = seen_pk.get(str(_f["showName"]))
                        if idx is None:
                            seen_pk[str(_f["showName"])] = len(event_source_fields)
                            event_source_fields.append({
                                "showName": str(_f.get("showName", "")),
                                "componentKey": str(_f.get("componentKey") or ""),
                                "paramType": str(_f.get("paramType") or "").lower(),
                                "paramKey": pk,
                                "id": str(_f.get("id") or ""),
                            })
                        elif pk.endswith("[]") and not event_source_fields[idx]["paramKey"].endswith("[]"):
                            event_source_fields[idx]["paramKey"] = pk

        # 2026-08-05: event 上下文查询后立即补注册 字段名→id 映射 (component-context paramKey 权威源).
        # 之前只在自动映射路径注册, 显式 mapping 的中文 key 查不到 → paramKey 变中文 → 设计器标"已删除"
        # (模板验证-场景1 的"开始日期"实证). 提前注册让 显式/自动 mapping 都能用.
        _WF_IDS = _WORKFLOW_FIELD_IDS
        _by_wf: dict[str, dict[str, str]] = {}
        for _sf in event_source_fields:
            _pk = str(_sf.get("paramKey") or "")
            if "." in _pk and _sf.get("showName"):
                _head, _, _tail = _pk.rpartition(".")
                _by_wf.setdefault(_head, {})[str(_sf["showName"])] = _tail
        for _wf_id, _wf_map in _by_wf.items():
            if _wf_id and _wf_map:
                _WF_IDS.setdefault(_wf_id, {}).update(_wf_map)

        # ⚠️ 2026-08-05 23:2x: 提取流程明细表子字段 → _WORKFLOW_DETAIL_FIELDS.
        # paramKey 格式 '{wfId}.{明细表id}[].{子字段id}' → subFormId={明细表id}.
        # 供 detail 映射自动按名补全 (方案A) 使用. 之前只登记了主表字段.
        _WF_DETAIL = _WORKFLOW_DETAIL_FIELDS
        _ev_wf_id = str(event.get("workflowId", "") or "")
        if not _ev_wf_id:
            _ev_wf_id = str(((event.get("params") or {}).get("workflowPath") or {}).get("id", "") or "")
        for _sf in event_source_fields:
            _pk = str(_sf.get("paramKey") or "")
            _nm = str(_sf.get("showName") or "")
            if not _nm or ("[]. " not in _pk and "[]." not in _pk):
                continue
            try:
                _subform = _pk.rsplit("[]", 1)[0].rsplit(".", 1)[-1]
            except Exception:
                continue
            if _subform:
                _WF_DETAIL.setdefault(_ev_wf_id, {}).setdefault(_subform, {})[_nm] = _pk

        # ⚠️ 2026-08-07 13:3x: 注册流程明细表**真实名称** → _WORKFLOW_DETAIL_NAMES.
        # 组件上下文 FormData 组里明细表本身条目 paramKey='{wfId}.{subFormId}[]' (无
        # '[].' 子字段后缀), 其 showName 即明细表真实名 (如 "付款条件"/"采购订单明细").
        # 依据值/明细映射的 parentName 系列用它 — plan 手写 label 可能错名
        # ("付款条件明细"≠真实名). ⚠️ 必须**只登记有子字段的明细表** — 主表多选字段
        # (采购人员[]/部门选择[], ck=Employee/Department) 也是 endswith("[]") 形态,
        # 无子字段不能算明细表 (2026-08-07 采购合同申请流程验证发现).
        _WF_DETAIL_NAMES = _WORKFLOW_DETAIL_NAMES
        for _sf in event_source_fields:
            _pk = str(_sf.get("paramKey") or "")
            _nm = str(_sf.get("showName") or "")
            if not _nm or not _pk.endswith("[]") or ("[]. " in _pk or "[]." in _pk):
                continue
            try:
                _head, _, _tail = _pk.rpartition(".")
                _subf = _tail.rstrip("[]")
            except Exception:
                continue
            # 只登记真正的明细表: subFormId 是数字(id) 且在上一步 _WF_DETAIL 里有子字段.
            # isdigit 排除 ApprovalData 组系统字段 (arriveInfo[]/nodeOperator[] 等, 有子
            # 字段但非明细表); 有子字段排除主表多选 (采购人员[]/部门选择[], 数字但无子字段).
            if _head and _subf and _subf.isdigit() and _WF_DETAIL.get(_head, {}).get(_subf):
                _WF_DETAIL_NAMES.setdefault(_head, {})[_subf] = _nm

        # 对 ApproveTrigger: 补充 workflow-fields 作为合法上下文(与 mapping 赋值一致)
        # ⚠️ 2026-08-06 18:5x: 上下文注册扩展到 TimeBatchTrigger/EventFormData —
        # 它们的上下文是 form-context (FormData.{formId}.*, 含系统字段 id/name/creator),
        # 不注册则 _assign_flat_context_direct 的 frontId/ApprovalData 判定缺缓存,
        # FormData 系统字段(componentKey=None)会被误判成 ApprovalData → 数据ID 引用错组.
        if event.get("type") in ("ApproveTrigger", "TimeBatchTrigger", "EventFormData", "DateTrigger"):
            workflow_path = event.get("workflowPath", {})
            if isinstance(event.get("params"), dict):
                workflow_path = event["params"].get("workflowPath", workflow_path)
            workflow_id = str(event.get("workflowId", "") or workflow_path.get("id", ""))
            if not workflow_id:
                # 数据触发/定时批量触发: 用表单 id 作上下文 key (form-context)
                ev_params = event.get("params") or {}
                _ds = ev_params.get("dataSource") or {}
                _ds_id = str(_ds.get("id") or "") if isinstance(_ds, dict) else ""
                if not _ds_id:
                    _tf = ev_params.get("targetForm") or {}
                    _ds_id = str(_tf.get("id") or "") if isinstance(_tf, dict) else ""
                workflow_id = _ds_id
            if workflow_id:
                register_workflow_context_fields(workflow_id, event_context_fields)
                # workflow-fields 的 targetTableId 只需合法 formId; 优先取 plan 中
                # 已填的目标表单(更相关), 否则才查应用下第一个表单, 结果进程内缓存.
                fid = _FORM_ID_CACHE.get(workflow_id, "")
                if not fid:
                    for s in plan.get("actions", []):
                        tp = s.get("params", {}).get("targetForm", {}) if isinstance(s.get("params"), dict) else {}
                        if isinstance(tp, dict) and tp.get("id"):
                            fid = str(tp["id"])
                            break
                if not fid:
                    try:
                        apps = client.list_apps()
                        apps_data = apps.get("data", []) if isinstance(apps, dict) else []
                        first_app = (apps_data[0] if isinstance(apps_data, list) and apps_data
                                     else {}).get("id", "")
                        if first_app:
                            forms = client.list_forms(str(first_app))
                            forms_data = forms.get("data", []) if isinstance(forms, dict) else []
                            first_form = (forms_data[0] if isinstance(forms_data, list) and forms_data
                                          else {}).get("id", "")
                            if first_form:
                                fid = str(first_form)
                    except Exception:
                        pass
                if fid:
                    _FORM_ID_CACHE[workflow_id] = fid
                    try:
                        wf_fields = client.get_workflow_fields(str(workflow_id), str(fid))
                        if isinstance(wf_fields, dict) and isinstance(wf_fields.get("data"), list):
                            register_workflow_field_ids(str(workflow_id), wf_fields["data"])
                            for f in wf_fields["data"]:
                                if isinstance(f, dict) and f.get("name"):
                                    field_id = str(f.get("id", f.get("fieldId", "")))
                                    # workflow-fields 接口的精简返回只有 id/name；
                                    # 回退时也必须构造真实数字 paramKey，不能把中文名称
                                    # 写入 setting.main，否则设计器会显示“已删除”。
                                    param_key = str(f.get("paramKey") or (
                                        f"{workflow_id}.{field_id}" if field_id else f["name"]
                                    ))
                                    store.merge({f["name"]: {"paramKey": param_key}}, "workflow-fields")
                    except Exception:
                        pass

        # 显式 mapping 也必须带实时显示名。计划可只传 paramKey（便于机器生成），
        # 但设计器 FormulaBean 的 name 不能是数字/paramKey；同名主表与明细字段
        # 则按完整 paramKey 精确匹配，不能回退到按名称去重的自动映射索引。
        label_by_param_key = {
            str(field.get("paramKey")): str(field.get("showName") or field.get("paramName") or "")
            for field in event_context_fields
            if isinstance(field, dict) and field.get("paramKey")
        }

        def hydrate_mapping_labels(steps: list[Any]) -> None:
            for step in steps or []:
                if not isinstance(step, dict):
                    continue
                params = step.get("params") or {}
                mapping = params.get("mapping") if isinstance(params, dict) else None
                if isinstance(mapping, dict):
                    for source_key, target in list(mapping.items()):
                        label = label_by_param_key.get(str(source_key), "")
                        if not label:
                            continue
                        if isinstance(target, dict):
                            target.setdefault("paramKey", str(source_key))
                            target.setdefault("label", label)
                        else:
                            mapping[source_key] = {
                                "target": str(target), "paramKey": str(source_key), "label": label,
                            }
                # 明细映射同样是上下文字段引用。若不注入实时 label，转换器只能
                # 把完整 paramKey 当显示名，设计器会显示数字 ID 或错分作用域。
                for detail in params.get("detail") or []:
                    if not isinstance(detail, dict) or not isinstance(detail.get("mapping"), dict):
                        continue
                    detail_mapping = detail["mapping"]
                    for source_key, target in list(detail_mapping.items()):
                        source_param_key = (str(target.get("paramKey") or source_key)
                                            if isinstance(target, dict) else str(source_key))
                        label = label_by_param_key.get(source_param_key, "")
                        if not label:
                            continue
                        if isinstance(target, dict):
                            target.setdefault("paramKey", source_param_key)
                            target.setdefault("label", label)
                        else:
                            detail_mapping[source_key] = {
                                "target": str(target), "paramKey": source_param_key, "label": label,
                            }
                if step.get("type") == "Condition":
                    for branch in step.get("branches") or []:
                        if isinstance(branch, dict):
                            hydrate_mapping_labels(branch.get("actions") or [])

        hydrate_mapping_labels(plan.get("actions") or [])

        if errors:
            return {"valid": False, "errors": errors, "contextStore": store.as_dict()}

        def walk(steps: list[dict[str, Any]], branch_store: ContextStore, prefix: str) -> None:
            for index, step in enumerate(steps):
                path = f"{prefix}[{index}]"
                result = _query_node_context(
                    step, app_id=app_id, event_node_id="event_1", store=branch_store,
                    provider=provider, path=path,
                )
                errors.extend(result["errors"])
                if result["errors"]:
                    return
                if step.get("type") == "Condition":
                    # 分支输出不会在汇合点自动成为主链上下文，分别校验即可。
                    for branch_index, branch in enumerate(step.get("branches", [])):
                        if isinstance(branch, dict):
                            child_store = ContextStore(branch_store.as_dict())
                            walk(branch.get("actions", []), child_store, f"{path}.branches[{branch_index}].actions")
                elif step.get("type") == "ApproveCreate":
                    # 新建流程: 调 getWfField 拿目标流程真实字段, 注入 plan 供转换用.
                    # 平台保存 ApproveCreate 需要 fields (目标流程表单字段结构),
                    # 缺失会导致"初始化组件失败".
                    _resolve_biz_create_fields(step, plan, client, errors, path)

        walk(plan.get("actions", []), store, "actions")

        # ── 自动映射 (2026-08-04 用户要求): 用户没指定 mapping 时, 用平台
        # 自动映射逻辑 (set-formdata → field-map getDefaultData) 补全 plan.
        # 在类型校验之前执行, 补全的 mapping 同样过 _check_mapping_types.
        _auto_map_missing_mappings(plan, client, event_source_fields)

        # ── mapping 类型兼容校验 (2026-08-04): 源/目标字段 componentKey 必须同组 ──
        # 拦截"请假原因(TextArea)→单行文本(Text)"类错误, 不依赖模型自觉.
        _check_mapping_types(plan, store, client, errors, event_field_types, warnings)
        _check_mapping_identity(plan, client, errors, event_context_fields)
        if errors:
            return {"valid": False, "errors": errors, "warnings": warnings,
                    "contextStore": store.as_dict()}
    except ContextUnavailableError as exc:
        errors.append(str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"context preflight failed: {exc}")

    return {"valid": not errors, "errors": errors, "contextStore": store.as_dict(),
            "autoMappings": plan.get("_autoMappings", []),
            "autoResources": plan.get("_autoResources", [])}


def _sync_auto_mappings_to_draft(draft: dict[str, Any], plan: dict[str, Any]) -> None:
    """把 preflight 规范化后的 mapping 同步到 compile 产物 draft.

    preflight 的 _auto_map_missing_mappings 修改的是 plan (mapping 空 → 自动补全),
    而 convert 消费的是 compile_workflow_draft 的产物 draft — 必须把自动生成的
    mapping 同步过去, 否则设计里仍是空映射. 显式 mapping 也会在预检中补齐
    实时 ``label``，因此不能只同步原本为空的 mapping。
    """
    plan_actions = plan.get("actions", []) if isinstance(plan, dict) else []
    draft_actions = draft.get("actions", []) if isinstance(draft, dict) else []
    for p_action, d_action in zip(plan_actions, draft_actions):
        if not isinstance(p_action, dict) or not isinstance(d_action, dict):
            continue
        p_params = p_action.get("params", {})
        d_params = d_action.get("params", {})
        if not isinstance(p_params, dict) or not isinstance(d_params, dict):
            continue
        p_mapping = p_params.get("mapping")
        d_mapping = d_params.get("mapping")
        if p_mapping:
            d_params["mapping"] = p_mapping


def _sync_form_references_to_draft(draft: dict[str, Any], plan: dict[str, Any]) -> None:
    """Copy real-time-resolved form references from plan into the compiled draft.

    Compilation intentionally precedes preflight.  Therefore a targetForm that
    was supplied as only ``groupId/id`` must be synchronized after preflight,
    otherwise conversion receives the old partial reference and emits an empty
    designer selector despite a successful lookup.
    """
    def sync_step(plan_step: Any, draft_step: Any) -> None:
        if not isinstance(plan_step, dict) or not isinstance(draft_step, dict):
            return
        plan_params = plan_step.get("params")
        draft_params = draft_step.get("params")
        if isinstance(plan_params, dict) and isinstance(draft_params, dict):
            for key in ("targetForm", "dataSource"):
                ref = plan_params.get(key)
                if isinstance(ref, dict) and ref.get("id"):
                    draft_params[key] = deepcopy(ref)
        plan_branches = plan_step.get("branches")
        draft_branches = draft_step.get("branches")
        if isinstance(plan_branches, list) and isinstance(draft_branches, list):
            for plan_branch, draft_branch in zip(plan_branches, draft_branches):
                if not isinstance(plan_branch, dict) or not isinstance(draft_branch, dict):
                    continue
                for plan_action, draft_action in zip(
                        plan_branch.get("actions") or [], draft_branch.get("actions") or []):
                    sync_step(plan_action, draft_action)

    sync_step(plan.get("event"), draft.get("event"))
    for plan_action, draft_action in zip(plan.get("actions") or [], draft.get("actions") or []):
        sync_step(plan_action, draft_action)


def _sync_event_resources_to_draft(draft: dict[str, Any], plan: dict[str, Any]) -> None:
    """同步预检阶段补齐的触发器资源到已编译 draft。"""
    plan_event = plan.get("event", {}) if isinstance(plan, dict) else {}
    draft_event = draft.get("event", {}) if isinstance(draft, dict) else {}
    if not isinstance(plan_event, dict) or not isinstance(draft_event, dict):
        return
    plan_params = plan_event.get("params", {})
    draft_params = draft_event.get("params", {})
    if not isinstance(plan_params, dict) or not isinstance(draft_params, dict):
        return
    if plan_event.get("type") in {"DateTrigger", "TimeBatchTrigger"} and plan_params.get("operator"):
        draft_params["operator"] = plan_params["operator"]


def _sync_fixed_people_to_draft(draft: dict[str, Any], plan: dict[str, Any]) -> None:
    """同步预检补全的固定人员 Browser 对象到已编译 draft。

    编译在预检之前完成。若只更新 semantic plan，转换器仍会消费旧的
    ``{id,name}``，暂存回读就会丢掉 Browser 的 avatar/department 等字段。
    只同步固定人员参数；上下文动态引用不在此路径上，保持原结构不被改写。
    """
    person_keys = {
        "MeetingCreate": ("caller", "contacter", "hrmMembers"),
        "ScheduleCreate": ("creatorUser", "manager", "participants", "sharedUsers"),
        "ApproveCreate": ("operator",),
    }
    plan_actions = plan.get("actions", []) if isinstance(plan, dict) else []
    draft_actions = draft.get("actions", []) if isinstance(draft, dict) else []
    for plan_action, draft_action in zip(plan_actions, draft_actions):
        if not isinstance(plan_action, dict) or not isinstance(draft_action, dict):
            continue
        keys = person_keys.get(str(plan_action.get("type") or ""), ())
        if not keys:
            continue
        plan_params = plan_action.get("params", {})
        draft_params = draft_action.get("params", {})
        if not isinstance(plan_params, dict) or not isinstance(draft_params, dict):
            continue
        containers = [(plan_params, draft_params)]
        plan_fields = plan_params.get("meetingFields")
        draft_fields = draft_params.get("meetingFields")
        if isinstance(plan_fields, dict) and isinstance(draft_fields, dict):
            containers.append((plan_fields, draft_fields))
        for plan_container, draft_container in containers:
            for key in keys:
                value = plan_container.get(key)
                if value is None:
                    continue
                values = value if isinstance(value, list) else [value]
                if values and all(_is_browser_person(item) for item in values):
                    draft_container[key] = value


def _sync_biz_fields_to_draft(draft: dict[str, Any], plan: dict[str, Any]) -> None:
    """把 preflight 注入 plan 的 ApproveCreate._bizFields 同步到 compile 产物 draft."""
    plan_actions = plan.get("actions", []) if isinstance(plan, dict) else []
    draft_actions = draft.get("actions", []) if isinstance(draft, dict) else []
    for p_action, d_action in zip(plan_actions, draft_actions):
        if not isinstance(p_action, dict) or not isinstance(d_action, dict):
            continue
        if p_action.get("type") != "ApproveCreate":
            continue
        p_params = p_action.get("params", {})
        if not isinstance(p_params, dict) or not p_params.get("_bizFields"):
            continue
        d_params = d_action.setdefault("params", {})
        if isinstance(d_params, dict):
            d_params["_bizFields"] = p_params["_bizFields"]


def _resolve_biz_create_fields(step: dict[str, Any], plan: dict[str, Any],
                               client, errors: list[str], path: str) -> None:
    """ApproveCreate 新建流程: 调 getWfField 拿目标流程真实表单字段.

    平台保存 ApproveCreate 时 fields 必须含目标流程的表单字段结构
    ({main:[{id,showName,componentKey,formId,...}], detail:[]}), 否则
    saveDesign 报"初始化组件失败". 查询结果注入 plan (step.params._bizFields),
    转换阶段据此生成 fields + 校验 mapping 目标字段.
    """
    params = step.get("params", {}) if isinstance(step, dict) else {}
    wf_path = params.get("workflowPath", {}) if isinstance(params, dict) else {}
    wf_id = str(wf_path.get("id", wf_path.get("createFlowId", ""))) if isinstance(wf_path, dict) else ""
    if not wf_id:
        errors.append(f"{path}.params.workflowPath.id 缺失 (新建流程必须指定目标流程)")
        return
    try:
        resp = client._request("/api/bs/esb/setting/component/getWfField", method="GET",
                               query={"wfid": wf_id, "module": "workflow"})
        data = resp.get("data", {})
        if resp.get("code") == 200:
            # 不同租户/版本会返回 {main,detail} 或直接 main 数组；统一处理，
            # 不能只依赖当前测试租户的对象形状。
            if isinstance(data, list):
                data = {"main": data, "detail": []}
            if isinstance(data, dict):
                main = data.get("main", [])
                if not isinstance(main, list):
                    main = []
                biz_fields = {
                    "main": [{"id": str(f.get("id", "")), "showName": str(f.get("showName", "")),
                              "componentKey": str(f.get("componentKey", "")),
                              "formId": str(f.get("formId", "")), "required": bool(f.get("required", False)),
                              "custom": bool(f.get("custom", False)), "subFormId": str(f.get("subFormId", "-1"))}
                             for f in main if isinstance(f, dict)],
                    "detail": data.get("detail", []) or [],
                }
                params["_bizFields"] = biz_fields
                # ApproveCreate 保存要求 workflowPath.formIds。流程浏览接口在
                # 部分租户不返回该字段，但 getWfField 的目标主表字段自带 formId；
                # 这里实时回填，避免跨环境生成出 formIds=[] 的无效动作。
                raw_form_ids = wf_path.get("formIds")
                if isinstance(raw_form_ids, (str, int)):
                    raw_form_ids = [raw_form_ids]
                form_ids = [str(x) for x in (raw_form_ids or []) if x]
                if not form_ids:
                    form_ids = list(dict.fromkeys(
                        str(f.get("formId", "")) for f in main
                        if isinstance(f, dict) and f.get("formId")
                    ))
                    if form_ids:
                        wf_path["formIds"] = form_ids
                if not form_ids:
                    errors.append(
                        f"{path}.params.workflowPath.formIds 缺失: getWfField 未返回目标流程主表 formId，"
                        "无法安全保存新建流程；请确认目标流程已绑定表单。"
                    )
                # ⚠️ 2026-08-07 15:59 修复: 校验**必须覆盖 detail 明细字段** —
                # 之前只校验 main (1281 行), 明细 target id 猜错/推算 (如采购总价
                # 按 +1 推) 会直接通过预检保存成功, 设计器明细字段"请选择".
                # detail 结构: [{fields: [{id, showName,...}]}] → 收集全部子字段 id.
                _all_field_ids = {str(f["id"]) for f in biz_fields["main"]}
                for _dt in biz_fields["detail"]:
                    if isinstance(_dt, dict):
                        for _df in (_dt.get("fields") or []):
                            if isinstance(_df, dict) and _df.get("id"):
                                _all_field_ids.add(str(_df["id"]))
                # 校验 mapping (main) 目标字段存在
                mapping = params.get("mapping", {})
                if isinstance(mapping, dict):
                    for src_key, target_fid in mapping.items():
                        # ⚠️ 2026-08-07: 支持对象 {target,label} (label 作 assign.name 中文显示)
                        _tid = str(target_fid.get("target") or target_fid.get("fieldId") or "") if isinstance(target_fid, dict) else str(target_fid)
                        if _tid and _tid not in _all_field_ids:
                            errors.append(
                                f"{path}.params.mapping['{src_key}'] 目标字段 '{target_fid}' "
                                f"不存在于目标流程 '{wf_id}' 的表单字段中"
                            )
                # 固定值以“目标字段 id → 值”表达，和 mapping 一样必须来自
                # getWfField 的实时字段清单；否则设计器会留下不可见字段或保存后丢值。
                constants = params.get("constants", {})
                if isinstance(constants, dict):
                    for target_fid in constants:
                        if str(target_fid) not in _all_field_ids:
                            errors.append(
                                f"{path}.params.constants['{target_fid}'] 目标字段不存在于目标流程 "
                                f"'{wf_id}' 的表单字段中"
                            )
                # 动态映射和固定值同时写同一个字段时，后写者会静默覆盖前写者。
                # 这是业务歧义，不允许以任意顺序“猜”一个值。
                if isinstance(mapping, dict) and isinstance(constants, dict):
                    mapped_targets = {
                        str(value.get("target") or value.get("fieldId") or "")
                        if isinstance(value, dict) else str(value)
                        for value in mapping.values()
                    }
                    collisions = sorted(fid for fid in mapped_targets if fid and fid in constants)
                    if collisions:
                        errors.append(
                            f"{path}.params.mapping 与 constants 同时设置目标字段 {collisions}；"
                            "请保留其中一种赋值方式。"
                        )
                # ⚠️ 2026-08-07 15:59: 校验 detail[].mapping 的目标字段 (明细表子字段)
                for _di, _ditem in enumerate(params.get("detail") or []):
                    if not isinstance(_ditem, dict):
                        continue
                    _dm = _ditem.get("mapping") or {}
                    if not isinstance(_dm, dict):
                        continue
                    for _sk, _tv in _dm.items():
                        _tid2 = str(_tv.get("target") or _tv.get("fieldId") or "") if isinstance(_tv, dict) else str(_tv)
                        if _tid2 and _tid2 not in _all_field_ids:
                            errors.append(
                                f"{path}.params.detail[{_di}].mapping['{_sk}'] 目标字段 '{_tid2}' "
                                f"不存在于目标流程 '{wf_id}' 的表单字段中 (明细表子字段 id 必须实时查全量, 禁止推算)"
                            )
    except Exception as exc:
        errors.append(f"{path}: getWfField 查询目标流程字段失败: {exc}")


# ── Condition 两步法: saveCondition 拿 server 分配的 conditionDataJson ──────

_OPERATOR_MAP = {
    "nempty": ("97", "14"), "isnotnull": ("97", "14"), "不为空": ("97", "14"),   # 不为空
    "empty": ("97", "13"), "isnull": ("97", "13"), "为空": ("97", "13"),        # 为空
    "eq": ("97", "5"), "equals": ("97", "5"), "等于": ("97", "5"),              # 等于
    "neq": ("97", "6"), "notequals": ("97", "6"), "不等于": ("97", "6"),        # 不等于
    "contains": ("97", "9"), "包含": ("97", "9"),                               # 包含
    "notcontains": ("97", "10"), "notcontain": ("97", "10"), "不包含": ("97", "10"),  # 不包含
    "in": ("97", "11"), "属于": ("97", "11"),                                   # 属于(in)
    "notin": ("97", "12"), "不属于": ("97", "12"),                              # 不属于(notin)
    "gt": ("4", "1"), "greaterthan": ("4", "1"), "大于": ("4", "1"),            # 大于
    "lt": ("4", "3"), "lessthan": ("4", "3"), "小于": ("4", "3"),               # 小于
    "gte": ("4", "2"), "ge": ("4", "2"), "大于等于": ("4", "2"),                # 大于等于
    "lte": ("4", "4"), "le": ("4", "4"), "小于等于": ("4", "4"),                # 小于等于
}
