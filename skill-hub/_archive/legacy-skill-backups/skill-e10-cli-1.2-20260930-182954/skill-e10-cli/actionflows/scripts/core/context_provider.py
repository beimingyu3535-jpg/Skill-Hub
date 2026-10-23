"""真实 Weaver 组件上下文查询.

本模块只调用 ``getComponentContext``.调用前必须把简化参数转换为当前
设计器节点的完整 ``data``,平台返回的 ``paramKey`` 才是后续动态赋值可用
的真实引用,不能由模型自行拼接.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.platform_client import PlatformAuthError, PlatformRequestError, make_client

COMPONENT_OUTPUTS: dict[str, dict[str, Any]] = {
    "ApproveTrigger": {"outputs": ["FormData", "申请人", "流程执行人"], "triggerContext": True},
    "ActionEbUpdate": {"outputs": ["FormData", "FormField", "SettingInfo", "accessId", "monitorId"]},
    "ActionEbAdd": {"outputs": ["FormData", "FormField", "SettingInfo", "accessId", "monitorId"]},
    "ActionEbDelete": {"outputs": ["SettingInfo", "rpcRequestData", "resultMap"]},
    "SendMessage": {"outputs": ["Request", "ImSendReceiverCheck"]},
    "Condition": {"outputs": ["conditionResult"]},
    "Output": {"outputs": []},
}

class ContextUnavailableError(RuntimeError):
    """真实上下文接口不可用."""

class ContextStore:
    """保存每个已填节点返回的真实上下文,供后续节点选择引用."""

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._store = dict(initial) if initial else {}

    def merge(self, context: dict[str, Any], component_name: str = "") -> None:
        for key, value in context.items():
            self._store[key] = value
            self._store[f"_source_{key}"] = component_name

    def list_all(self) -> list[dict[str, Any]]:
        return [
            {
                "key": key,
                "value": value if not isinstance(value, dict) else "<object>",
                "type": type(value).__name__,
                "source": self._store.get(f"_source_{key}", ""),
            }
            for key, value in self._store.items()
            if not key.startswith("_source_")
        ]

    def as_dict(self) -> dict[str, Any]:
        return {key: value for key, value in self._store.items() if not key.startswith("_source_")}

class ContextProvider(ABC):
    @abstractmethod
    def get_context(self, component_type: str, data: dict[str, Any]) -> dict[str, Any]:
        ...

class PlatformContextProvider(ContextProvider):
    """使用环境文件中的会话直接调用真实平台接口."""

    def __init__(self, client=None) -> None:
        self.client = client or make_client()

    def get_context(self, component_type: str, data: dict[str, Any]) -> dict[str, Any]:
        try:
            raw = self.client.get_component_context(component_type, data)
            if isinstance(raw, dict) and (raw.get("code") != 200 or raw.get("status") is False):
                raise ContextUnavailableError(
                    f"getComponentContext failed: code={raw.get('code')}, msg={raw.get('msg', '')}"
                )
            return _parse_platform_context(raw, component_type)
        except (PlatformAuthError, PlatformRequestError) as exc:
            raise ContextUnavailableError(str(exc)) from exc

def get_context_provider(config: dict[str, Any] | None = None) -> ContextProvider:
    config = config or {}
    if config.get("source", "platform") != "platform":
        raise ValueError("only source='platform' is supported")
    return PlatformContextProvider()

def get_component_context(
    component_type: str,
    data: dict[str, Any],
    store: ContextStore | None = None,
    provider: ContextProvider | None = None,
) -> dict[str, Any]:
    """查询完整前端节点 data 对应的真实下游引用."""
    if not isinstance(data, dict):
        raise ValueError("component context data must be an object")
    provider = provider or get_context_provider()
    context = provider.get_context(component_type, data)
    return {
        "context": context,
        "component": component_type,
        "availableReferences": [
            {
                "key": key,
                "label": value.get("label", value.get("name", key)) if isinstance(value, dict) else key,
                "type": value.get("type", "unknown") if isinstance(value, dict) else type(value).__name__,
                "value": value.get("value", "") if isinstance(value, dict) else "",
            }
            for key, value in context.items()
            if not key.startswith("_")
        ],
    }

def _parse_platform_context(raw: Any, component_type: str) -> dict[str, Any]:
    """保留平台分组和真实 paramKey,并展开为可选引用."""
    data = raw.get("data", raw) if isinstance(raw, dict) else raw
    context: dict[str, Any] = {}

    if isinstance(data, list):
        for index, group in enumerate(data):
            if not isinstance(group, dict):
                continue
            primary_key = str(group.get("primaryKey") or group.get("id") or f"group_{index}")
            fields = group.get("tableData") if isinstance(group.get("tableData"), list) else []
            context[primary_key] = {
                "key": primary_key,
                "label": group.get("name", primary_key),
                "type": "context_group",
                "value": primary_key,
                "component": component_type,
                "fields": fields,
            }
            for field in fields:
                if not isinstance(field, dict):
                    continue
                param_key = field.get("paramKey")
                if not param_key or param_key in context:
                    continue
                context[param_key] = {
                    "key": param_key,
                    "label": field.get("showName") or field.get("paramName") or param_key,
                    "name": field.get("paramName") or field.get("showName") or param_key,
                    "type": field.get("paramType") or field.get("paramTypeString") or "unknown",
                    "value": param_key,
                    "group": primary_key,
                    "description": field.get("description", ""),
                    "raw": field,
                }
        return context

    if not isinstance(data, dict):
        return context
    for variable in data.get("variables", data.get("variableList", [])):
        if isinstance(variable, dict) and (key := variable.get("key", variable.get("name", ""))):
            context[str(key)] = variable
    for field in data.get("formFields", data.get("fields", [])):
        if isinstance(field, dict) and (field_id := field.get("id", field.get("key", ""))):
            context[f"FormData.{field_id}"] = {
                "key": str(field_id),
                "name": field.get("name", field_id),
                "type": field.get("type", field.get("fieldType", "")),
                "value": f"FormData.{field_id}",
            }
    return context or {str(key): value for key, value in data.items() if key not in {"code", "msg", "status"}}
