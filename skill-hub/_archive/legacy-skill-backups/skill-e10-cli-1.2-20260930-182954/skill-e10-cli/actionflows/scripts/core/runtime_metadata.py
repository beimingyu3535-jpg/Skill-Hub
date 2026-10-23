"""本轮转换使用的表单、流程和上下文字段元数据。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def find_in_metadata(meta: dict, collection: str, draft_ref: dict) -> dict | None:
    """按 id 或名称查找当前轮元数据中的对象。"""
    items = meta.get(collection, [])
    rid, rname = draft_ref.get("id", ""), draft_ref.get("name", "")
    for item in items:
        if rid and item.get("id") == rid:
            return item
        if rname and item.get("name") == rname:
            return item
    return None

# 中文 paramKey 会被设计器标记"已删除".generate 预检时调用 register_workflow_field_ids
# 把 workflow-fields 查询结果登记到这里,转换器生成 paramKey/value 时替换为 id 格式.
_WORKFLOW_FIELD_IDS: dict[str, dict[str, str]] = {}
# ConditionSet 不能只靠字段 id 推断控件。前端会按 componentKey/type 决定
# 操作符与右值编辑器，因此保存前把本轮实时接口返回的字段元数据登记到这里。
_TARGET_FORM_FIELDS: dict[str, dict[str, dict[str, Any]]] = {}
_WORKFLOW_CONTEXT_FIELDS: dict[str, dict[str, dict[str, Any]]] = {}
# 按完整 paramKey 建索引，避免主表/明细表同名字段在动态赋值解析时互相覆盖。
_WORKFLOW_CONTEXT_FIELDS_BY_KEY: dict[str, dict[str, dict[str, Any]]] = {}
#  自动按名补全 detail 映射的数据源.
# 目标表单明细表字段: formId → {detailTableId: {fieldId: {name, showName, componentKey}}}
_TARGET_DETAIL_FIELDS: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
# 流程明细表子字段: workflowId → {subFormId: {字段名: paramKey('{wfId}.{明细表id}[].{子字段id}')}}
_WORKFLOW_DETAIL_FIELDS: dict[str, dict[str, dict[str, str]]] = {}
#  流程明细表**真实名称**: {wfId} → {subFormId: showName}.
# (如 "付款条件"). 依据值 basisValueFormula/bassisValue 与 main 字段 allName 的
# parentName 系列用它 — plan 手写 label 可能错 ("付款条件明细"≠真实"付款条件").
_WORKFLOW_DETAIL_NAMES: dict[str, dict[str, str]] = {}

def register_workflow_field_ids(workflow_id: str, fields: list) -> None:
    """登记 workflow-fields 查询结果: workflowId → {name: id}."""
    if not workflow_id:
        return
    mapping = _WORKFLOW_FIELD_IDS.setdefault(str(workflow_id), {})
    for f in fields or []:
        if not isinstance(f, dict):
            continue
        fname = f.get("name")
        fid = f.get("id")
        if fname and fid:
            mapping[str(fname)] = str(fid)

def register_target_form_fields(form_id: str, fields: list) -> None:
    """登记 getEbField 的实时字段元数据，供 ConditionSet 精确还原控件类型。"""
    if not form_id:
        return
    index = _TARGET_FORM_FIELDS.setdefault(str(form_id), {})
    for field in fields or []:
        if not isinstance(field, dict) or not field.get("id"):
            continue
        normalized = deepcopy(field)
        normalized["id"] = str(field["id"])
        normalized.setdefault("name", field.get("showName", ""))
        normalized.setdefault("showName", field.get("name", ""))
        index[normalized["id"]] = normalized

def register_workflow_context_fields(workflow_id: str, fields: list) -> None:
    """登记触发器上下文字段，保留真实 paramKey/componentKey/paramType。"""
    if not workflow_id:
        return
    index = _WORKFLOW_CONTEXT_FIELDS.setdefault(str(workflow_id), {})
    key_index = _WORKFLOW_CONTEXT_FIELDS_BY_KEY.setdefault(str(workflow_id), {})
    for field in fields or []:
        if not isinstance(field, dict):
            continue
        name = str(field.get("showName") or field.get("name") or "")
        param_key = str(field.get("paramKey") or "")
        if not name:
            continue
        normalized = deepcopy(field)
        normalized["showName"] = name
        normalized["paramKey"] = param_key
        if param_key:
            key_index[param_key] = normalized
        # 同名普通/数组字段并存时保留数组版本；ConditionSet 的“属于”依赖它。
        old = index.get(name, {})
        if not old or (param_key.endswith("[]") and not str(old.get("paramKey", "")).endswith("[]")):
            index[name] = normalized

def workflow_field_id(workflow_id: str, field_name: str) -> str:
    """把中文字段名映射为字段 id;查不到返回原名(兼容).

     增强: 若 field_name 本身就是 "{workflowId}.{fieldId}" 数字格式
    (component-context 的 paramKey), 直接取后半段 fieldId, 避免中文 paramKey
    被设计器标"已删除". 自动映射注入的 mapping key 是源字段名, 转换器先经
    register_workflow_field_ids 注册的缓存查找, 缓存缺失时才走 paramKey 兜底.
    """
    cache = _WORKFLOW_FIELD_IDS.get(str(workflow_id), {})
    hit = cache.get(str(field_name))
    if hit:
        return str(hit)
    #: 依据值下级 paramKey 格式 '{明细表id}[].{子字段id}' (batchInsert/明细映射)
    if "[]. " in str(field_name) or "[]." in str(field_name):
        return str(field_name)
    if "." in str(field_name):
        parts = str(field_name).split(".")
        if len(parts) == 2 and parts[1].isdigit():
            return parts[1]
    return str(field_name)

#  **设计器右侧"字段类型"列就是 component-context 返回的
# paramType 渲染的** (string→文本 / datetime→日期时间 / json→JSON 等)。
# 用户明确: 会议负责人字段在设计器里就是"文本" (component-context paramType=string),
