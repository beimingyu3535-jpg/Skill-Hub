"""条件节点构造与设计器契约检查。"""
from __future__ import annotations

import json
from typing import Any

from core.filter_rules import (
    _condition_field_family,
    _condition_operator_override,
    _normalize_filter_operator,
)
from core.id_generator import gen_id as _gen_id
from core.runtime_metadata import _TARGET_FORM_FIELDS, workflow_field_id as _workflow_field_id

_VISIBLE_FIELDS_CACHE: dict[tuple[str, str], list[dict]] = {}

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

def _get_visible_field_meta(workflow_id: str, source_id: str,
                           client) -> tuple[str, str]:
    """查 ESB Condition 字段浏览器, 返回 (field_id, form_id) 映射字典.
    进程内缓存 (key: workflowId+sourceId). 平台数据 paramKey 必须用
    "{formId}.{fieldId}" (字段所在表 id + 字段 id), 不是 workflowId.
    """
    key = (str(workflow_id), str(source_id))
    if key in _VISIBLE_FIELDS_CACHE:
        items = _VISIBLE_FIELDS_CACHE[key]
    else:
        try:
            items = client.get_condition_visible_fields(
                str(workflow_id), str(source_id), source=8)
        except Exception:
            items = []
        _VISIBLE_FIELDS_CACHE[key] = items
    return _make_field_index(items)

def _make_field_index(items: list) -> tuple[dict, dict]:
    """从 conditionFieldBrowser 返回的 items 构造 (name→fieldId, name→formId)."""
    name_to_fid: dict[str, str] = {}
    name_to_formid: dict[str, str] = {}
    for f in items:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name", "")).strip()
        fid = str(f.get("id", "")).strip()
        formid = str(f.get("formId", "")).strip()
        if name and fid:
            name_to_fid[name] = fid
            name_to_formid[name] = formid
    return name_to_fid, name_to_formid

