"""按节点顺序填充动作流并累积上下文.

模型负责先确定骨架和当前节点参数;本模块负责在每个节点填充后查询其
getComponentContext 输出,并把可用引用累积给后续节点.它不生成平台保存 JSON.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from core.context_provider import ContextStore, get_component_context, get_context_provider

def _provider_config(payload: dict[str, Any]) -> dict[str, Any]:
    config = payload.get("contextProvider", {})
    if not isinstance(config, dict):
        raise ValueError("contextProvider must be an object")
    return {"source": payload.get("contextSource", "platform"), **config}

def _reference_summary(result: dict[str, Any]) -> list[dict[str, Any]]:
    return result.get("availableReferences", []) if isinstance(result, dict) else []

def fill_node_context(payload: dict[str, Any]) -> dict[str, Any]:
    """填充单个节点后查询上下文,并返回供下一节点使用的 Store.

    这是模型实际执行逐节点循环的入口:模型拿到返回的
    ``availableReferences`` 后,再决定下一个节点的 params.
    """
    node = payload.get("node")
    if not isinstance(node, dict) or not isinstance(node.get("type"), str):
        raise ValueError("node must be an object with a component type")
    params = node.get("params", {})
    if not isinstance(params, dict):
        raise ValueError("node.params must be an object")

    provider_config = _provider_config(payload)
    provider = get_context_provider(provider_config)
    store_data = payload.get("store", {})
    if not isinstance(store_data, dict):
        raise ValueError("store must be an object")
    store = ContextStore(store_data)

    platform_data = payload.get("platformData")
    if not isinstance(platform_data, dict):
        return {
            "node": deepcopy(node),
            "context": {},
            "availableReferences": [],
            "contextStore": store.as_dict(),
            "error": "必须提供 platformData(前端 getComponentContext 的完整 data 对象)",
        }

    query_result = get_component_context(node["type"], platform_data, store, provider)
    context = query_result.get("context", {})
    if isinstance(context, dict) and not context.get("error"):
        store.merge(context, node["type"])

    return {
        "node": deepcopy(node),
        "context": context,
        "availableReferences": _reference_summary(query_result),
        "contextStore": store.as_dict(),
    }
