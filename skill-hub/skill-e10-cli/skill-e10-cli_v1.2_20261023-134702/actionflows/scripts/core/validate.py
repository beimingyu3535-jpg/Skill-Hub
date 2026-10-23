from __future__ import annotations

import json
import sys
from typing import Any

from core.component_registry import (
    get_registered_components,
    has_concrete_value,
    validate_assignment_value,
    validate_provided_param,
)

# ---------------------------------------------------------------------------
# 1. Semantic plan validation (was validate_semantic_plan.py)
# ---------------------------------------------------------------------------

MODEL_MANAGED_FIELDS = {"id", "previousId", "missingFields"}

# 与 actionflow_skill._OPERATOR_MAP 对齐的操作符白名单(含常见别名)。
# 未识别的操作符必须报错, 不能静默降级(否则写错拼写会生成错误条件).
_SUPPORTED_OPERATORS = frozenset({
    "empty", "isnull", "为空",
    "nempty", "isnotnull", "不为空",
    "eq", "equals", "等于",
    "neq", "notequals", "不等于",
    "contains", "包含",
    "notcontains", "notcontain", "不包含",
    "in", "属于",
    "notin", "不属于",
    "gt", "greaterthan", "大于",
    "lt", "lessthan", "小于",
    "gte", "ge", "大于等于",
    "lte", "le", "小于等于",
})

_DESIGNER_CONTEXT_PREFIXES = (
    "FormData.", "ApprovalData.", "CycleParams.", "FilterResult.",
)


def _validate_context_reference(value: Any, path: str, errors: list[str]) -> None:
    """Keep semantic plans independent from designer FormulaBean paths.

    A semantic plan identifies an upstream value with its raw ``paramKey``.
    ``FormData.*``/``ApprovalData.*`` are generated DTO display paths, not plan
    values.  Letting one into a plan makes it easy for a caller that skips the
    compiler to persist it as a quoted fixed string in ConditionSet.
    """
    if not isinstance(value, dict):
        return
    source = value.get("sourceRef") if isinstance(value.get("sourceRef"), dict) else value
    kind = str(source.get("kind") or source.get("assignmentKind") or source.get("type") or "").lower()
    if kind not in {"context", "user_reference"}:
        return
    display_path = str(source.get("value") or "")
    raw_key = str(source.get("paramKey") or source.get("key") or source.get("fieldKey") or "")
    if display_path.startswith(_DESIGNER_CONTEXT_PREFIXES) or raw_key.startswith(_DESIGNER_CONTEXT_PREFIXES):
        errors.append(
            f"{path}: 上下文引用只能传原始 paramKey（放在 paramKey/key），"
            "不能传 FormData./ApprovalData. 等设计器公式路径"
        )
    if not raw_key.strip():
        errors.append(f"{path}: 上下文引用缺少 paramKey/key")


def _validate_plan_context_contract(value: Any, path: str, errors: list[str]) -> None:
    """Recursively validate semantic context objects and mapping source keys.

    This runs before any platform DTO is built.  It deliberately validates only
    structured context references: a free-text message body may mention the
    literal word ``FormData`` without becoming a formula.
    """
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_plan_context_contract(item, f"{path}[{index}]", errors)
        return
    if not isinstance(value, dict):
        return
    _validate_context_reference(value, path, errors)
    for key, item in value.items():
        item_path = f"{path}.{key}"
        if key == "mapping" and isinstance(item, dict):
            for source_key in item:
                if str(source_key).startswith(_DESIGNER_CONTEXT_PREFIXES):
                    errors.append(
                        f"{item_path}.{source_key}: mapping 源字段必须是本次上下文返回的原始 paramKey，"
                        "不能使用设计器公式路径"
                    )
        _validate_plan_context_contract(item, item_path, errors)

