"""条件筛选的字段类型、操作符和右值公式规则。"""
from __future__ import annotations

import json
from typing import Any

from core.formula_service import (
    _make_config_obj,
    _resolve_param_key,
    _resolve_source_field_label,
    _resolve_source_field_type,
    formula_context,
    formula_fixed,
)
from core.id_generator import gen_id
from core.runtime_metadata import (
    _TARGET_FORM_FIELDS,
    _WORKFLOW_CONTEXT_FIELDS,
    find_in_metadata,
    workflow_field_id,
)

_FILTER_OPERATOR_MAP = {
    "eq": "eq", "==": "eq", "=": "eq",
    "neq": "unEqual", "ne": "unEqual", "!=": "unEqual",
    "gt": "greaterThan", ">": "greaterThan",
    "gte": "equalGreaterThan", ">=": "equalGreaterThan",
    "lt": "lessThan", "<": "lessThan",
    "lte": "equalLessThan", "<=": "equalLessThan",
    "contains": "contain", "include": "contain",
    "notcontains": "unContain", "exclude": "unContain",
    "empty": "empty", "isnull": "empty",
    "notempty": "nempty", "isnotnull": "nempty",
    "in": "in", "notin": "notIn",
    "startwith": "containForHead", "endwith": "containForTail",
}

_FILTER_OPERATOR_ALIASES = {
    "==": "eq", "=": "eq", "等于": "eq",
    "ne": "neq", "noteq": "neq", "notequals": "neq", "!=": "neq", "<>": "neq", "不等于": "neq",
    ">": "gt", "大于": "gt", ">=": "gte", "大于等于": "gte",
    "<": "lt", "小于": "lt", "<=": "lte", "小于等于": "lte",
    "contain": "contains", "include": "contains", "包含": "contains",
    "notcontain": "uncontains", "notcontains": "uncontains", "notlike": "uncontains",
    "notinclude": "uncontains", "exclude": "uncontains",
    "不包含": "uncontains",
    "startswith": "startWith", "startwith": "startWith", "开头包含": "startWith",
    "unstartswith": "unStartWith", "unstartwith": "unStartWith",
    "notstartswith": "unStartWith", "开头不包含": "unStartWith",
    "endswith": "endWith", "endwith": "endWith", "结尾包含": "endWith",
    "unendswith": "unEndWith", "unendwith": "unEndWith",
    "notendswith": "unEndWith", "结尾不包含": "unEndWith",
    "between": "range", "区间": "range",
    "containedwith": "containedWith", "被包含于": "containedWith",
    "in": "aggregate", "属于": "aggregate",
    "notin": "unaggregate", "not_in": "unaggregate", "不属于": "unaggregate",
    "isnull": "empty", "为空": "empty",
    "notempty": "nempty", "isnotnull": "nempty", "不为空": "nempty",
}

_FILTER_TEXT_COMPONENTS = {
    "String", "Text", "TextArea", "RichText", "Email", "Phone", "Mobile", "IDCard",
    "SerialNumber", "PositionComponent",
}
_FILTER_NUMBER_COMPONENTS = {
    "Number", "NumberComponent", "Money", "Monitor", "Raty", "ProgressBar",
}
_FILTER_DATE_COMPONENTS = {"Date", "DateComponent", "DateInterval", "TimeComponent", "DateTimeComponent"}
_FILTER_SELECT_COMPONENTS = {
    "Select", "SelectMultiple", "RadioBox", "CheckBox", "ImageRadioBox", "ImageCheckBox",
    "ComboSelect", "BusinessData",
}
_FILTER_BOOLEAN_COMPONENTS = {"Switch", "Boolean", "Checkbox"}
_FILTER_REFERENCE_COMPONENTS = {
    "Employee", "Department", "Subcompany", "EmployeeScope", "EmployeeOrganization",
    "HrmPosition", "Ebuilder", "RelateBrowser", "TreeSelect", "Mainline", "MainlineType",
    "Task", "Document", "Workflow", "AgendaComponent", "CustomerComponent", "ClueComponent",
    "OrderComponent", "ContactComponent", "ChanceComponent", "ProductionComponent",
    "ContractComponent", "ActivityComponent", "WorkreportComponent", "CompetitorComponent",
    "KpiFlowComponent", "QuoteComponent", "AttendComponent", "FormComponent", "DataSource",
    "ODocReceiveComponent", "RelateODoc", "CashBook", "EinvoiceComponent",
    "WorkflowPathBrowser", "WorkflowNodes", "RelateTag", "Cascader", "EmployeeShare",
    "Country", "Province", "City", "District", "Browser", "Sharer",
}

