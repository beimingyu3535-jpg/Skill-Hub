"""EnquiryForm 组件的专用平台 DTO 转换。"""
from __future__ import annotations

from copy import deepcopy
import json

def CONVERTER(draft_params: dict, *, meta=None, app_id: str = "", **_kwargs) -> dict:
    """构造数据源、筛选、查询字段与人员公式的真实结构。"""
    # 延迟导入避免注册发现循环。
    from core.draft_to_real import _build_filter_input
    from core.formula_service import build_person_formula
    from core.id_generator import gen_id

    result: dict = {}
    data_source = draft_params.get("dataSource") or {}
    if not isinstance(data_source, dict):
        data_source = {}
    source_id = str(data_source.get("id") or data_source.get("tableId") or data_source.get("sourceId", ""))
    source_text = str(data_source.get("text") or data_source.get("name") or "")
    group_id = str(data_source.get("groupId", data_source.get("appId", "-98")))
    source_type = str(data_source.get("type", "FORM"))
    op_type = str(data_source.get("opType", draft_params.get("opType", "list")))
    result["dataSource"] = {
        "sourceId": source_id,
        "isPhysical": True,
        "peratorId": str(data_source.get("peratorId", "")),
        "authorityFlag": data_source.get("authorityFlag", "0"),
        "groupId": group_id,
        "opType": op_type,
        "type": source_type,
        "id": source_id,
        "enquiryId": str(draft_params.get("enquiryId", "-1")),
        "text": source_text,
        "usage": str(data_source.get("usage", "")),
        "objType": str(data_source.get("objType", "")),
        "module": str(data_source.get("module", "")),
        "appId": str(data_source.get("appId", group_id)),
        "ebuilderDataConfig": {
            "dataSetup": {"dataSource": "ALL", "dataPermission": "HAVE_PERMISSION_DATA"},
            "type": source_type,
        },
    }
    filter_input = _build_filter_input(
        result, draft_params.get("filter", []), meta, app_id, component_type="EnquiryForm")
    result["filterInput"] = filter_input
    try:
        result["dataSource"]["opText"] = json.dumps(filter_input, ensure_ascii=False)
    except (TypeError, ValueError):
        result["dataSource"]["opText"] = ""

    result["queryFields"] = []
    for field in draft_params.get("queryFields", []) or []:
        if isinstance(field, dict) and field.get("id"):
            result["queryFields"].append({
                "formId": str(field.get("formId", source_id)),
                "parseMark": bool(field.get("parseMark", False)),
                "id": str(field["id"]),
                "content": str(field.get("content", field.get("id"))),
            })

    person = draft_params.get("person")
    if isinstance(person, dict):
        result["person"] = build_person_formula(person, meta, app_id, direct_person=True)
    else:
        result["person"] = build_person_formula(
            {"type": "user", "id": "", "name": ""}, meta, app_id, direct_person=True)
    result.update({
        "opType": str(draft_params.get("opType", "list")),
        "countFlag": bool(draft_params.get("countFlag", False)),
        "nodataFlag": bool(draft_params.get("nodataFlag", True)),
        "parseMark": bool(draft_params.get("parseMark", True)),
        "authorityFlag": str(draft_params.get("authorityFlag", "0")),
        "id": str(gen_id()),
    })
    for key in ("orderFields", "formPageNo", "formPageSize", "groupFields", "groupMessage"):
        if draft_params.get(key) not in (None, "", []):
            result[key] = deepcopy(draft_params[key])
    if app_id:
        result["currentApplication"] = app_id
        result["applicationId"] = app_id
    return result
