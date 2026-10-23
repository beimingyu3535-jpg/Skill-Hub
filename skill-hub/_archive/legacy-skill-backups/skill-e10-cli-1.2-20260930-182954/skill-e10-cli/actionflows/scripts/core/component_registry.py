from __future__ import annotations

from copy import deepcopy
from typing import Any

# ── 组件注册中心桥接 ──
# 所有组件数据从 scripts/components/ 注册中心读取,不再依赖 JSON 文件.

def _lazy_registry() -> dict[str, Any]:
    """延迟导入注册中心，避免循环依赖。"""
    from components import get_all
    return get_all()

def load_component_registry() -> dict[str, Any]:
    """返回 {components: {type: {...}}} 兼容旧接口。"""
    return {"components": _lazy_registry()}

def get_registered_components() -> dict[str, Any]:
    return _lazy_registry()

def get_component_contracts(component_types: list[str]) -> dict[str, Any]:
    registry = load_component_registry()["components"]
    components = {
        component_type: deepcopy(registry[component_type])
        for component_type in component_types
        if component_type in registry
    }
    unknown_types = [component_type for component_type in component_types if component_type not in registry]
    return {"components": components, "unknownTypes": unknown_types}


def search_component_catalog(query: str, node_role: str | None = None, limit: int = 8) -> dict[str, Any]:
    """返回轻量候选组件；完整参数仍由 get_component_contracts 提供。"""
    from components import search
    return {"candidates": search(query, node_role=node_role, limit=limit)}

def has_concrete_value(value: Any) -> bool:
    return value not in (None, "", [], {})

def has_required_shape(value: Any, definition: dict[str, Any]) -> bool:
    value_shape = definition.get("valueShape")
    if value_shape == "object":
        return isinstance(value, dict)
    if value_shape == "array":
        return isinstance(value, list)
    return True

def has_valid_items(value: Any, definition: dict[str, Any]) -> bool:
    item_schema = definition.get("itemSchema")
    if not isinstance(item_schema, dict):
        return True
    required_keys = item_schema.get("requiredKeys")
    if not isinstance(value, list) or not isinstance(required_keys, list):
        return False
    return all(
        isinstance(item, dict) and all(has_concrete_value(item.get(key)) for key in required_keys)
        for item in value
    )

def validate_provided_param(value: Any, definition: dict[str, Any]) -> list[str]:
    """Validate a supplied semantic value against a registry parameter contract.

    Missing values are intentionally valid here: the compiler turns those into
    ``missingFields``. This function only rejects values the model *did* supply
    but that cannot satisfy the declared contract.
    """
    if not has_concrete_value(value):
        return []

    errors: list[str] = []
    value_shape = definition.get("valueShape")
    if value_shape == "object" and not isinstance(value, dict):
        errors.append("must be an object")
    elif value_shape == "array" and not isinstance(value, list):
        errors.append("must be an array")

    if value_shape == "array" and isinstance(value, list) and not has_valid_items(value, definition):
        errors.append("contains an item without the required fields")

    value_type = definition.get("valueType")
    if value_type == "enum":
        allowed_values = {option["value"] for option in definition.get("options", [])}
        if value not in allowed_values:
            errors.append(f"must be one of {sorted(allowed_values)}")
    elif value_type == "string" and not isinstance(value, str):
        errors.append("must be a string")
    elif value_type == "boolean" and not isinstance(value, bool):
        errors.append("must be a boolean")
    elif value_type == "array" and not isinstance(value, list):
        errors.append("must be an array")

    return errors