def _build_condition_leaf(cond: dict, workflow_id: str, source_id: str,
                          upstream_wId: str = "", client=None) -> dict:
    """从 plan 条件构建 ESB saveCondition 叶子 (customFieldType 引用字段).

    upstream_wId: 上游触发器节点的 actionFlow wId (如 event_node.wId).
                 customFieldType.config.comId/selectType 必须用上游 wId,
                 否则前端 isLegalContextVar 在 cacheContext[comId] 找不到
                 contextData → 标"已删除".

    paramKey/value 格式关键修复: 平台数据 (采购 reloadFormula
    590+ 条样本) paramKey 是 "{formId}.{fieldId}" —— formId 是字段所在表的
    id (conditionFieldBrowser 返回的 formId 字段), 不是 workflowId.
    value 同理 "FormData.{formId}.{fieldId}".
    设计器对 paramKey 一对一匹配字段 id, 写错任何一段都会"已删除".

    字段名校验: 从 ESB conditionFieldBrowser 端点 (source=8) 查 design-time
    真实可见字段, 比 workflow-fields API 准确 (后者含子表单幽灵字段,
    设计器右栏看不见).
    """
    operator = str(cond.get("operator", "nempty")).casefold()
    mapped = _OPERATOR_MAP.get(operator)
    if mapped is None:
        # validate 已拦截非法操作符; 这里兜底防静默降级(写错拼写绝不能生成"不为空")
        raise ValueError(
            f"condition.operator '{operator}' is not supported "
            f"(支持: eq/neq/gt/gte/lt/lte/contains/notcontains/in/notin/empty/nempty)"
        )
    select_type, opt_code = mapped
    left = cond.get("left", {})
    field_key = str(left.get("key", left.get("paramKey", "")))
    field_label = str(left.get("label", field_key))

    # EnquiryForm 的 count 是上游查询节点输出，不是流程字段。
    # 它不应走 conditionFieldBrowser / workflow-fields；否则会被错误判定为
    # “不是流程可见字段”。这里保留平台条件叶子的统一结构，但把来源域
    # 指向查询节点，并使用 count 原始输出键。
    is_enquiry_count = field_key in {"count", "response.count", "Response.response.count"}

    # 字段 id: 从 ESB 字段浏览器 (source=8, design-time 真实可见字段) 查.
    #  - 第一页无 searchValue 查 (10 条, 命中"分页 1"字段)
    #  - 没命中用 searchValue=字段名 查 (命中第 2 页及以后的字段)
    #  - 兜底用 _WORKFLOW_FIELD_IDS (workflow-fields API, 含子表单幽灵字段)
    field_id = ""
    if client is not None and workflow_id and not is_enquiry_count:
        name_to_fid, _ = _get_visible_field_meta(workflow_id, source_id, client)
        field_id = name_to_fid.get(field_key, "")
        if not field_id:
            try:
                resp = client._request(
                    "/api/workflow/pathdef/common/browser/complete/conditionFieldBrowser",
                    method="POST",
                    json_body={
                        "browserMultiple": False,
                        "sourceId": str(source_id),
                        "tab": "formField",
                        "source": 8,
                        "workflowId": str(workflow_id),
                        "newly": 1,
                        "searchValue": str(field_key),
                    },
                )
                items = (resp.get("data") or {}).get("data") or []
                for f in items if isinstance(items, list) else []:
                    if isinstance(f, dict) and str(f.get("name", "")).strip() == field_key:
                        fid = str(f.get("id", "")).strip()
                        if fid:
                            field_id = fid
                            name_to_fid[field_key] = fid
                        break
            except Exception:
                pass
    if not field_id and workflow_id and not is_enquiry_count:
        fid = _workflow_field_id(str(workflow_id), field_key)
        if fid and fid != field_key:
            field_id = fid
    if field_key and workflow_id and not field_id and not is_enquiry_count and client is not None:
        try:
            items = client.get_condition_visible_fields(
                str(workflow_id), str(source_id), source=8) if client else []
        except Exception:
            items = []
        visible_names = [f.get("name") for f in items if isinstance(f, dict)][:20]
        raise ValueError(
            f"condition.left.key='{field_key}' 不是流程 '{workflow_id}' 可见字段. "
            f"设计器可见字段: {visible_names}. "
            f"请从设计器右栏的字段列表中选."
        )

    # paramKey/value 契约:
    #   getComponentContext (ApproveTrigger) 返回 tableData 里字段 paramKey =
    #   "{workflowId}.{fieldId}" (如 '<workflowId>.<fieldId>').
    #   "已删除" 判定 = assign.paramKey 必须在 tableData[].paramKey 中精确匹配.
    if is_enquiry_count:
        param_key_id = "response.count"
        value_id = "response.count"
        com_type = "EnquiryForm"
    elif field_id and workflow_id:
        param_key_id = f"{workflow_id}.{field_id}"
        value_id = f"FormData.{workflow_id}.{field_id}"
        com_type = "ApproveTrigger"
    else:
        param_key_id = field_key
        value_id = f"FormData.{field_key}" if field_key else ""
        com_type = "EbGetDataById"

    # upstream_wId: 上游触发器节点的 actionFlow wId (非工作流节点物理 id).
    # contexts?.[source] 用 actionFlow wId 索引 cacheContext; comId 必须传
    # 上游 wId 才能让前端 isLegalContextVar 在 cacheContext 里找到 contextData.
    child: dict[str, Any] = {
        "selectType": select_type,
        "workflowId": workflow_id,
        "elementValue1Id": "",
        "elementValue2Id": "",
        "expressionBaseId": "",
        "dataValueId": "",
        # 真实叶子用 customFieldType 引用上下文字段 (非 formField)
        "customFieldType": {
            "paramType": "string", "formulaType": "string",
            "name": field_label or field_key, "businessId": "",
            "selectType": "-1", "id": "", "source": upstream_wId,
            "type": "3", "value": value_id,
            "config": {
                "paramKey": param_key_id, "paramType": "string",
                "isMultCom": False, "comType": com_type,
                "parentComId": 0, "parentName": field_label,
                "multName": "", "multKey": "",
                "multTypeObj": {
                    "allName": field_label, "currentName": field_label,
                    "currentParamKey": value_id,
                    "allParamKey": value_id,
                },
                "comId": upstream_wId, "newParentName": field_label,
            },
            "fieldType": "string",
        },
    }

    is_unary = opt_code in ("13", "14")
    right = cond.get("right", {}) if isinstance(cond, dict) else {}

    if select_type == "97":
        child["StringCompareOptionLeft"] = opt_code
        if not is_unary:
            # right 两种形式:
            #   固定值: {value: "..."}  → StringTextValueLeft (type=1)
            #   上下文字段: {key/label: "..."} → 自定义 customFieldType (type=3)
            # 二者互斥: 有 key/label 就走自定义字段; 否则固定值.
            if isinstance(right, dict) and (right.get("key") or right.get("label")):
                right_label = str(right.get("label") or right.get("key") or "").strip()
                right_key = str(right.get("key") or right.get("label") or "").strip()
                # 字段名校验 + id 解析 (与 left 同样的处理路径)
                right_field_id = ""
                if client is not None and workflow_id:
                    name_to_fid, name_to_formid = _get_visible_field_meta(
                        workflow_id, source_id, client)
                    right_field_id = name_to_fid.get(right_key, "")
                    if not right_field_id:
                        try:
                            resp = client._request(
                                "/api/workflow/pathdef/common/browser/complete/conditionFieldBrowser",
                                method="POST",
                                json_body={
                                    "browserMultiple": False,
                                    "sourceId": str(source_id),
                                    "tab": "formField", "source": 8,
                                    "workflowId": str(workflow_id),
                                    "newly": 1, "searchValue": right_key,
                                })
                            items = (resp.get("data") or {}).get("data") or []
                            for f in items if isinstance(items, list) else []:
                                if isinstance(f, dict) and str(f.get("name", "")).strip() == right_key:
                                    fid = str(f.get("id", "")).strip()
                                    if fid:
                                        right_field_id = fid
                                        break
                        except Exception:
                            pass
                if not right_field_id and workflow_id:
                    fid = _workflow_field_id(str(workflow_id), right_key)
                    if fid and fid != right_key:
                        right_field_id = fid
                if right_key and workflow_id and not right_field_id:
                    raise ValueError(
                        f"condition.right.key='{right_key}' 不是流程 '{workflow_id}' 可见字段"
                    )
                if right_field_id:
                    right_param_key = f"{workflow_id}.{right_field_id}"
                    right_value_id = f"FormData.{workflow_id}.{right_field_id}"
                    right_com_type = "ApproveTrigger"
                else:
                    right_param_key = right_key
                    right_value_id = f"FormData.{right_key}" if right_key else ""
                    right_com_type = "EbGetDataById"
                child["StringTextValueLeft"] = {
                    "formulaType": "string", "paramType": "string",
                    "name": right_label or right_key, "selectType": "-1",
                    "id": str(_gen_id()), "source": upstream_wId,
                    "type": "3", "value": right_value_id,
                    "config": {
                        "paramKey": right_param_key, "isMultCom": False,
                        "comType": right_com_type, "parentComId": 0,
                        "parentName": right_label or right_key,
                        "paramType": "string", "fieldInfo": {
                            "paramKey": right_param_key, "tablePrimaryKey": "FormData"},
                        "tableName": "表单数据", "multName": "", "multKey": "",
                        "multTypeObj": {
                            "allName": right_label, "currentName": right_label,
                            "currentParamKey": right_value_id, "allParamKey": right_value_id},
                        "comId": upstream_wId, "newParentName": right_label,
                    },
                    "fieldType": "string",
                }
            else:
                value = str(right.get("value", "")) if isinstance(right, dict) else ""
                if value:
                    child["StringTextValueLeft"] = {
                        "formulaType": "string", "name": value,
                        "selectType": "-1", "id": "", "type": "1",
                        "value": value, "fieldType": "string",
                    }
    else:
        # 数值/日期类 right 暂只支持固定值 (上下文引用用 StringTextValueLeft 路径)
        value = str(right.get("value", "")) if isinstance(right, dict) else ""
        child["NumberCompareOptionLeft"] = int(opt_code)
        child["NumberValueOptionLeft"] = 1
        if not is_unary and value:
            child["NumberTextValueLeft1"] = value
    return child

