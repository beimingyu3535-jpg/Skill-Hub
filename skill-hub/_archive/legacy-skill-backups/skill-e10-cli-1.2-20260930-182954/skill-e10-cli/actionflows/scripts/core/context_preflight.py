"""上下文引用校验与节点上下文查询。"""
from __future__ import annotations

from typing import Any

from core.context_provider import ContextStore, PlatformContextProvider, get_component_context
from core.context_data_builder import build_component_context_data
from core.draft_to_real import map_draft_data

def _context_keys(value: Any) -> set[str]:
    """收集语义参数中显式声明的上下文引用键。"""
    keys: set[str] = set()
    if isinstance(value, list):
        for item in value:
            keys.update(_context_keys(item))
    elif isinstance(value, dict):
        ref_type = str(value.get("type", "")).casefold()
        if ref_type in {"context", "platform_context"} or "paramKey" in value:
            key = value.get("paramKey", value.get("key"))
            if isinstance(key, str) and key.strip():
                keys.add(key.strip())
        for item in value.values():
            keys.update(_context_keys(item))
    return keys

def _has_context_key(store: ContextStore, key: str) -> bool:
    values = store.as_dict()
    return key in values or f"FormData.{key}" in values or (
        key.startswith("FormData.") and key.removeprefix("FormData.") in values
    )

def _edit_distance(a: str, b: str, cap: int = 3) -> int:
    """莱文斯坦距离(截断版), 中文短串足够用."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    dp = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev = dp[0]
        dp[0] = i
        for j, cb in enumerate(b, 1):
            cur = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (ca != cb))
            prev = cur
    return dp[-1]

def _similar_context_keys(key: str, store: ContextStore) -> list[str]:
    """从上下文里找与未解析引用相似的字段名, 给 AI/用户修正建议."""
    values = store.as_dict()
    candidates: set[str] = set()
    for k in values:
        if not isinstance(k, str) or k.startswith("_source_"):
            continue
        candidates.add(k.removeprefix("FormData.") if k.startswith("FormData.") else k)
    scored: list[tuple[int, str]] = []
    for c in candidates:
        if not c or c == key:
            continue
        if key in c or c in key:          # 包含关系: 中文名最常见
            scored.append((0, c))
        else:
            d = _edit_distance(key, c)
            if d <= 2:
                scored.append((d, c))
    seen: set[str] = set()
    top: list[str] = []
    for _, c in sorted(scored, key=lambda x: (x[0], x[1])):
        if c not in seen:
            seen.add(c)
            top.append(c)
        if len(top) >= 3:
            break
    return top

def _validate_references(node: dict[str, Any], store: ContextStore, path: str) -> list[str]:
    errors: list[str] = []
    params = node.get("params", {})
    for key in sorted(_context_keys(params)):
        if not _has_context_key(store, key):
            similar = _similar_context_keys(key, store)
            hint = f" (相似: {', '.join(similar)})" if similar else ""
            errors.append(f"{path}: unresolved context reference '{key}'{hint}")
    if node.get("type") == "Condition":
        for index, branch in enumerate(node.get("branches", [])):
            condition = branch.get("condition", {}) if isinstance(branch, dict) else {}
            if isinstance(condition, dict) and condition.get("type") != "else":
                for key in sorted(_context_keys(condition)):
                    if not _has_context_key(store, key):
                        similar = _similar_context_keys(key, store)
                        hint = f" (相似: {', '.join(similar)})" if similar else ""
                        errors.append(f"{path}.branches[{index}]: unresolved context reference '{key}'{hint}")
    return errors

def _query_node_context(
    node: dict[str, Any], *, app_id: str, event_node_id: str, store: ContextStore,
    provider: PlatformContextProvider, path: str,
) -> dict[str, Any]:
    errors = _validate_references(node, store, path)
    if errors:
        return {"errors": errors, "context": {}}
    data = build_component_context_data(
        str(node["type"]), node.get("params", {}), app_id, event_node_id=event_node_id,
        data_mapper=map_draft_data,
    )
    result = get_component_context(str(node["type"]), data, store, provider)
    context = result.get("context", {})
    if isinstance(context, dict):
        store.merge(context, str(node["type"]))
    # EnquiryForm 的运行时真实响应包含 Response.response.count；把它和兼容别名
    # 注册为可引用上下文。最终能否被 Condition 保存仍由租户的 saveCondition
    # 契约决定，失败必须阻断，不得把它降级成流程字段。
    if node.get("type") == "EnquiryForm":
        count_context = {
            # 后端真实响应是 Response.response.count；保留 count 别名兼容旧 plan。
            "response.count": {
                "key": "response.count", "label": "查询结果数量", "name": "count",
                "type": "number", "value": "response.count", "component": "EnquiryForm",
                "sourceType": "enquiry_count",
            },
            "count": {
                "key": "count", "label": "查询结果数量", "name": "count",
                "type": "number", "value": "response.count", "component": "EnquiryForm",
                "sourceType": "enquiry_count", "aliasOf": "response.count",
            },
        }
        store.merge(count_context, "EnquiryForm")
        if not isinstance(context, dict):
            context = {}
        context.update(count_context)
    return {"errors": [], "context": context}
