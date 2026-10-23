"""组件注册中心 — 自动发现 scripts/components/ 下所有组件包。

用法:
    from components import get, get_all, describe, list_types

加新组件: 建立 scripts/components/new_thing/component.py，定义 COMPONENT dict → 自动注册。
"""
from __future__ import annotations

import importlib
import pkgutil
import re
from pathlib import Path
from typing import Any

_components: dict[str, dict[str, Any]] = {}
_source_files: dict[str, str] = {}  # type → 来源包名（契约文件校验/脚手架用）
_converters: dict[str, Any] = {}    # type → 可选专用转换器 CONVERTER
_validators: dict[str, Any] = {}
_readback_asserts: dict[str, Any] = {}
_discovered: bool = False

def _discover() -> None:
    global _components, _discovered
    if _discovered:
        return

    package_dir = Path(__file__).parent
    discovery_errors: list[str] = []
    for _, name, is_package in pkgutil.iter_modules([str(package_dir)]):
        if name.startswith("_"):
            continue
        # 组件只能来自独立包；避免旧扁平文件与新包同时存在时静默加载两份。
        if not is_package:
            continue
        try:
            mod = importlib.import_module(f"components.{name}")
            if hasattr(mod, "COMPONENT") and isinstance(mod.COMPONENT, dict):
                ctype = mod.COMPONENT.get("type")
                if ctype and isinstance(ctype, str):
                    if ctype in _components:
                        discovery_errors.append(
                            f"组件类型重复: {ctype}（{_source_files[ctype]} 与 {name}）"
                        )
                        continue
                    _components[ctype] = mod.COMPONENT
                    _source_files[ctype] = name
                    # 可选专用转换器: CONVERTER(draft_params, **kwargs) -> dict
                    if hasattr(mod, "CONVERTER") and callable(mod.CONVERTER):
                        _converters[ctype] = mod.CONVERTER
                    # 可选钩子直接从独立模块发现，组件入口无需为不存在的空文件写
                    # try/except 壳；若文件存在但导入失败，外层会让注册整体失败。
                    for module_name, attribute, target in (
                        ("validator", "VALIDATOR", _validators),
                        ("readback", "READBACK_ASSERT", _readback_asserts),
                    ):
                        hook_path = f"components.{name}.{module_name}"
                        if importlib.util.find_spec(hook_path) is None:
                            continue
                        hook_module = importlib.import_module(hook_path)
                        hook = getattr(hook_module, attribute, None)
                        if not callable(hook):
                            raise TypeError(f"{hook_path}.{attribute} 必须是可调用对象")
                        target[ctype] = hook
        except Exception as exc:
            discovery_errors.append(f"组件 {name} 加载失败: {exc}")
    if discovery_errors:
        # 不能将损坏包静默排除，否则新增组件的语法/导入错误会被遗漏。
        raise RuntimeError("；".join(discovery_errors))
    _discovered = True

_discover()

# ── 查询 API ──

def get_all() -> dict[str, dict[str, Any]]:
    return dict(_components)

def get(ctype: str) -> dict[str, Any] | None:
    return _components.get(ctype)

def get_source_file(ctype: str) -> str:
    """返回组件契约来源包名（无则回退 to_snake 猜测）。"""
    return _source_files.get(ctype, "")

def get_converter(ctype: str):
    """返回组件可选专用转换器 CONVERTER（无则 None，map_draft_data 走内置通用分支）。"""
    return _converters.get(ctype)

def get_validator(ctype: str):
    """返回组件专用动态校验器（无则 None）。"""
    return _validators.get(ctype)

def get_readback_assert(ctype: str):
    """返回组件专用暂存回读断言（无则 None）。"""
    return _readback_asserts.get(ctype)

def describe(types: list[str]) -> dict[str, Any]:
    """生成 describe 命令的输出（params + description + nodeRole）"""
    result: dict[str, Any] = {}
    for t in types:
        comp = _components.get(t)
        if comp:
            result[t] = {
                "description": comp.get("description", ""),
                "nodeRole": comp.get("nodeRole", "action"),
                "params": comp.get("params", {}),
            }
    return result


def search(query: str, node_role: str | None = None, limit: int = 8) -> list[dict[str, str]]:
    """按用户意图返回少量候选组件，不展开参数契约。"""
    normalized = re.sub(r"\s+", "", str(query or "")).casefold()
    if node_role is not None and node_role not in {"event", "action"}:
        raise ValueError("nodeRole must be event or action")
    if not normalized:
        raise ValueError("query must not be empty")
    if len(normalized) < 2:
        raise ValueError("query must contain at least two characters")

    query_bigrams = {normalized[index:index + 2] for index in range(len(normalized) - 1)}
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for component_type, contract in _components.items():
        role = str(contract.get("nodeRole", "action"))
        if node_role and role != node_role:
            continue
        display = contract.get("display") if isinstance(contract.get("display"), dict) else {}
        text = " ".join([
            component_type,
            str(contract.get("name", "")),
            str(contract.get("description", "")),
            str(display.get("typeName", "")),
            str(display.get("componentName", "")),
        ])
        searchable = re.sub(r"\s+", "", text).casefold()
        bigram_hits = len(query_bigrams & {searchable[index:index + 2] for index in range(len(searchable) - 1)})
        if normalized not in searchable and not bigram_hits:
            continue
        score = (100 if normalized in searchable else 0) + 8 * bigram_hits
        score += len(set(normalized) & set(searchable))
        if score > 0:
            candidates.append((score, component_type, contract))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [
        {
            "type": component_type,
            "nodeRole": str(contract.get("nodeRole", "action")),
            "description": str(contract.get("description", "")),
        }
        for _, component_type, contract in candidates[:max(1, min(int(limit), 20))]
    ]

def list_types(node_role: str | None = None) -> list[str]:
    if node_role:
        return [t for t, c in _components.items() if c.get("nodeRole") == node_role]
    return list(_components.keys())
