"""更新表单数据的公式引用与字段条件转换。"""
from __future__ import annotations

from copy import deepcopy

from core.formula_service import _assign_flat_context_direct, _resolve_param_key, formula_context, formula_fixed
from core.id_generator import gen_id


def build_formula_reference(value, *, meta: dict | None = None, app_id: str = "",
                            event_id: str = "", component_type: str = "") -> dict:
    """把更新动作的 ID/依据值语义赋值转为后端 FormulaBean。"""
    if isinstance(value, dict) and (value.get("type") or value.get("formulaType")) and not value.get("kind"):
        return deepcopy(value)
    if isinstance(value, dict):
        kind = value.get("kind") or value.get("assignmentKind")
        if kind in ("context", "reference") or value.get("key"):
            key = str(value.get("paramKey") or value.get("key") or value.get("fieldKey") or "")
            if not key:
                raise ValueError("ActionEbUpdate 公式引用缺少 key/paramKey")
            wf_id = str((meta or {}).get("_workflow_id", ""))
            resolved_key = _resolve_param_key(wf_id, key)
            return formula_context(
                str(event_id or value.get("source") or "0"), resolved_key,
                name=str(value.get("label") or value.get("name") or key),
                business_id=str(app_id or value.get("businessId") or "0"),
                component_type=component_type or "ApproveTrigger",
                field_type=str(value.get("fieldType") or value.get("valueType") or "string"),
            )
        if kind in ("fixed", "literal") or "value" in value:
            return formula_fixed(value.get("value", ""), str(value.get("valueType") or "string"))
    if isinstance(value, (str, int, float, bool)):
        return formula_fixed(value)
    raise ValueError("ActionEbUpdate 公式引用必须是 FormulaBean、fixed 或 context")


def build_update_field_condition(value, *, meta: dict | None = None, app_id: str = "",
                                 event_id: str = "", component_type: str = "") -> dict:
    """转换 common/update-field 的真实 updateField 行结构。"""
    if not isinstance(value, dict):
        raise ValueError("ActionEbUpdate.updateFieldCondition 必须是对象")
    raw_items = value.get("updateField", [])
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("ActionEbUpdate.fieldUpdate 至少需要一个 updateField 条件")
    items = []
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict) or not raw.get("fieldKey"):
            raise ValueError(f"ActionEbUpdate.updateFieldCondition.updateField[{index}] 缺少 fieldKey")
        item = deepcopy(raw)
        item_id = str(item.get("id") or gen_id())
        item["id"] = item_id
        item.setdefault("primaryId", item_id)
        item.setdefault("original", False)
        item.setdefault("operate", "OPERATE_EQUAL")
        item.setdefault("fieldSet", {})
        item.setdefault("assignType", "")
        item.setdefault("multiSelect", False)
        assignment = item.get("assign", item.get("value"))
        if assignment is None:
            raise ValueError(f"ActionEbUpdate.updateFieldCondition.updateField[{index}] 缺少 assign")
        if not (isinstance(assignment, dict) and (assignment.get("type") or assignment.get("formulaType")) and not assignment.get("kind")):
            wf_id = str((meta or {}).get("_workflow_id", ""))
            src_id = str(event_id or (assignment.get("source") if isinstance(assignment, dict) else ""))
            if isinstance(assignment, dict) and (assignment.get("kind") == "context" or assignment.get("key") or assignment.get("paramKey")):
                key = str(assignment.get("paramKey") or assignment.get("key") or assignment.get("fieldKey") or "")
                resolved = _resolve_param_key(wf_id, key)
                label = str(assignment.get("label") or assignment.get("name") or key)
                wf_name = str((meta or {}).get("_upstream_workflow_name", ""))
                assignment = _assign_flat_context_direct(
                    resolved, label, src_id, app_id, parent_name=f"{wf_name}.{label}" if wf_name else label, meta=meta,
                )
            else:
                assignment = build_formula_reference(
                    assignment, meta=meta, app_id=app_id, event_id=event_id, component_type=component_type,
                )
        item["assign"] = assignment
        item.setdefault("assignId", str(assignment.get("id") or gen_id()))
        item.setdefault("switchType", "fixvalue" if assignment.get("type") == "1" else "assign")
        item.setdefault("fieldType", "Text")
        items.append(item)
    return {"id": str(value.get("id") or gen_id()), "updateField": items,
            "deleteFieldIds": list(value.get("deleteFieldIds") or [])}