_FILTER_FILE_COMPONENTS = {"ImageComponent", "FileComponent"}
_FILTER_EMPTY_ONLY_COMPONENTS = {"HandwritingSignature", "SignatureComponent", "AudioRecord", "VideoRecord"}

_FILTER_ALLOWED_OPERATORS = {
    # ActionEbUpdate/ActionEbDelete 使用 FORM 数据源且未开启 showFilterSubOpt；
    # 这里与 @weapp/components getFuncOptsByType 的该宿主分支保持一致。
    "text": {"eq", "neq", "aggregate", "unaggregate", "contains", "uncontains",
             "startWith", "unStartWith", "endWith", "unEndWith", "empty", "nempty",
             "containedWith"},
    "number": {"range", "eq", "neq", "aggregate", "unaggregate", "gt", "lt", "gte", "lte",
               "empty", "nempty"},
    "date": {"range", "eq", "neq", "gt", "lt", "gte", "lte", "contains", "uncontains",
             "startWith", "endWith", "empty", "nempty"},
    "select": {"eq", "neq", "empty", "nempty", "aggregate", "unaggregate"},
    "boolean": {"eq", "neq", "empty", "nempty", "aggregate", "unaggregate"},
    "reference": {"eq", "neq", "empty", "nempty", "aggregate", "unaggregate"},
    "file": {"eq", "neq", "contains", "uncontains", "empty", "nempty"},
    "color": {"eq", "neq", "empty", "nempty"},
    "empty_only": {"empty", "nempty"},
    "app_tag": {"contains", "uncontains"},
    "doc_folder": {"eq", "neq", "aggregate", "unaggregate", "contains", "uncontains",
                   "startWith", "endWith", "empty", "nempty"},
    "placeholder": {"eq"},
}

_PLACEHOLDER_OPERATOR_MAP = {
    "eq": "eq", "noteq": "neq", "like": "contains", "notlike": "uncontains",
    "isnull": "empty", "isnotnull": "nempty", "between": "range",
    "include": "contains", "notinclude": "uncontains", "in": "aggregate",
    "notin": "unaggregate", "gt": "gt", "lt": "lt", "startwith": "startWith",
    "endwith": "endWith",
}

def _condition_field_family(component_key: str, field_type: str) -> str:
    """按前端 ConditionSet 的字段控件分类，而不是只压成 String/Number。"""
    if component_key in _FILTER_TEXT_COMPONENTS:
        return "text"
    if component_key in _FILTER_NUMBER_COMPONENTS:
        return "number"
    if component_key in _FILTER_DATE_COMPONENTS:
        return "date"
    if component_key in _FILTER_SELECT_COMPONENTS:
        return "select"
    if component_key in _FILTER_BOOLEAN_COMPONENTS:
        return "boolean"
    if component_key in _FILTER_REFERENCE_COMPONENTS:
        return "reference"
    if component_key in _FILTER_FILE_COMPONENTS:
        return "file"
    if component_key == "ColorPicker":
        return "color"
    if component_key in _FILTER_EMPTY_ONLY_COMPONENTS:
        return "empty_only"
    if component_key == "EbuilderAppTag":
        return "app_tag"
    if component_key in {"DocFolder", "DocFloder"}:
        return "doc_folder"
    if component_key == "Placeholder":
        return "placeholder"
    t = str(field_type or "").casefold()
    if t in {"number", "int", "integer", "long", "double", "float", "decimal"}:
        return "number"
    if t in {"date", "time", "datetime", "timestamp"}:
        return "date"
    if t in {"select", "enum"}:
        return "select"
    if t in {"bool", "boolean"}:
        return "boolean"
    return "text"

def _filter_field_type(field_type: str, component_key: str = "") -> str:
    """转换为 ConditionSet 保存 JSON 使用的真实 fieldType。"""
    family = _condition_field_family(component_key, field_type)
    return {
        "number": "Number", "date": "Date", "select": "Select",
        "boolean": "Boolean", "reference": field_type or "String",
    }.get(family, "String")

