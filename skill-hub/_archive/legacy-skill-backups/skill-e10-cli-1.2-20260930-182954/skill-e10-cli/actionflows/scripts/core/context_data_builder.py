"""getComponentContext 请求 data 的构造。"""
from __future__ import annotations

from typing import Any, Callable

def build_component_context_data(
    component_type: str,
    params: dict[str, Any],
    current_application: str,
    *,
    event_node_id: str = "",
    data_mapper: Callable[..., dict] | None = None,
) -> dict[str, Any]:
    """生成调用 getComponentContext 所需的完整前端节点 ``data``.

    参数中的流程、表单、字段必须已经由实时浏览接口解析.这里不访问目录、
    不猜字段,只复用真实设计 JSON 转换器的 data 映射补全 person、targetForm、
    tableType、appType 和 setting 等前端所需结构.
    """
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    if not current_application:
        raise ValueError("currentApplication is required before querying component context")

    target_form = params.get("targetForm")
    forms = [target_form] if isinstance(target_form, dict) else []
    metadata = {
        "forms": forms,
        # preflight 逐节点查询时尚未生成最终事件 wId，先使用编译器事件别名；
        # 最终 convert 会替换为真实事件节点 id。
        "_upstream_w_id": str(event_node_id or "event"),
    }
    if data_mapper is None:
        raise ValueError("data_mapper is required")
    data = data_mapper(
        params,
        component_type,
        metadata,
        str(current_application),
        event_node_id=str(event_node_id),
    )
    data["currentApplication"] = str(current_application)
    data["applicationId"] = str(current_application)
    data["type"] = component_type
    return data
