"""流程触发器的实时节点补全。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from core.platform_client import make_client

WORKFLOW_NODES_CACHE: dict[str, list] = {}

def enrich_approve_trigger_node(plan: dict[str, Any]) -> dict[str, Any]:
    """为流程触发器补全真实节点,供真实 JSON 适配器生成触发时机.

    模型只表达语义 ``triggerTiming``.这里根据当前账号可见的流程节点选择:
    - 提交类(submitted) → 发起节点(nodeType=0),配合 objType="approve"
    - 审批通过类(approve_passed) → 审批节点(nodeType=1/2/5),配合 objType="after"
    - 流程结束类(workflow_completed) → 结束节点(nodeType=3),配合 objType="approve"
    用户已经指定 ``approveNode`` 时不覆盖,避免改变其明确选择.

    失败处理: 找不到匹配的流程节点时(如流程只有发起/结束节点却指定
    approve_passed), 不再静默生成空 singleApproveConfig. 改为在 plan 上加
    ``_enrich_errors`` 列表, generate 主流程据此中止生成.
    """
    enriched = deepcopy(plan)
    event = enriched.get("event")
    if not isinstance(event, dict) or event.get("type") != "ApproveTrigger":
        return enriched
    # 兼容两种 plan 写法: workflowId/triggerTiming 在 event 顶层或在 params 内
    timing = str(event.get("triggerTiming", "")).strip().casefold()
    workflow_id = str(event.get("workflowId", ""))
    existing_node = event.get("approveNode")
    if not isinstance(existing_node, dict) and isinstance(event.get("params"), dict):
        existing_node = event["params"].get("approveNode")

    if event.get("params") and isinstance(event["params"], dict):
        params = event["params"]
        timing = timing or str(params.get("triggerTiming", "")).strip().casefold()
        wp = params.get("workflowPath")
        workflow_id = workflow_id or (str(wp.get("id", "")) if isinstance(wp, dict) else "")
        event.setdefault("params", {})
    else:
        event["params"] = {}
        params = event["params"]
    #  plan 顶层 workflowId 但 params 缺 workflowPath 时补上 —
    # preflight 用 enrich 后 plan 的 event.params 构造 getComponentContext data,
    # 缺 workflowPath → 事件上下文不返回流程字段 (明细表子字段拿不到) →
    # batchInsert 依据值下级 paramKey 预检报 unresolved context. compile 会补,
    # 但 preflight 发生在 compile 前, 必须在此补齐.
    if workflow_id and isinstance(params, dict) and not params.get("workflowPath"):
        params["workflowPath"] = {"id": workflow_id}
    if not workflow_id or not timing:
        return enriched

    # 调用方已从 workflow-nodes 查到真实节点时，接受顶层或 params 写法，
    # 不要重复访问平台，避免重复查询失败后误报“流程没有节点”。
    #: 用户只给 approveNode.name (如"发起节点") 未带 nodeType 时,
    # 也按名称在流程节点中匹配补全 (模板五要素"触发节点"支持), 否则转换器
    # _pre_exec_options(int(None)) 报错, 且生成器无法验证节点类型合法性.
    # plan 手写的 approveNode.id 可能是**旧流程/幽灵节点**：流程重建后节点 ID 会变化。
    # 平台设计提交会注册触发绑定
    # 挂到幽灵节点 → 设计器「动作执行节点/出口」读当前流程节点看不到 → 触发时机空.
    # 因此**即使 plan 指定 approveNode 也必须校验 id 在当前节点列表中**, 不在则
    # 按触发时机自动重选正确节点 — 这是"每次实时查"的真正落实.
    requested_name = ""
    if isinstance(existing_node, dict):
        if existing_node.get("nodeType") is not None:
            pass  # 仍需节点列表校验 id → 走下方查询逻辑
        requested_name = str(existing_node.get("name") or "").strip()
    else:
        requested_name = ""

    wf_key = str(workflow_id)
    node_query_error = ""
    if wf_key not in WORKFLOW_NODES_CACHE:
        try:
            response = make_client().list_workflow_nodes(wf_key)
            if isinstance(response, dict) and response.get("code") not in (None, 200):
                node_query_error = f"code={response.get('code')}, msg={response.get('msg', '')}".strip(" ,")
            cached_nodes = response.get("data", {}).get("data", []) if isinstance(response, dict) else []
            WORKFLOW_NODES_CACHE[wf_key] = cached_nodes if isinstance(cached_nodes, list) else []
        except Exception as exc:
            WORKFLOW_NODES_CACHE[wf_key] = []
            node_query_error = str(exc)
    nodes = WORKFLOW_NODES_CACHE[wf_key]

    #  plan 指定 approveNode 时校验 id 是否为当前流程节点.
    # 是 → 直接用 (保留用户明确选择); 否 (幽灵/过期 id) → 置空走自动选节点.
    if isinstance(existing_node, dict) and existing_node.get("id"):
        _plan_nid = str(existing_node.get("id"))
        _live_node = next(
            (n for n in nodes if isinstance(n, dict) and str(n.get("id")) == _plan_nid), None
        )
        if _live_node is not None:
            # 即使 ID 有效，也必须采用接口返回的完整节点对象。调用方常只传
            # {id,name}；缺 nodeType 会在流程结束/归档触发的执行时间校验中触发 int(None)。
            params["approveNode"] = _live_node
            return enriched
        # 过期节点 id → 记录 warning 并由下方逻辑自动重选
        enriched.setdefault("_enrich_warnings", []).append(
            f"approveNode.id={_plan_nid} 不在流程 {workflow_id} 当前节点列表中"
            f"(流程可能已重建), 已按触发时机 '{timing}' 自动重选正确节点"
        )
        existing_node = None
        requested_name = ""

    # 触发时机 → 可选节点类型:
    #   create(提交) 仅发起[0]; approve(批准确认) 仅中间[1,2,5] (发起/归档列表无 approve);
    #   workflow_completed 结束[3]; pause/stopAndOpen 非归档[0,1,2,5];
    #   leave/delete/save/revert/cancel/link 任意节点 (默认按中间→发起→结束顺序选)
    submit_timings = {"submitted", "submitted_after", "workflow_started", "submit"}
    approve_timings = {"approve_passed", "approve_node_passed", "approvepass", "approve"}
    end_timings = {"workflow_completed", "workflow_archived", "workflowcompleted",
                   "end", "archived", "流程结束"}
    any_node_timings = {"leave", "node_leave", "after",
                        "delete", "flow_deleted", "process_deleted",
                        "save", "flow_saved", "process_saved",
                        "revert", "flow_reverted", "process_reverted",
                        "cancel", "cancel_and_recover", "flow_canceled", "process_canceled",
                        "link", "exit", "node_link"}
    pause_timings = {"pause", "stop_and_open", "flow_paused", "process_paused"}

    if timing in submit_timings:
        desired_types = [0]
    elif timing in approve_timings:
        desired_types = [1, 2, 5]
    elif timing in end_timings:
        desired_types = [3]
    elif timing in pause_timings:
        desired_types = [0, 1, 2, 5]
    elif timing in any_node_timings:
        desired_types = [1, 2, 5, 0, 3]
    else:
        desired_types = [3]

    node = None
    if requested_name:
        # 用户按名字指定节点 (如"发起节点"/"1级审批节点") → 精确匹配名称
        node = next(
            (item for item in nodes
             if isinstance(item, dict) and str(item.get("name") or "").strip() == requested_name),
            None,
        )
        # 名称匹配失败时给明确报错 (不静默回退到别的节点)
        if node is None:
            errs: list[str] = enriched.setdefault("_enrich_errors", [])
            errs.append(
                f"指定触发节点 '{requested_name}' 不在流程 {workflow_id} 中; "
                f"实际节点: {[n.get('name') for n in nodes if isinstance(n, dict)]}"
            )
            return enriched
    else:
        node = next(
            (item for item in nodes
             if isinstance(item, dict) and item.get("nodeType") in desired_types),
            None,
        )
    if node:
        params["approveNode"] = node
        return enriched

    # 找不到对应节点 → 记录错误, 不静默通过
    errs: list[str] = enriched.setdefault("_enrich_errors", [])
    type_label = {0: "发起节点", 3: "结束节点"}.get(desired_types[0] if desired_types else 0,
                                          f"nodeType∈{desired_types}")
    if not nodes:
        errs.append(
            f"流程 {workflow_id} 节点查询失败: {node_query_error or '未返回任何节点'}; "
            "请确认当前环境会话有效，或先用 workflow-nodes 查询并把真实 approveNode 传入"
        )
    else:
        errs.append(
            f"triggerTiming='{timing}' 要求触发节点为 {type_label}, 但流程 {workflow_id} "
            f"只有 {[n.get('nodeType') for n in nodes if isinstance(n, dict)]} 类型节点"
        )
    return enriched