def validate_node(
    node: Any,
    path: str,
    expected_role: str,
    errors: list[str],
) -> None:
    if not isinstance(node, dict):
        errors.append(f"{path} should be an object")
        return

    for key in MODEL_MANAGED_FIELDS.intersection(node):
        errors.append(f"{path}.{key} is compiler-managed and must not be provided")

    component_type = node.get("type")
    params = node.get("params")
    if not isinstance(component_type, str) or not component_type:
        errors.append(f"{path}.type is required")
        return
    if component_type == "Output":
        # Output(终止) 只能通过 finalOutput 表达主链结束, 不能出现在动作列表
        # 或条件分支里 (用户语义: output 是最后的).
        errors.append(f"{path}.type Output must be expressed through finalOutput")
        return
    if not isinstance(params, dict):
        errors.append(f"{path}.params should be an object")
        return

    components = get_registered_components()
    contract = components.get(component_type)
    if not contract:
        errors.append(f"{path}.type {component_type} has no component registry contract")
        return
    if contract["nodeRole"] != expected_role:
        errors.append(f"{path}.type {component_type} is not a {expected_role} component")
        return

    allowed_params = set(contract["params"])
    #: 转换器自动补齐的字段不算 plan 层参数 — 组件 params 未显式声明,
    # 但传了也不报错 (validate 只认声明参数会误报 "not defined", 如 TimeBatchTrigger
    # 的 queryFields/operator/filterCondition 由 draft_to_real 自动生成).
    EXTRA_ALLOWED = {
        "TimeBatchTrigger": {"queryFields", "operator", "filterCondition"},
        "EventFormData": {"filter", "filterCondition", "queryFields"},
        "DateTrigger": {"filter", "filterCondition", "queryFields"},
    }
    allowed_params |= EXTRA_ALLOWED.get(component_type, set())
    for key in params:
        if key not in allowed_params:
            errors.append(f"{path}.params.{key} is not defined for {component_type}")
            continue
        for reason in validate_provided_param(params[key], contract["params"][key]):
            errors.append(f"{path}.params.{key} {reason}")
        if component_type in {"ActionEbAdd", "ActionEbUpdate"} and key in {"setting", "updates"}:
            if isinstance(params[key], list):
                for index, item in enumerate(params[key]):
                    if not isinstance(item, dict) or "value" not in item:
                        continue
                    for reason in validate_assignment_value(item["value"]):
                        errors.append(f"{path}.params.{key}[{index}].value {reason}")
    _validate_plan_context_contract(params, f"{path}.params", errors)

    # 组件包可登记专用动态必填/互斥规则；公共校验通过后再执行，避免新增
    # 组件必须改这个公共文件。
    from components import get_validator
    validator = get_validator(component_type)
    if validator:
        for reason in validator(params, node=node):
            errors.append(f"{path} {reason}")

    if component_type != "Condition":
        return
    branches = node.get("branches")
    if not isinstance(branches, list) or not branches:
        errors.append(f"{path}.branches must be a non-empty array")
        return
    else_index: int | None = None
    for index, branch in enumerate(branches):
        branch_path = f"{path}.branches[{index}]"
        if not isinstance(branch, dict):
            errors.append(f"{branch_path} should be an object")
            continue
        for key in MODEL_MANAGED_FIELDS.intersection(branch):
            errors.append(f"{branch_path}.{key} is compiler-managed and must not be provided")
        condition = branch.get("condition", {})
        if condition is not None and not isinstance(condition, dict):
            errors.append(f"{branch_path}.condition should be an object or null")
        elif isinstance(condition, dict):
            is_else = condition.get("type") == "else"
            if is_else:
                if else_index is not None:
                    errors.append(f"{branch_path}.condition: only one else branch is allowed")
                else:
                    else_index = index
                if index != len(branches) - 1:
                    errors.append(f"{branch_path}.condition: else branch must be last")
                invalid_else_keys = set(condition) - {"type"}
                if invalid_else_keys:
                    errors.append(f"{branch_path}.condition else must not include {sorted(invalid_else_keys)}")
            else:
                left = condition.get("left")
                operator = condition.get("operator")
                if not isinstance(left, dict) or not str(left.get("key", "")).strip():
                    errors.append(f"{branch_path}.condition.left.key must be a resolved platform field key")
                if not isinstance(operator, str) or not operator.strip():
                    errors.append(f"{branch_path}.condition.operator is required")
                elif str(operator).casefold() not in _SUPPORTED_OPERATORS:
                    errors.append(
                        f"{branch_path}.condition.operator '{operator}' is not supported "
                        f"(支持: eq/neq/gt/gte/lt/lte/contains/notcontains/empty/nempty)"
                    )
                if str(operator).casefold() not in {"empty", "isnull", "为空", "nempty", "isnotnull", "不为空"}:
                    # right 可以是固定值 ({value: ...}) 或上下文字段 ({key/label: ...})
                    right = condition.get("right")
                    if not isinstance(right, dict):
                        errors.append(f"{branch_path}.condition.right is required and must be an object")
                    elif "value" not in right and not (right.get("key") or right.get("label")):
                        errors.append(
                            f"{branch_path}.condition.right 必须含 value (固定值) 或 key/label (上下文字段)"
                        )
        branch_actions = branch.get("actions")
        if not isinstance(branch_actions, list):
            errors.append(f"{branch_path}.actions should be an array")
            continue
        for step_index, step in enumerate(branch_actions):
            validate_node(step, f"{branch_path}.actions[{step_index}]", "action", errors)

