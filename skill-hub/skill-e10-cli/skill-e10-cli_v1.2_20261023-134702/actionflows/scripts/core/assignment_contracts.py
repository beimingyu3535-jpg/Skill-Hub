"""动态赋值的组件合同与保存前审计。

这里不生成平台 JSON；只把前端 AssignSwitch 和后端 FormulaBean 的共同契约固化为
可执行校验，防止某个场景的兼容代码悄悄污染其它组件。
"""

from __future__ import annotations

from typing import Any, Iterator

# 当前已登记组件的能力边界。没有在这里声明 context 的字段，转换器不得把语义对象
# stringify 后伪装成固定值。
ASSIGNMENT_CAPABILITIES: dict[str, dict[str, Any]] = {
    "ActionEbAdd": {"formMapping": "type3", "detailMapping": "type10", "context": True},
    "ActionEbUpdate": {
        "formMapping": "type3", "detailMapping": "type10", "context": True,
        # 当前运行平台 fieldUpdate 保存后不回读每行 assign，仅保存字段 ID/策略；
        # 因而不能把这个前端展示模式暴露为可生成能力。
        "unsupportedModes": {"fieldUpdate"},
    },
    "ApproveCreate": {"formMapping": "type3", "detailMapping": "type10", "context": True},
    "SendMessage": {"contextFields": {"msgTitle", "msgContent", "pcLink", "mobileLink"}},
    "EnquiryForm": {"contextFields": {"filterInput"}, "fixedOnly": {"person", "formPageNo", "formPageSize"}},
    "ScheduleCreate": {"fixedOnly": {"creatorUser", "managerFormulaId", "participants", "title", "startTime", "endTime", "content"}},
    "MeetingCreate": {"fixedOnly": {"setting", "flag"}},
}

_ASSIGN_SWITCH_FIXED_FIELDS: dict[str, set[str]] = {
    "ApproveCreate": {"requestName"},
    "ScheduleCreate": {"title", "startTime", "endTime", "content"},
    "SendMessage": {"msgTitle", "msgContent", "pcLink", "mobileLink"},
}

def _walk(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)

def _is_context_formula(value: dict[str, Any]) -> bool:
    return str(value.get("type")) in {"3", "10"} and isinstance(value.get("config"), dict) \
        and value["config"].get("switchType") in {"assign", "sub"}


def _is_fixed_formula(value: dict[str, Any]) -> bool:
    return str(value.get("type")) == "1"


def _config_as_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            import json
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else None
        except (TypeError, ValueError):
            return None
    return None

def audit_dynamic_assignments(design: dict[str, Any]) -> tuple[list[str], list[str]]:
    """校验已转换的动态 FormulaBean 是否仍能被设计器解析。

    仅检查本 Skill 生成的 context/type=3、依据值下级/type=10。固定值、函数、
    Browser/Upload 对象和平台未知原生结构不做猜测或重写。
    """
    errors: list[str] = []
    warnings: list[str] = []
    nodes: dict[str, dict[str, Any]] = {}
    event = design.get("event") if isinstance(design, dict) else None
    if isinstance(event, dict):
        for key in ("id", "wId"):
            if event.get(key):
                nodes[str(event[key])] = event
    for node in (design.get("actions") or []) if isinstance(design, dict) else []:
        if not isinstance(node, dict):
            continue
        for key in ("id", "wId"):
            if node.get(key):
                nodes[str(node[key])] = node

    for node in ([event] if isinstance(event, dict) else []) + [n for n in (design.get("actions") or []) if isinstance(n, dict)]:
        node_type = str(node.get("type") or "")
        data = node.get("data") if isinstance(node.get("data"), dict) else {}
        for formula in _walk(data):
            if _is_fixed_formula(formula):
                # 非 AssignSwitch 字段的固定 FormulaBean 由各后端 DTO 自己解释；
                # 不做全局 UI 格式改写或拦截，避免误伤已验证的组件数据。
                continue
            if not _is_context_formula(formula):
                continue
            config = formula["config"]
            label = str(formula.get("name") or "").strip()
            param_key = str(config.get("paramKey") or formula.get("paramKey") or "")
            switch = str(config.get("switchType"))
            source_id = str(config.get("comId") or formula.get("source") or "")
            source_node = nodes.get(source_id)

            if not label:
                errors.append(f"{node_type}: 动态赋值缺少显示名称 (paramKey={param_key})")
            elif label == param_key or (label.isdigit() and len(label) >= 8):
                errors.append(f"{node_type}: 动态赋值显示名称退化为字段ID ({label})")

            if not param_key:
                errors.append(f"{node_type}: 动态赋值缺少 paramKey")
            if switch == "assign":
                if not str(formula.get("value") or "").startswith(("FormData.", "ApprovalData.", "CycleParams.")):
                    errors.append(f"{node_type}: 动态赋值 value 不是可识别上下文路径 ({formula.get('value')})")
                if formula.get("formulaType") and config.get("paramType") and str(formula["formulaType"]) != str(config["paramType"]):
                    errors.append(f"{node_type}: 动态赋值 formulaType 与 paramType 不一致 ({formula['formulaType']} != {config['paramType']})")

            if source_node:
                expected_type = str(source_node.get("type") or "")
                actual_type = str(config.get("comType") or "")
                if actual_type and expected_type and actual_type != expected_type:
                    errors.append(
                        f"{node_type}: 动态赋值来源组件错误 (comId={source_id}, comType={actual_type}, 应为{expected_type})"
                    )
            elif source_id:
                warnings.append(f"{node_type}: 动态赋值来源节点未在当前设计找到，未校验 comType (comId={source_id})")

            if switch == "sub" and "[]" not in param_key:
                errors.append(f"{node_type}: 依据值下级必须引用明细 paramKey (缺少[])" )

        # 这些页面的 AssignSwitch 直接读取 FormulaBean.config.switchType；只对
        # 固定 type=1 做对象要求，type=3/type=10 动态引用保持其既有结构。
        for field_name in _ASSIGN_SWITCH_FIXED_FIELDS.get(node_type, set()):
            formula = data.get(field_name)
            if not isinstance(formula, dict) or str(formula.get("type")) != "1":
                continue
            config = formula.get("config")
            if not isinstance(config, dict) or config.get("switchType") != "fixvalue":
                errors.append(f"{node_type}.{field_name}: 固定值必须使用 config 对象且 switchType=fixvalue，否则会显示为动态赋值")
        if node_type == "MeetingCreate":
            for formula in (data.get("setting") or {}).values() if isinstance(data.get("setting"), dict) else ():
                if isinstance(formula, dict) and str(formula.get("type")) == "1":
                    config = formula.get("config")
                    if not isinstance(config, dict) or config.get("switchType") != "fixvalue":
                        errors.append("MeetingCreate.setting: 固定值必须使用 config 对象且 switchType=fixvalue，否则会显示为动态赋值")
    return errors, warnings