def _normalize_filter_operator(operator: Any, family: str, *, context_is_array: bool = False,
                               multi_select: bool = False,
                               allowed_override: set[str] | None = None) -> str:
    operator_text = str(operator or "eq").strip()
    raw = operator_text.casefold()
    func = _FILTER_OPERATOR_ALIASES.get(raw, operator_text)
    if context_is_array and func == "eq":
        func = "aggregate"
    elif context_is_array and func == "neq":
        func = "unaggregate"
    # 新版 ConditionSet 对多选字段把“属于/不属于”替换成“包含/不包含”。
    if multi_select and func == "aggregate":
        func = "contains"
    elif multi_select and func == "unaggregate":
        func = "uncontains"
    allowed = set(allowed_override or _FILTER_ALLOWED_OPERATORS.get(
        family, _FILTER_ALLOWED_OPERATORS["text"]))
    if multi_select:
        allowed.update({"eq", "neq", "contains", "uncontains", "empty", "nempty"})
    if func not in allowed:
        raise ValueError(
            f"filterCondition operator '{operator}' 不适用于 {family} 字段; "
            f"支持: {', '.join(sorted(allowed))}"
        )
    return func

def _condition_operator_override(field_meta: dict, family: str, component_key: str,
                                 field_id: str, filter_value_type: str = "") -> set[str] | None:
    """返回前端 getFuncOptsByType 中依赖字段实例状态的操作符集合。"""
    schema = field_meta.get("schema", {}) if isinstance(field_meta.get("schema"), dict) else {}
    raw_config = field_meta.get("config")
    if isinstance(raw_config, str):
        try:
            raw_config = json.loads(raw_config)
        except json.JSONDecodeError:
            raw_config = {}
    if family == "placeholder":
        condition_types = (
            field_meta.get("conditionType") or schema.get("conditionType")
            or (raw_config.get("conditionType") if isinstance(raw_config, dict) else None)
            or []
        )
        condition_types = condition_types if isinstance(condition_types, list) else []
        mapped = {
            _PLACEHOLDER_OPERATOR_MAP.get(
                str(entry.get("id") if isinstance(entry, dict) else entry).casefold(), "")
            for entry in condition_types
        }

        return {op for op in mapped if op} or {"eq"}
    if component_key in {"Employee", "Sharer"} and filter_value_type:
        if filter_value_type in {"Department", "Subcompany", "Position"}:
            return {"aggregate", "unaggregate", "empty", "nempty"}
        if filter_value_type == "Role":
            return {"contains", "uncontains"}
        if filter_value_type == "sup":
            return {"eq", "neq", "contains", "uncontains", "empty", "nempty"}
    field_name = str(field_meta.get("fieldName") or field_id).casefold()
    if field_name in {"batchmytags", "batchpubtags"}:
        return {"aggregate", "unaggregate", "empty", "nempty"}
    return None

def _resolve_form_ctx(result: dict, meta: dict, form_id: str) -> dict:
    """从 result(targetForm) 与 catalog 表单 schema 块解析表单级上下文.

    catalog 表单可携带真实 schema 块(sformId/objId/layoutId/...),来自平台实时
    拉取的表单定义;缺失时退化为以 formId 兜底,保证结构完整、字段可被设计器解析.
    """
    tf = result.get("targetForm", {}) or result.get("dataSource", {}) or {}
    fid = form_id or tf.get("id", "")
    group_id = tf.get("groupId", result.get("appId", ""))
    form_name = tf.get("text", tf.get("name", ""))
    form = find_in_metadata(meta, "forms", {"id": fid}) or {}
    schema = form.get("schema", {}) or {}
    return {
        "formId": fid,
        "groupId": group_id or schema.get("groupId", ""),
        "formName": form_name or schema.get("formName", ""),
        "sformId": schema.get("sformId", fid),
        "objId": schema.get("objId", fid),
        "refObjId": schema.get("refObjId", fid),
        "layoutId": schema.get("layoutId", fid),
    }

def _formula_config_object(value: dict) -> dict:
    config = value.get("config", {}) if isinstance(value, dict) else {}
    if isinstance(config, str):
        try:
            parsed = json.loads(config)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return config if isinstance(config, dict) else {}