def validate_semantic_plan(plan: dict[str, Any]) -> dict[str, list[str] | bool]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(plan, dict):
        return {"valid": False, "errors": ["semantic plan should be an object"], "warnings": []}

    validate_node(plan.get("event"), "event", "event", errors)
    actions = plan.get("actions")
    if not isinstance(actions, list):
        errors.append("actions should be an array")
    else:
        for index, step in enumerate(actions):
            validate_node(step, f"actions[{index}]", "action", errors)

    final_output = plan.get("finalOutput", {})
    if not isinstance(final_output, dict):
        errors.append("finalOutput should be an object")
    else:
        output_params = final_output.get("params", {})
        if not isinstance(output_params, dict):
            errors.append("finalOutput.params should be an object")
        else:
            output_contract = get_registered_components()["Output"]
            for key in output_params:
                if key not in output_contract["params"]:
                    errors.append(f"finalOutput.params.{key} is not defined for Output")
                    continue
                for reason in validate_provided_param(output_params[key], output_contract["params"][key]):
                    errors.append(f"finalOutput.params.{key} {reason}")

    plan_warnings = plan.get("warnings", [])
    if not isinstance(plan_warnings, list) or not all(isinstance(item, str) for item in plan_warnings):
        errors.append("warnings should be an array of strings")
    else:
        warnings.extend(plan_warnings)

    return {"valid": not errors, "errors": errors, "warnings": warnings}

# ---------------------------------------------------------------------------
# 2. Workflow draft validation (was validate_workflow_draft.py)
# ---------------------------------------------------------------------------

def build_contracts() -> tuple[dict[str, Any], set[str], set[str]]:
    """Build validation sets exclusively from the current component registry."""
    contracts = get_registered_components()
    trigger_types = {
        component_type
        for component_type, contract in contracts.items()
        if contract["nodeRole"] == "event"
    }
    action_types = {
        component_type
        for component_type, contract in contracts.items()
        if contract["nodeRole"] == "action"
    }
    return contracts, trigger_types, action_types

def validate_params(node: dict[str, Any], contract: dict[str, Any] | None, path: str, errors: list[str]) -> None:
    component_type = node.get("type")
    if not contract:
        errors.append(f"{path}: unknown component type {component_type}")
        return

    params = node.get("params", {})
    if not isinstance(params, dict):
        errors.append(f"{path}: params should be an object")
        return
    missing_fields = node.get("missingFields", [])
    if not isinstance(missing_fields, list):
        errors.append(f"{path}: missingFields should be an array")
        missing_fields = []

    definitions = contract.get("params", {})
    for key, value in params.items():
        definition = definitions.get(key)
        if not definition:
            errors.append(f"{path}: params.{key} is not defined in schema for {component_type}")
            continue
        if definition.get("valueType") == "enum":
            allowed_values = {option["value"] for option in definition.get("options", [])}
            if value not in allowed_values:
                errors.append(f"{path}: params.{key} has invalid enum value {value}")

    for key, definition in definitions.items():
        if not definition.get("required"):
            continue
        if has_concrete_value(params.get(key)) or key in missing_fields:
            continue
        errors.append(f"{path}: required params.{key} is missing and not listed in missingFields")

def validate_action_chain(actions: list[dict[str, Any]], path: str, errors: list[str]) -> None:
    previous = "0"
    for index, action in enumerate(actions):
        if action.get("previousId") != previous:
            errors.append(
                f"{path}[{index}]: previousId should be {previous}, got {action.get('previousId')}"
            )
        previous = action.get("id", "")