def _build_condition_childrens(plan_action: dict, workflow_id: str,
                               source_id: str, upstream_wId: str = "",
                               client=None) -> list[dict]:
    """从 plan 的 branch 条件构建 saveCondition childrens.

    upstream_wId: 上游触发器节点 actionFlow wId, 传给 leaf 让 customFieldType
    .config.comId 指向正确节点 (前端 isLegalContextVar 用它索引 cacheContext).
    """
    childrens: list[dict] = []
    # Condition 的公开组件合同把 branches 放在 params 中；编译后的 Draft 才会
    # 提升到节点顶层。这里拿到的是原始 plan，必须兼容两种合法形态，否则会
    # 静默保存默认的“(不为空)”空叶子，设计器中表现为条件没有内容。
    branches = plan_action.get("branches")
    if not isinstance(branches, list):
        params = plan_action.get("params", {})
        branches = params.get("branches", []) if isinstance(params, dict) else []
    for branch in branches:
        if not isinstance(branch, dict):
            continue
        cond = branch.get("condition", {})
        if not isinstance(cond, dict) or cond.get("type") == "else":
            continue
        childrens.append(_build_condition_leaf(cond, workflow_id, source_id, upstream_wId, client))
    if not childrens:
        childrens.append(_build_condition_leaf(
            {"left": {}, "operator": "nempty", "right": {}},
            workflow_id, source_id, upstream_wId))
    return childrens

