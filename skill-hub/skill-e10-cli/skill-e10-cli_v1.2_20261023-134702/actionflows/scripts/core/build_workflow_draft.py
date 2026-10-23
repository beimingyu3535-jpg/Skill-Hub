from __future__ import annotations

from copy import deepcopy
from typing import Any

from core.component_registry import normalize_assignment_items, normalize_node_with_contract

def public_node_fields(node: dict[str, Any]) -> dict[str, Any]:
    node = normalize_node_with_contract(node)
    return {
        "type": node.get("type", ""),
        "params": deepcopy(node.get("params", {})),
        "missingFields": deepcopy(node.get("missingFields", [])),
        "warnings": deepcopy(node.get("warnings", [])),
    }

def next_action_id(counter: dict[str, int]) -> str:
    value = counter["value"]
    counter["value"] += 1
    return f"action_{value}"

def build_branch_actions(steps: list[dict[str, Any]], counter: dict[str, int]) -> list[dict[str, Any]]:
    built: list[dict[str, Any]] = []
    previous_id = "0"
    for step in steps:
        node = public_node_fields(step)
        node["id"] = next_action_id(counter)
        node["previousId"] = previous_id
        previous_id = node["id"]
        built.append(reorder_action_fields(node))
    return built

def build_condition_node(step: dict[str, Any], counter: dict[str, int]) -> dict[str, Any]:
    node = public_node_fields(step)
    branches = []
    for index, branch in enumerate(step.get("branches", []), start=1):
        branches.append(
            {
                "id": branch.get("id") or f"branch_{index}",
                "name": branch.get("name", ""),
                "condition": branch.get("condition", {}),
                "actions": build_branch_actions(branch.get("actions", []), counter),
            }
        )
    node["branches"] = branches
    return node

def reorder_action_fields(node: dict[str, Any]) -> dict[str, Any]:
    ordered = {
        "id": node["id"],
        "type": node.get("type", ""),
        "previousId": node["previousId"],
        "params": node.get("params", {}),
    }
    if "branches" in node:
        ordered["branches"] = node["branches"]
    ordered["missingFields"] = node.get("missingFields", [])
    ordered["warnings"] = node.get("warnings", [])
    return ordered

def build_workflow_draft(plan: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_semantic_plan(plan)
    event_data = public_node_fields(normalized["event"])
    event = {
        "id": "event_1",
        "type": event_data["type"],
        "params": event_data["params"],
        "missingFields": event_data["missingFields"],
        "warnings": [*event_data["warnings"], *normalized["warnings"]],
    }

    actions = []
    previous_id = "0"
    counter = {"value": 1}
    for step in normalized["actions"]:
        action_id = next_action_id(counter)
        if step.get("type") == "Condition":
            node = build_condition_node(step, counter)
        else:
            node = public_node_fields(step)
        node["id"] = action_id
        node["previousId"] = previous_id
        previous_id = node["id"]
        actions.append(reorder_action_fields(node))

    output = public_node_fields({"type": "Output", **normalized["finalOutput"]})
    output["id"] = next_action_id(counter)
    output["previousId"] = previous_id
    actions.append(reorder_action_fields(output))

    return {"event": event, "actions": actions}

# ---------------------------------------------------------------------------
# Semantic plan normalization (merged from normalize_semantic_plan.py)
# ---------------------------------------------------------------------------

def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]