def validate_branch_actions(
    action: dict[str, Any],
    path: str,
    action_types: set[str],
    contracts: dict[str, Any],
    errors: list[str],
) -> None:
    if action.get("type") != "Condition":
        return
    for branch_index, branch in enumerate(action.get("branches", [])):
        previous = "0"
        for action_index, branch_action in enumerate(branch.get("actions", [])):
            branch_path = f"{path}.branches[{branch_index}].actions[{action_index}]"
            if branch_action.get("type") == "Output":
                errors.append(
                    f"{branch_path}: Output is not allowed inside branch actions "
                    f"(Output 是主链结束节点, 请用 finalOutput 表达)"
                )
            if branch_action.get("type") not in action_types:
                errors.append(f"{branch_path}: unknown action type {branch_action.get('type')}")
            validate_params(branch_action, contracts.get(branch_action.get("type")), branch_path, errors)
            if branch_action.get("previousId") != previous:
                errors.append(
                    f"{branch_path}: previousId should be {previous}, got {branch_action.get('previousId')}"
                )
            previous = branch_action.get("id", "")

def check_context_domains(
    action: dict[str, Any], path: str, errors: list[str], warnings: list[str],
) -> None:
    """组件 × 上下文来源校验 .

    宽松白名单: 只 block 明确违规 (平台实证必失败的写法), 未知/未验证来源域仅 warn.
    原则: 不误杀现有场景 — 现有全部场景 (ActionEbAdd 的 flow-context/fixed、
    Condition 上游 paramKey、SendMessage 人员等) 都在白名单内.
    """
    ctype = str(action.get("type") or "")
    params = action.get("params") or {}
    if not isinstance(params, dict):
        return

    # ① 固定值-only 组件: 字段值禁止上下文映射 (mapping).
    if ctype in _CONTEXT_ONLY_FIXED:
        if params.get("mapping"):
            errors.append(
                f"{path}: {ctype} 字段值只支持固定值(constants), 不支持上下文映射(mapping)"
            )
        for d_idx, d_item in enumerate(params.get("detail") or []):
            if isinstance(d_item, dict) and d_item.get("mapping"):
                errors.append(
                    f"{path}: {ctype} detail[{d_idx}] 字段只支持固定值, 不支持上下文映射"
                )

    # ② 无字段映射组件: 不允许 mapping/constants/detail.
    if ctype in _NO_FIELD_MAPPING:
        for key in ("mapping", "constants", "detail"):
            if params.get(key):
                errors.append(
                    f"{path}: {ctype} 无字段映射能力, 不能有 {key}"
                )

    # ③ EventFormData: filterInput 不支持 esbAssign 上下文公式右值.
    if ctype == "EventFormData":
        for cond in (params.get("filter") or []):
            if not isinstance(cond, dict):
                continue
            val = cond.get("value")
            if isinstance(val, str) and (
                "FormData." in val or "[]. " in val or "[].]" in val or val == "{userid}"
            ):
                errors.append(
                    f"{path}: EventFormData filterInput 不支持上下文公式右值(esbAssign), 只能用固定值"
                )

    # ④ SendMessage: 接收人必须是人员上下文对象结构.
    if ctype == "SendMessage":
        to = params.get("to") or params.get("receiver") or {}
        if isinstance(to, str):
            errors.append(
                    f"{path}: SendMessage 接收人必须是人员上下文对象({{type,id,name}} 或 persons 数组), 不能用裸字符串"
            )

_CONTEXT_ONLY_FIXED = frozenset({"MeetingCreate", "ScheduleCreate"})
_NO_FIELD_MAPPING = frozenset({
    "DateTrigger", "SimpleScheduler", "TimeBatchTrigger", "Output",
})

def _walk_actions(actions: list[Any]):
    """Yield main and conditional-branch actions without changing their order."""
    for action in actions or []:
        if not isinstance(action, dict):
            continue
        yield action
        if action.get("type") == "Condition":
            for branch in action.get("branches") or []:
                if isinstance(branch, dict):
                    yield from _walk_actions(branch.get("actions") or [])