# 设计器「动态赋值」对话框的合法 objType 枚举 (SendMessage/auth/constants.ts getObjectOptions)
_VALID_SHARE_OBJTYPES = {
    "resource", "department", "subcompany", "role", "group", "position",
    "external", "all", "allExternal", "employeeScope", "employeeShare",
    "employeeOrganization",
}

def _designer_contract_check(design: dict) -> tuple[list[str], list[str]]:
    """设计器契约自检 (保存前拦截"服务端接受但 UI 显示错位"的字段).

    平台预检是纯结构层, 对下列"前端契约"字段静默接受, 只有设计器
    打开时才暴雷 (已删除 / 对象类型空 / 表单没选 / 条件左值空). 这些必须
    在保存前显式校验, 否则每次都要靠用户截图发现问题.

    校验项:
      1. ActionEbAdd/Update/Delete targetForm.groupId 不能是 -1/空 (否则"表单没选")
      2. SendMessage shareList[].objType 必须在枚举内 (否则"对象类型请选择")
      3. setting.main 的 assign paramKey/value 不能是中文 (否则"已删除")
      4. Condition conditionDetail.conditionDataJson 必须非空 (否则条件丢失)
      5. person 必须存在 (Add/Update/Delete 必有, 否则执行时报错)
      6. 主链必须有 Output 结束节点 (否则流程不完整)
      7. filterInput 必须保留真实字段控件类型，动态右值必须引用上游节点真实 paramKey
    返回 (errors, warnings); errors 非空必须中止保存.
    """
    errors: list[str] = []
    warnings: list[str] = []
    actions = design.get("actions", [])
    if not isinstance(actions, list):
        return [], []

    has_output = False
    event = design.get("event", {}) if isinstance(design.get("event"), dict) else {}
    event_id = str(event.get("id") or event.get("wId") or "")
    event_data = event.get("data", {}) if isinstance(event.get("data"), dict) else {}
    workflow_path = event_data.get("workflowPath")
    workflow_id = ""
    if isinstance(workflow_path, list) and workflow_path and isinstance(workflow_path[0], dict):
        workflow_id = str(workflow_path[0].get("id") or "")

    def config_object(value: dict) -> dict:
        cfg = value.get("config", {}) if isinstance(value, dict) else {}
        if isinstance(cfg, str):
            try:
                parsed = json.loads(cfg)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return cfg if isinstance(cfg, dict) else {}

    def validate_condition_set(owner: str, filter_input: Any,
                               target_form_id: str) -> None:
        """校验 ConditionSet 四段链路：字段→操作符→取值方式→值控件。"""
        if not isinstance(filter_input, dict) or not isinstance(filter_input.get("datas"), list):
            return
        known_fields = _TARGET_FORM_FIELDS.get(str(target_form_id), {})
        for j, item in enumerate(filter_input["datas"]):
            if not isinstance(item, dict) or item.get("type") != "condition":
                continue
            path = f"{owner}.datas[{j}]"
            field_id = str(item.get("id") or item.get("fieldName") or "")
            expected = known_fields.get(field_id, {})
            expected_comp = str(expected.get("componentKey") or "")
            actual_comp = str(item.get("compType") or "")
            if expected_comp and actual_comp != expected_comp:
                errors.append(
                    f"{path}.compType='{actual_comp}' 与实时字段 componentKey='{expected_comp}' 不一致"
                )
            conditions = item.get("conditions", {}) if isinstance(item.get("conditions"), dict) else {}
            func = str(conditions.get("func") or "")
            value = conditions.get("value")
            value_mode = conditions.get("type")
            raw_field_type = str(expected.get("type") or expected.get("fieldType") or item.get("fieldType") or "String")
            family = _condition_field_family(actual_comp, raw_field_type)
            is_multi = item.get("multiSelect") is True or str(item.get("multiSelect")).casefold() == "true"
            allowed_override = _condition_operator_override(
                expected, family, actual_comp, field_id,
                str(conditions.get("filterValueType") or ""))
            try:
                normalized_func = _normalize_filter_operator(
                    func, family, multi_select=is_multi, allowed_override=allowed_override)
                if normalized_func != func:
                    errors.append(
                        f"{path}.conditions.func='{func}' 应按 {actual_comp or family} 规则保存为 "
                        f"'{normalized_func}'"
                    )
            except ValueError as exc:
                errors.append(f"{path}: {exc}")
            if func in {"empty", "nempty"}:
                if conditions.get("isEsb") is True or value not in (None, ""):
                    errors.append(f"{path} 空值操作符不应携带右值/动态赋值")
                continue

            if conditions.get("isEsb") is True and not isinstance(value, dict):
                errors.append(f"{path} 动态赋值必须保存为 FormulaBean 对象")
            elif conditions.get("isEsb") is True and isinstance(value, dict):
                formula_type = str(value.get("type") or "")
                cfg = config_object(value)
                if formula_type == "1":
                    errors.append(
                        f"{path} 固定/手动输入不能设置 isEsb=true 或封装为 FormulaBean；"
                        "ConditionSet 会把它渲染成动态赋值标签"
                    )
                elif formula_type == "3":
                    pk = str(cfg.get("paramKey") or "")
                    if str(value.get("source") or "") != event_id or str(cfg.get("comId") or "") != event_id:
                        errors.append(f"{path} 动态右值未引用上游事件节点")
                    if workflow_id and not pk.startswith(f"{workflow_id}."):
                        errors.append(
                            f"{path}.paramKey='{pk}' 不是当前流程字段路径 '{workflow_id}.<fieldId>'"
                        )
                    if str(value.get("applicationId") or "") != str(design.get("appId") or ""):
                        errors.append(f"{path}.applicationId 未指向当前动作流")
                    expected_mode = "custombyhander" if family == "reference" else "formField"
                    if str(value.get("value") or "").startswith("FormData.") and value_mode != expected_mode:
                        errors.append(
                            f"{path}.conditions.type='{value_mode}'，应为 '{expected_mode}'，"
                            "否则第三个取值方式选择框不能正确回显"
                        )
                else:
                    errors.append(f"{path} 不支持的动态赋值 FormulaBean.type='{formula_type}'")
            elif conditions.get("isEsb") is False:
                # 非 ESB 分支由具体 FilterCom 决定第三个选择框。除空/手动/selectData 外，
                # 还可能是 custom/custombyhander/formField/varField/filterVal、日期系统值、
                # 当前人员/部门/分部及其他组件专属原生 mode，不能再用全局三值白名单误杀。
                if isinstance(value, dict) and str(value.get("type") or "") in {"1", "3"} \
                        and (value.get("businessId") or value.get("formulaType")):
                    errors.append(f"{path} isEsb=false 时不能携带 FormulaBean，应保存组件原生值")

    event_source = event_data.get("targetForm") or event_data.get("dataSource") or {}
    event_form_id = str(event_source.get("id") or event_source.get("sourceId") or "") if isinstance(event_source, dict) else ""
    validate_condition_set(
        f"event({event.get('type', '')}).filterInput",
        event_data.get("filterInput") or event_data.get("dataFilter"),
        event_form_id,
    )

    for i, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        ctype = str(action.get("type", ""))
        data = action.get("data", {}) if isinstance(action.get("data"), dict) else {}

        # 1) targetForm.groupId 契约
        if ctype in {"ActionEbAdd", "ActionEbUpdate", "ActionEbDelete"}:
            tf = data.get("targetForm")
            if isinstance(tf, dict):
                gid = str(tf.get("groupId", "")).strip()
                if not gid or gid in {"-1", "0"}:
                    errors.append(
                        f"actions[{i}]({ctype}).targetForm.groupId='{gid}' 非法: "
                        f"表单必须属于某个 e-builder 应用 (preflight 会自动补全, 查不到应报错)"
                    )
                else:
                    # appType/tableType 应与 targetForm 一致
                    at = data.get("appType")
                    if isinstance(at, list) and at:
                        at_id = str(at[0].get("id", "")) if isinstance(at[0], dict) else ""
                        if at_id != gid:
                            errors.append(
                                f"actions[{i}]({ctype}).appType[0].id='{at_id}' 与 targetForm.groupId='{gid}' 不一致"
                            )
            else:
                errors.append(f"actions[{i}]({ctype}).targetForm missing")
            # 5) person 必须存在
            if not data.get("person"):
                errors.append(f"actions[{i}]({ctype}).data.person missing (数据操作人必填)")

            # 7) ConditionSet 字段/操作符/取值方式/值控件契约
            target_form_id = str(tf.get("id") or "") if isinstance(tf, dict) else ""
            validate_condition_set(
                f"actions[{i}]({ctype}).filterInput", data.get("filterInput"), target_form_id)

        if ctype == "EnquiryForm":
            ds = data.get("dataSource") or {}
            ds_id = str(ds.get("id") or ds.get("sourceId") or "") if isinstance(ds, dict) else ""
            validate_condition_set(
                f"actions[{i}](EnquiryForm).filterInput", data.get("filterInput"), ds_id)

        # 2) SendMessage shareList objType 契约
        if ctype == "SendMessage":
            share_list = data.get("shareList")
            if isinstance(share_list, list) and share_list:
                for j, entry in enumerate(share_list):
                    if not isinstance(entry, dict):
                        continue
                    ot = str(entry.get("objType", "")).strip()
                    if ot and ot not in _VALID_SHARE_OBJTYPES:
                        errors.append(
                            f"actions[{i}](SendMessage).shareList[{j}].objType='{ot}' 非法, "
                            f"合法值: {sorted(_VALID_SHARE_OBJTYPES)}"
                        )
                    elif not ot:
                        errors.append(f"actions[{i}](SendMessage).shareList[{j}].objType 缺失")
                    # 值字段(obj_id 系列)必须存在 (除了 all/allExternal 无值类型)
                    has_value_field = any(
                        k.startswith("obj_id") and v for k, v in entry.items() if k != "objType"
                    )
                    if ot not in {"all", "allExternal"} and not has_value_field:
                        errors.append(
                            f"actions[{i}](SendMessage).shareList[{j}] 缺对象值字段 "
                            f"(obj_id/obj_id_<type>), 设计器「对象」列会为空"
                        )
            elif data.get("person") is None:
                warnings.append(f"actions[{i}](SendMessage): 无 shareList 也无 person, 接收人可能为空")

        # 3) setting.main paramKey 契约 (中文 → 设计器"已删除")
        if ctype in {"ActionEbAdd", "ActionEbUpdate"}:
            setting = data.get("setting")
            main = setting.get("main", {}) if isinstance(setting, dict) else {}
            if isinstance(main, dict):
                for fid, entry in main.items():
                    if not isinstance(entry, dict):
                        continue
                    v = entry.get("value", {})
                    if not isinstance(v, dict):
                        continue
                    assign = v.get("assign")
                    if not isinstance(assign, dict):
                        continue
                    # assign.type=8 容器 → 查 childs; 直接 type=3/9 → 查自身
                    nodes = []
                    if assign.get("type") == "8" and isinstance(assign.get("childs"), list):
                        nodes = [c for c in assign["childs"] if isinstance(c, dict)]
                    else:
                        nodes = [assign]
                    for n in nodes:
                        ntype = str(n.get("type", ""))
                        # 1固定/3上下文/4/5/6运算/9系统变量/10 esbAssignSelf
                        if ntype not in {"1", "3", "5", "4", "6", "9", "10"}:
                            warnings.append(
                                f"actions[{i}]({ctype}).setting.main['{fid}'].assign.type='{ntype}' 未知"
                            )
                        cfg = n.get("config")
                        if ntype == "3" and isinstance(cfg, dict):
                            pk = str(cfg.get("paramKey", "")).strip()
                            if pk and "." in pk:
                                a, b = pk.rsplit(".", 1)
                                #  仅当**首段非数字**才警告 — 中文/裸 key 设计器
                                # 标"已删除"。'{wfId}.requestId' (ApprovalData 流程数据引用)
                                # 未定义变量直接 NameError; 且对 requestId 后缀误报).
                                #  'dataResponse.{fieldId}' 前缀是
                                # 表单类事件 (DateTrigger/TimeBatchTrigger/EventFormData)
                                # 的**合法上下文格式** (前端 cacheContext 原样缓存,
                                #  已钉死), 不是中文 key — 仅首段=dataResponse 放过,
                                # 中文/其它字母前缀仍告警 (设计器标"已删除").
                                if not a.isdigit() and a != "dataResponse":
                                    warnings.append(
                                        f"actions[{i}]({ctype}).setting.main['{fid}'].paramKey='{pk}' "
                                        f"非 '{workflow_id}.{{fieldId}}' 数字格式, 设计器可能标'已删除'"
                                    )
                            elif pk and not pk.isdigit():
                                warnings.append(
                                    f"actions[{i}]({ctype}).setting.main['{fid}'].paramKey='{pk}' "
                                    f"中文/裸 key, 设计器可能标'已删除'"
                                )

        # 4) Condition conditionDetail 契约
        if ctype == "Condition":
            cd = data.get("conditionDetail")
            if not isinstance(cd, dict) or not cd.get("conditionDataJson"):
                errors.append(
                    f"actions[{i}](Condition).data.conditionDetail.conditionDataJson 缺失, "
                    f"条件不会保存 (需走 ESB saveCondition 两步法)"
                )

        # 6) Output 结束节点
        if ctype == "Output":
            has_output = True

    if not has_output:
        errors.append("design.actions 缺少 Output 结束节点 (主链必须以 Output 结尾)")

    return errors, warnings