def normalize_node(node: dict[str, Any]) -> dict[str, Any]:
    """Keep model-owned semantic fields; IDs and missing fields belong to the compiler.

    Top-level fields that are NOT ``type``/``params``/``branches`` are
    moved into ``params`` so the contract-based normalizer can process them.
    This is critical for event nodes (e.g. ApproveTrigger) where the AI
    puts ``workflowId`` / ``triggerTiming`` / ``approveNode`` at event
    top-level instead of inside ``params``.
    """
    params = deepcopy(node.get("params", {})) if isinstance(node.get("params", {}), dict) else {}
    # Promote top-level semantic fields into params so they survive normalization
    known_meta_keys = frozenset({"type", "params", "branches", "missingFields", "warnings",
                                 "condition", "actions", "name"})
    for key, value in node.items():
        if key in known_meta_keys:
            continue
        if key not in params:
            params[key] = value
    # Map AI-friendly top-level fields to contract-friendly param names
    #  params 可能已被 enrich 预填 workflowPath (preflight 事件
    # 上下文查询需要) — 此时 normalize 不能因 workflowPath 已存在就保留 workflowId,
    # 否则 validate 报 "event.params.workflowId is not defined". 无论是否已转换,
    # workflowId/workflowName 都是编译器字段, 一律从 params 移除.
    if "workflowId" in params:
        if "workflowPath" not in params:
            wf_path = {"id": str(params["workflowId"])}
            if "workflowName" in params:
                wf_path["name"] = str(params["workflowName"])
            params["workflowPath"] = wf_path
        params.pop("workflowId", None)
        params.pop("workflowName", None)
    # ApproveCreate 的真实 data 字段及用户合同都叫 operator。早期 Skill
    # 曾把简化参数写成 operateUser，导致按当前文档组装的 operator 被契约层
    # 静默忽略。接受旧别名，但统一为 operator 进入后续编译/预检/转换链路。
    if node.get("type") == "ApproveCreate" and "operator" not in params and "operateUser" in params:
        params["operator"] = params["operateUser"]
    if node.get("type") == "ApproveCreate":
        params.pop("operateUser", None)
    if node.get("type") == "ApproveTrigger":
        timing_aliases = {
            "archived": "workflow_completed",
            "workflow_archived": "workflow_completed",
            "workflowcompleted": "workflow_completed",
            "end": "workflow_completed",
            "流程结束": "workflow_completed",
            "归档": "workflow_completed",
            "流程归档": "workflow_completed",
        }
        timing = str(params.get("triggerTiming", "")).strip().casefold()
        if timing in timing_aliases:
            params["triggerTiming"] = timing_aliases[timing]
    if node.get("type") in {"ActionEbAdd", "ActionEbUpdate"}:
        for assignment_key in ("setting", "updates"):
            if assignment_key in params:
                params[assignment_key] = normalize_assignment_items(params[assignment_key])
    # Time-based trigger contracts use a numeric-looking *string* for cycle.
    # Plans produced by an LLM commonly contain 1 instead of "1"; normalize at
    # the boundary so the semantic plan remains portable across runtimes while
    # the generated platform data satisfies the real component contract.
    if node.get("type") in {"SimpleScheduler", "TimeBatchTrigger"}:
        cycle = params.get("cycle")
        if isinstance(cycle, (int, float)) and not isinstance(cycle, bool):
            params["cycle"] = str(cycle)
    normalized = {
        "type": node.get("type", ""),
        "params": params,
    }
    if normalized["type"] == "Condition":
        # 组件 registry 的公开合同将 branches 定义为 params.branches；早期编译器
        # 却只读取节点顶层 branches，导致按 describe 组装的合法 plan 被报空分支。
        # 这里兼容两种输入，并统一为 Draft 顶层 branches（平台转换器的规范形态）。
        raw_branches = node.get("branches")
        if not isinstance(raw_branches, list):
            raw_branches = params.pop("branches", [])
        else:
            params.pop("branches", None)
        branches = []
        for branch in raw_branches:
            branch_actions = branch.get("actions", [])
            branches.append(
                {
                    "name": branch.get("name", ""),
                    "condition": deepcopy(branch.get("condition", {})),
                    # 分支内 Output 保留到 normalized plan, 由 validate 显式报错
                    # (Output 是主链结束节点, 只能通过 finalOutput 表达). 若在这里
                    # 过滤, validate 看不到 Output, 会静默生成空分支.
                    "actions": [
                        normalize_node(step)
                        for step in branch_actions
                    ],
                }
            )
        normalized["branches"] = branches
    return normalized

def normalize_semantic_plan(plan: dict[str, Any]) -> dict[str, Any]:
    actions = [normalize_node(step) for step in plan.get("actions", []) if step.get("type") != "Output"]
    legacy_outputs = [step for step in plan.get("actions", []) if step.get("type") == "Output"]
    final_output = plan.get("finalOutput")
    if not isinstance(final_output, dict):
        final_output = legacy_outputs[-1] if legacy_outputs else {}

    return {
        "event": normalize_node(plan.get("event", {})),
        "actions": actions,
        "finalOutput": {"params": deepcopy(final_output.get("params", {}))},
        "warnings": ensure_list(plan.get("warnings")),
    }