def _build_filter_context_formula(right: dict, meta: dict, app_id: str,
                                  target_field_type: str,
                                  target_component_key: str = "") -> tuple[dict, bool]:
    """按真实 ApproveTrigger 上下文生成 ConditionSet 的 type=3 FormulaBean。"""
    workflow_id = str(meta.get("_workflow_id", "") or "") if isinstance(meta, dict) else ""
    source_id = str(meta.get("_upstream_w_id", "") or "") if isinstance(meta, dict) else ""
    requested_key = str(right.get("key") or right.get("paramKey") or right.get("value") or "")
    if requested_key.startswith(("FormData.", "ApprovalData.", "CycleParams.", "FilterResult.")):
        raise ValueError(
            "filterCondition 上下文引用必须使用原始 paramKey（key/paramKey），"
            "不能使用 FormData./ApprovalData. 设计器公式路径"
        )
    if not workflow_id:
        candidates = [wf_id for wf_id, fields in _WORKFLOW_CONTEXT_FIELDS.items()
                      if requested_key in fields]
        if len(candidates) == 1:
            workflow_id = candidates[0]
    source_meta = {}
    if workflow_id:
        _ctx_fields = _WORKFLOW_CONTEXT_FIELDS.get(workflow_id, {})
        source_meta = _ctx_fields.get(requested_key, {})  # 键=showName (如"流程ID")
        if not source_meta:
            # requested_key 可能是完整 paramKey ({wfId}.{fieldId}/requestId), 按 paramKey 遍历
            for _n, _f in _ctx_fields.items():
                if str(_f.get("paramKey") or "") == requested_key:
                    source_meta = _f
                    break
    param_key = str(source_meta.get("paramKey") or "")
    if not param_key:
        if requested_key.startswith(f"{workflow_id}.") if workflow_id else False:
            param_key = requested_key  # 已是完整 paramKey, 不重复拼 workflowId
        else:
            source_field_id = workflow_field_id(workflow_id, requested_key) if workflow_id else requested_key
            param_key = f"{workflow_id}.{source_field_id}" if workflow_id and source_field_id else source_field_id
    if not source_id or not param_key:
        raise ValueError(
            f"filterCondition 右值上下文字段 '{requested_key}' 未解析到真实触发器节点/paramKey"
        )
    label = str(right.get("label") or source_meta.get("showName") or requested_key)
    param_type = str(source_meta.get("paramType") or "").lower()
    if not param_type:
        param_type = {"Number": "double", "Date": "date", "Boolean": "boolean"}.get(
            target_field_type, "string")
    component_key = str(source_meta.get("componentKey") or "")
    if component_key:
        source_family = _condition_field_family(component_key, param_type)
        target_family = _condition_field_family(target_component_key, target_field_type)
        if source_family != target_family:
            raise ValueError(
                f"filterCondition 右值字段 '{requested_key}'({component_key}) 与左侧字段"
                f"({target_component_key or target_field_type})类型不兼容"
            )
    context_is_array = param_key.endswith("[]") or bool(source_meta.get("arrs"))
    #  ApprovalData 系统字段 (paramKey 末段非数字 且字段无
    # componentKey, 如 requestId) — value 前缀用 "ApprovalData." (组 primaryKey),
    # tableName="流程数据", tablePrimaryKey="ApprovalData"; FormData 字段
    # (末段数字 或有 componentKey, 如测试模拟 wf-1.src-text) 保持 "FormData."/"表单数据".
    # 对齐 _assign_flat_context_direct 的四要素契约 (value/frontId/tableName/parentName).
    is_approval = (not str(param_key).rsplit(".", 1)[-1].removesuffix("[]").isdigit()) \
        and not str(source_meta.get("componentKey") or "")
    value_path = param_key if param_key.startswith(("FormData.", "ApprovalData.", "CycleParams.", "FilterResult.")) else (
        f"ApprovalData.{param_key}" if is_approval else f"FormData.{param_key}")
    table_primary_key = "ApprovalData" if is_approval else "FormData"
    table_name = "流程数据" if is_approval else "表单数据"
    wf_name = str(meta.get("_upstream_workflow_name", "")) if isinstance(meta, dict) else ""
    display_parent = f"{wf_name}.{label}" if is_approval and wf_name else label
    config = {
        "paramKey": param_key,
        "paramType": param_type,
        "isMultCom": False,
        "comType": "ApproveTrigger",
        "parentName": display_parent,
        "newParentName": display_parent,
        "parentComId": 0,
        "multName": "",
        "multKey": "",
        "multTypeObj": {
            "allName": display_parent, "currentName": display_parent,
            "currentParamKey": value_path, "allParamKey": value_path,
        },
        "comId": source_id,
        "tableName": table_name,
        "fieldInfo": {"paramKey": param_key, "tablePrimaryKey": table_primary_key},
    }
    value = {
        "frontId": str(source_meta.get("id") or param_key.rsplit(".", 1)[-1].removesuffix("[]")),
        "formulaType": param_type,
        "businessId": str(gen_id()),
        "paramKey": param_key,
        "paramType": param_type,
        "name": label,
        "showName": label,
        "parentName": display_parent,
        "source": source_id,
        "id": str(gen_id()),
        "type": "3",
        "applicationId": str(app_id),
        "value": value_path,
        "arrs": context_is_array,
        "config": config,
        "fieldType": param_type,
    }
    if component_key:
        value["componentKey"] = component_key
    return value, context_is_array