def validate_assignment_value(value: Any) -> list[str]:
    """Validate the stable semantic form of one dynamic assignment value.

    Platform FormulaBean is deliberately not accepted here. The model supplies
    a scalar, a resolved context object, or one of the documented semantic
    assignment kinds; ``draft_to_real.py`` owns the platform-specific tree.
    """
    value = normalize_assignment_value(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return []
    if not isinstance(value, dict):
        return ["must be a scalar, a resolved reference, or an assignment object"]

    # Keep a raw reference legal for callers that validate before resolve.
    if set(value) == {"$ref"} and isinstance(value["$ref"], dict):
        return []

    kind = value.get("kind")
    if kind in {"fixed", "literal"}:
        return [] if "value" in value else ["fixed assignment must contain value"]
    if kind in {"context", "system_variable"}:
        return [] if isinstance(value.get("key"), str) and value["key"] else [f"{kind} assignment must contain key"]
    if kind in {"constant", "transform", "formula"}:
        errors = []
        if not isinstance(value.get("id"), str) or not value["id"]:
            errors.append(f"{kind} assignment must contain id")
        if kind in {"transform", "formula"} and "arguments" in value and not isinstance(value["arguments"], list):
            errors.append(f"{kind}.arguments must be an array after resolution")
        return errors

    # Resolved context values have a key but do not need assignmentKind.
    if isinstance(value.get("key"), str) and value["key"]:
        return []
    # A literal wrapper is also accepted, including enum {label, value}.
    if "value" in value and not isinstance(value["value"], (dict, list)):
        return []
    return ["does not match a supported assignment value shape"]

def enrich_assignment_plans(component_type: str, param_key: str, value: Any, warnings: list[str]) -> Any:
    if component_type not in {"ActionEbUpdate", "ActionEbAdd"} or param_key not in {"updates", "setting"}:
        return value
    if not isinstance(value, list):
        return value

    enriched: list[dict[str, Any]] = []
    for index, item in enumerate(normalize_assignment_items(value)):
        if not isinstance(item, dict) or "value" not in item:
            return value
        updated_item = deepcopy(item)
        updated_item["value"] = normalize_assignment_value(updated_item["value"])
        try:
            updated_item["assignmentPlan"] = build_assignment_plan(updated_item["value"])
        except ValueError as exc:
            warnings.append(f"{component_type}.{param_key}[{index}] 动态赋值计划无法生成:{exc}")
        enriched.append(updated_item)
    return enriched

def is_required(definition: dict[str, Any], source_params: dict[str, Any]) -> bool:
    if definition.get("required"):
        return True

    required_when = definition.get("requiredWhen")
    if not isinstance(required_when, dict):
        return False

    dependency = required_when.get("param")
    if not isinstance(dependency, str):
        return False
    if "equals" in required_when:
        return source_params.get(dependency) == required_when["equals"]
    if "in" in required_when:
        expected_values = required_when["in"]
        return isinstance(expected_values, list) and source_params.get(dependency) in expected_values
    return False

def normalize_node_with_contract(node: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(node)
    component_type = normalized.get("type")
    contract = load_component_registry()["components"].get(component_type)
    normalized.setdefault("params", {})
    normalized.setdefault("missingFields", [])
    normalized.setdefault("warnings", [])

    if not contract:
        return normalized

    source_params = normalized["params"] if isinstance(normalized["params"], dict) else {}
    params: dict[str, Any] = {}
    missing_fields = list(dict.fromkeys(normalized["missingFields"]))
    warnings = list(dict.fromkeys(normalized["warnings"]))

    for key, definition in contract["params"].items():
        value = source_params.get(key)
        if component_type in {"ActionEbUpdate", "ActionEbAdd"} and key in {"updates", "setting"}:
            value = normalize_assignment_items(value)
        if not has_concrete_value(value) and "default" in definition:
            value = deepcopy(definition["default"])

        if has_concrete_value(value) and not has_required_shape(value, definition):
            warnings.append(f"{component_type}.{key} 参数格式无效:需要 {definition['valueShape']}")
            value = None

        if has_concrete_value(value) and not has_valid_items(value, definition):
            warnings.append(f"{component_type}.{key} 参数项格式无效")
            value = None

        if has_concrete_value(value):
            value = enrich_assignment_plans(component_type, key, value, warnings)

        if has_concrete_value(value) and definition.get("valueType") == "enum":
            options = {option["value"] for option in definition.get("options", [])}
            if value not in options:
                warnings.append(f"{component_type}.{key} 枚举值无效:{value}")
                value = None

        if has_concrete_value(value):
            params[key] = value
            missing_fields = [field for field in missing_fields if field != key]
        elif is_required(definition, source_params) and key not in missing_fields:
            missing_fields.append(key)

    for key in source_params:
        if key not in contract["params"]:
            warnings.append(f"{component_type}.{key} 不在当前简化组件契约中,已忽略")

    normalized["params"] = params
    normalized["missingFields"] = missing_fields
    normalized["warnings"] = warnings
    return normalized

# ---------------------------------------------------------------------------
# Assignment adapter (merged from assignment_adapter.py)
# ---------------------------------------------------------------------------

ASSIGNMENT_ENGINE_TYPES = {
    "fixed": "1",
    "context": "3",
    "transform": "4",
    "constant": "5",
    "formula": "6",
    # The current ESB frontend uses 9; older formula-engine documentation uses 2.
    "system_variable": "9",
}

def normalize_assignment_items(value: Any) -> Any:
    """归一 ActionEbAdd.setting / ActionEbUpdate.updates 的每项字段别名。"""
    if not isinstance(value, list):
        return value
    normalized: list[Any] = []
    for item in value:
        if not isinstance(item, dict):
            normalized.append(item)
            continue
        updated = deepcopy(item)
        if "field" not in updated and isinstance(updated.get("formField"), dict):
            updated["field"] = deepcopy(updated["formField"])
        if "value" in updated:
            updated["value"] = normalize_assignment_value(updated["value"])
        normalized.append(updated)
    return normalized

def normalize_assignment_value(value: Any) -> Any:
    """将 AI 友好的动态赋值写法归一为唯一语义契约。

    对外推荐 ``{kind:"context", key:"真实 paramKey"}``。为兼容早期文档
    和已生成计划，也接受 ``type:"context"``、``paramKey``；归一后不会
    被转换器误判为固定值。
    """
    if not isinstance(value, dict):
        return value
    normalized = deepcopy(value)
    supported = set(ASSIGNMENT_ENGINE_TYPES) | {"literal"}
    kind = normalized.get("assignmentKind") or normalized.get("kind")
    if not kind and normalized.get("type") in supported:
        kind = normalized["type"]
    if isinstance(kind, str) and kind:
        normalized["kind"] = kind
    if normalized.get("kind") in {"context", "system_variable"}:
        key = normalized.get("key") or normalized.get("paramKey") or normalized.get("fieldKey")
        if isinstance(key, str) and key:
            normalized["key"] = key
    return normalized

def to_formula_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)

def build_assignment_plan(value: Any) -> dict[str, Any]:
    """Build a simplified assignment plan without platform-generated IDs."""
    value = normalize_assignment_value(value)
    if isinstance(value, dict) and isinstance(value.get("kind"), str):
        kind = value["kind"]
        if kind == "context":
            key = value.get("key")
            if not isinstance(key, str) or not key:
                raise ValueError("context assignment must contain key")
            return {
                "kind": kind,
                "type": ASSIGNMENT_ENGINE_TYPES[kind],
                "name": value.get("label", value.get("name", key)),
                "value": key,
                "resultType": value.get("valueType", "string"),
                "sourceRef": {"kind": "trigger_context", "key": key},
            }

        if kind in {"fixed", "literal"}:
            if "value" not in value:
                raise ValueError("fixed assignment must contain value")
            fixed_value = value["value"]
            if fixed_value is None or isinstance(fixed_value, (dict, list)):
                raise ValueError("fixed assignment value must be a scalar")
            return {
                "kind": "fixed",
                "type": "1",
                "name": to_formula_value(value.get("label", fixed_value)),
                "value": to_formula_value(fixed_value),
                "formulaType": "string",
                "config": {"switchType": "fixvalue", "originValue": fixed_value},
            }
        if kind == "system_variable":
            key = value.get("key")
            if not isinstance(key, str) or not key:
                raise ValueError("system variable must contain key")
            return {
                "kind": kind,
                "type": ASSIGNMENT_ENGINE_TYPES[kind],
                "name": value.get("name", key),
                "value": key,
                "resultType": value.get("valueType", "string"),
                "sourceRef": {"kind": kind, "key": key},
            }

        if kind == "constant":
            reference_id = value.get("id")
            if not isinstance(reference_id, str) or not reference_id:
                raise ValueError("constant must contain id")
            return {
                "kind": kind,
                "type": ASSIGNMENT_ENGINE_TYPES[kind],
                "name": value.get("name", reference_id),
                "value": reference_id,
                "resultType": value.get("valueType", "string"),
                "sourceRef": {"kind": kind, "id": reference_id},
            }

        if kind in {"transform", "formula"}:
            reference_id = value.get("id")
            arguments = value.get("arguments")
            if not isinstance(reference_id, str) or not reference_id:
                raise ValueError(f"{kind} must contain id")
            if not isinstance(arguments, list):
                raise ValueError(f"{kind} must contain resolved arguments")
            argument_plans: list[dict[str, Any]] = []
            for index, argument in enumerate(arguments):
                if not isinstance(argument, dict) or not isinstance(argument.get("name"), str) or "value" not in argument:
                    raise ValueError(f"{kind}.arguments[{index}] must contain name and value")
                argument_plans.append(
                    {
                        "name": argument["name"],
                        "assignment": build_assignment_plan(argument["value"]),
                    }
                )
            return {
                "kind": kind,
                "type": ASSIGNMENT_ENGINE_TYPES[kind],
                "name": value.get("name", reference_id),
                "value": reference_id,
                "resultType": value.get("valueType", "string"),
                "arguments": argument_plans,
                "sourceRef": {"kind": kind, "id": reference_id},
            }

        raise ValueError(f"unsupported assignmentKind: {kind}")

    if isinstance(value, dict) and isinstance(value.get("key"), str):
        return {
            "kind": "context",
            "type": "3",
            "name": value.get("label", value["key"]),
            "value": value["key"],
            "resultType": value.get("valueType", "string"),
            "sourceRef": {"kind": "trigger_context", "key": value["key"]},
        }

    if isinstance(value, dict) and "value" in value:
        fixed_value = value["value"]
        name = value.get("label", fixed_value)
    else:
        fixed_value = value
        name = value

    if fixed_value is None or isinstance(fixed_value, (dict, list)):
        raise ValueError("assignment value must be a scalar or a resolved trigger context")

    formula_value = to_formula_value(fixed_value)
    return {
        "kind": "fixed",
        "type": "1",
        "name": to_formula_value(name),
        "value": formula_value,
        "formulaType": "string",
        "config": {
            "switchType": "fixvalue",
            "originValue": fixed_value,
        },
    }

def adapt_updates(updates: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(updates, list):
        raise ValueError("updates must be an array")
    plans: list[dict[str, Any]] = []
    for index, update in enumerate(updates):
        if not isinstance(update, dict) or "field" not in update or "value" not in update:
            raise ValueError(f"updates[{index}] must contain field and value")
        plans.append({"field": update["field"], "assignment": build_assignment_plan(update["value"])})
    return {"assignments": plans}