def _contains_dynamic_context(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("type") in {"context", "platform_context"}:
            return True
        return any(_contains_dynamic_context(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_dynamic_context(item) for item in value)
    return False

def validate_platform_limitations(draft: dict[str, Any], errors: list[str]) -> None:
    """Reject combinations proven to fail during platform save, before creating an app."""
    event_type = str((draft.get("event") or {}).get("type") or "")
    for index, action in enumerate(_walk_actions(draft.get("actions") or [])):
        action_type = str(action.get("type") or "")
        params = action.get("params") or {}
        path = f"actions[*:{index}]"
        # 真实动作流快照已包含 TimeBatchTrigger → ActionEbUpdate（常见于
        # 查询/循环的子流，也可按当前批次记录的 id 更新）。因此不能再把这
        # 个组件组合做成全局禁用；由 targetForm、opType=id、updateId 的
        # 正常契约校验决定是否可保存。
        if action_type == "ActionEbUpdate" and params.get("opType") == "fieldUpdate":
            errors.append(
                f"{path}: 当前平台 ActionEbUpdate.fieldUpdate 仅回读匹配字段 ID/策略，"
                "不会持久化 updateFieldCondition.updateField[].assign；正式保存回读会丢失右侧条件值。"
                "请使用 updateData + filterCondition。"
            )
        if action_type in _CONTEXT_ONLY_FIXED and _contains_dynamic_context(params):
            errors.append(
                f"{path}: {action_type} 动态上下文赋值尚无该组件的前端控件/DTO/readBack 实证；当前仅支持固定值。"
            )
        if action_type == "EnquiryForm" and str(params.get("opType") or "list") not in {"list", "groupFields"}:
            errors.append(
                f"{path}: EnquiryForm.opType 仅支持 list/groupFields；查询数量请使用 countFlag=true 并读取 Response.response.count。"
            )

def validate_workflow_draft(draft: dict[str, Any]) -> dict[str, Any]:
    contracts, trigger_types, action_types = build_contracts()
    errors: list[str] = []
    warnings: list[str] = []

    event = draft.get("event", {})
    if event.get("id") != "event_1":
        errors.append("event.id should be event_1")
    if event.get("type") not in trigger_types:
        errors.append(f"event.type is not a known trigger: {event.get('type')}")
    validate_params(event, contracts.get(event.get("type")), "event", errors)

    actions = draft.get("actions", [])
    if not actions:
        errors.append("actions must not be empty")
    else:
        validate_action_chain(actions, "actions", errors)
        output_count = sum(1 for action in actions if action.get("type") == "Output")
        if output_count != 1:
            errors.append(f"main actions should contain exactly one Output, got {output_count}")
        if actions[-1].get("type") != "Output":
            errors.append("last main action should be Output")

    for index, action in enumerate(actions):
        path = f"actions[{index}]"
        if action.get("type") not in action_types:
            errors.append(f"{path}: unknown action type {action.get('type')}")
        validate_params(action, contracts.get(action.get("type")), path, errors)
        validate_branch_actions(action, path, action_types, contracts, errors)
        check_context_domains(action, path, errors, warnings)
        if action.get("type") == "Condition" and not action.get("branches"):
            warnings.append(f"{path}: Condition has no branches")

    validate_platform_limitations(draft, errors)

    return {"valid": not errors, "errors": errors, "warnings": warnings}

# ---------------------------------------------------------------------------
# 3. Real platform JSON contract validation (was validate_real_json.py)
# ---------------------------------------------------------------------------

def validate_real_json(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return validate_real_design(json.load(f))

def validate_real_design(d: dict[str, Any]) -> list[str]:
    """校验内存中的真实设计 JSON，供转换器单测和保存前检查复用。"""
    if not isinstance(d, dict):
        return ["real design must be an object"]

    errors = []

    # 1. Top level
    if not isinstance(d.get("appId"), str): errors.append("appId must be string")
    if not isinstance(d.get("sceneId"), str): errors.append("sceneId must be string")
    if not d.get("assistLayer"): errors.append("assistLayer missing")
    try: json.loads(d["assistLayer"])
    except: errors.append("assistLayer not valid JSON")

    # 2. Event
    e = d.get("event", {})
    if not isinstance(e.get("id"), str): errors.append(f"event.id not str: {type(e['id']).__name__}")
    if not isinstance(e.get("wId"), str): errors.append(f"event.wId not str")
    event_type = e.get("type")
    registered_events = {
        component_type
        for component_type, contract in get_registered_components().items()
        if contract.get("nodeRole") == "event"
    }
    if event_type not in registered_events:
        errors.append(f"event.type is not a registered event: {event_type}")
    if "parentId" not in e: errors.append("event missing parentId")
    if "triggerTypeName" not in e: errors.append("event missing triggerTypeName")
    event_data = e.get("data", {})
    if event_type == "ApproveTrigger":
        wp = event_data.get("workflowPath")
        if not isinstance(wp, list): errors.append(f"event.data.workflowPath not list: {type(wp).__name__}")
    elif event_type == "SimpleScheduler":
        if e.get("triggerType") != "TimerTrigger":
            errors.append(f"event.triggerType expected TimerTrigger, got {e.get('triggerType')}")
        if not isinstance(event_data.get("rate"), str):
            errors.append("event.data.rate must be a string")
        if not isinstance(event_data.get("startTime"), str) or not event_data["startTime"]:
            errors.append("event.data.startTime must be a non-empty string")
    # 禁止冗余字段
    for bad in ("nameMultilang", "dataId", "canDelete", "canEdit", "canSwitch", "isOpen"):
        if bad in e: errors.append(f"event has forbidden field: {bad}")

    # 3. Actions
    for i, a in enumerate(d.get("actions", [])):
        p = f"actions[{i}]"
        t = a.get("type", "?")

        # ID checks
        if not isinstance(a.get("id"), str): errors.append(f"{p}.id not str")
        if not isinstance(a.get("wId"), str): errors.append(f"{p}.wId not str")
        if "parentId" not in a: errors.append(f"{p} missing parentId")
        if "componentId" not in a: errors.append(f"{p} missing componentId")
        # 禁止冗余字段
        for bad in ("nameMultilang", "typeName", "canDelete", "canEdit", "canSwitch", "isOpen",
                     "componentName", "componentDesc", "componentNameLabel", "componentDescLabel"):
            if bad in a: errors.append(f"{p} has forbidden field: {bad}")

        ad = a.get("data", {})

        # ActionEbUpdate
        if t == "ActionEbUpdate":
            if "targetForm" not in ad: errors.append(f"{p} missing targetForm")
            tf = ad.get("targetForm", {})
            if tf.get("type") != "FORM": errors.append(f"{p}.targetForm.type != FORM")
            if "ebActionId" not in ad: errors.append(f"{p} missing ebActionId")
            if "person" not in ad and "personId" not in ad: errors.append(f"{p} missing person")
            # person formula
            pform = ad.get("person", {})
            if pform.get("type") != "8": errors.append(f"{p}.person.type expected 8, got {pform.get('type')}")
            pchild = pform.get("childs", [])
            if pchild and int(pchild[0].get("type", 0)) not in (3, 9):
                errors.append(f"{p}.person.child[0].type expected 3|9, got {pchild[0].get('type')}")
            if not isinstance(pchild[0].get("position"), str):
                errors.append(f"{p}.person.child[0].position not str")
            # setting
            setting = ad.get("setting", {})
            sdetail = setting.get("detail")
            if not isinstance(sdetail, list):
                errors.append(f"{p}.setting.detail not list: {type(sdetail).__name__}")
            # updateId (opType=id)
            op_type = ad.get("opType")
            if op_type not in {"id", "updateData", "fieldUpdate"}:
                errors.append(f"{p} invalid opType: {op_type}")
            if op_type == "id" and "updateId" not in ad:
                errors.append(f"{p} opType=id but missing updateId")
            if op_type == "updateData" and not ad.get("filterInput"):
                errors.append(f"{p} opType=updateData but missing filterInput")
            if op_type == "fieldUpdate":
                condition = ad.get("updateFieldCondition")
                rows = condition.get("updateField") if isinstance(condition, dict) else None
                if not isinstance(rows, list) or not rows:
                    errors.append(f"{p} opType=fieldUpdate but missing updateFieldCondition.updateField")
                else:
                    for j, row in enumerate(rows):
                        if not isinstance(row, dict) or not row.get("fieldKey") or not row.get("assign"):
                            errors.append(f"{p}.updateFieldCondition.updateField[{j}] missing fieldKey/assign")
                if ad.get("updatePolicy") not in {"ALL", "FIRST", "LAST", "ZERO", "EXCEPTION"}:
                    errors.append(f"{p} fieldUpdate invalid updatePolicy")

        # SendMessage(真实平台字段名:msgContent/msgTitle/person)
        if t == "SendMessage":
            # channelSetting 是前端可选渠道状态；真实成功节点可缺省，平台使用默认消息渠道。
            # 接收人:person(FormulaBean, type=8 含 child[])
            if "person" not in ad: errors.append(f"{p} missing person")
            # 正文:必填 msgContent
            if "msgContent" not in ad: errors.append(f"{p} missing msgContent")
            # 标题:可选(平台默认填充"通知"),不做强校验
            if ad.get("msgId") != -1: errors.append(f"{p}.msgId expected -1")

        # Condition
        if t == "Condition":
            if "trueBranchActions" not in ad:
                errors.append(f"{p} missing trueBranchActions")
            if "falseBranchActions" not in ad:
                errors.append(f"{p} missing falseBranchActions")
            detail = ad.get("conditionDetail")
            if ad.get("trueBranchActions") and not isinstance(detail, dict):
                errors.append(f"{p} true branch requires conditionDetail")
            if isinstance(detail, dict):
                if not detail.get("conditionId"):
                    errors.append(f"{p}.conditionDetail missing conditionId")
                if not detail.get("conditionDataJson"):
                    errors.append(f"{p}.conditionDetail missing conditionDataJson")

            for branch_key in ("trueBranchActions", "falseBranchActions"):
                branch_actions = ad.get(branch_key, [])
                if not isinstance(branch_actions, list):
                    errors.append(f"{p}.{branch_key} must be an array")
                    continue
                for branch_index, branch_action in enumerate(branch_actions):
                    bp = f"{p}.{branch_key}[{branch_index}]"
                    if not isinstance(branch_action, dict):
                        errors.append(f"{bp} must be an action object")
                        continue
                    if branch_action.get("type") == "Output":
                        errors.append(f"{bp} must not contain Output")
                    if not isinstance(branch_action.get("wId"), str):
                        errors.append(f"{bp}.wId not str")
                    if branch_index == 0:
                        continue
                    sources = branch_action.get("sources", [])
                    expected = branch_actions[branch_index - 1].get("wId")
                    if not any(str(item.get("wId")) == str(expected) for item in sources if isinstance(item, dict)):
                        errors.append(f"{bp} does not link to prior branch action")

        # Output
        if t == "Output":
            if not (isinstance(a.get("id"), str) and a.get("parentId") == "0" and "componentId" in a):
                errors.append(f"{p} missing required fields: id(parentId/componentId)")

        # 禁止 action.data 中有 personId
        if "personId" in ad and t != "ActionEbUpdate":
            errors.append(f"{p} has unexpected personId")

    # 全树契约:所有 id 类字段(id/wId/componentId)均必须为字符串.
    _check_ids_str(d, "root", errors)

    return errors

def _check_ids_str(obj, path: str, errors: list) -> None:
    ID_KEYS = ("id", "wId", "componentId", "parentId", "parentNode", "frontId")
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ID_KEYS and not isinstance(v, str):
                errors.append(f"{path}.{k} not str: {type(v).__name__}")
            _check_ids_str(v, f"{path}.{k}" if k not in ID_KEYS else path, errors)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _check_ids_str(item, f"{path}[{i}]", errors)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python validate.py <generated.json>  [mode: real|semantic|draft]")
        sys.exit(1)

    mode = sys.argv[1]
    path = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]
    if mode in ("semantic", "draft"):
        pass
    elif mode == "real" and len(sys.argv) > 2:
        path = sys.argv[2]
    else:
        mode, path = "real", sys.argv[1]

    if mode == "real":
        errs = validate_real_json(path)
        if errs:
            print(f"❌ {len(errs)} errors:")
            for e in errs:
                print(f"  - {e}")
            sys.exit(1)
        print("✅ All checks passed")
    else:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        result = validate_semantic_plan(doc) if mode == "semantic" else validate_workflow_draft(doc)
        print(json.dumps(result, ensure_ascii=False, indent=2))
