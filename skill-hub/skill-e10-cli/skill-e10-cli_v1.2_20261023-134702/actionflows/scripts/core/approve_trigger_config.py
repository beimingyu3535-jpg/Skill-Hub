"""ApproveTrigger 的触发时机平台配置构造。"""
from __future__ import annotations

def _build_approve_trigger_config(draft_params: dict) -> list[dict]:
    """将简化触发语义转换为 WfppsAdActionSet 的真实行结构.

    该配置由 weapp-workflow-develop 的 ``WfppsAdActionSet`` 维护:
    ``objType``、``nodeOrLinkName``、``executeTime``、``open``、``async``.

    触发时机映射 (e10-cli EVENT_MAP + additionSyncDialog.tsx 主下拉选项):
      主下拉「类型」对应 objType; 「执行时间」对应 executeTime[0] (子方向).
      e10 实证: arrive(到达节点=发起流程创建)→pre+['1']; leave(离开节点)→after+['1'];
      delete/save/revert 对应同名 objType (无 executeTime); pause→stopAndOpen+['1'];
      cancel→cancelAndRegain+['1']; approve→approve+['1'].

    执行时间子方向 (WfppsPreSelect/WfppsAfterSelect, select.tsx 实证):
      pre: 1=正向流转到达 / 2=退回到达 / 3=强制收回到达 / 4=撤回到达 / 6=干预到达 (+归档节点 5=强制结束到达)
      after: 1=正向离开后 / 2=退回离开后 / 3=强制收回离开 / 6=干预离开
      stopAndOpen: 1=暂停时 / 2=启用时
      cancelAndRegain: 1=撤销时 / 2=恢复时
      approve/link/delete/save/revert: 无子方向 (不渲染执行时间列)

    默认 executeTime=['1'] (正向方向). plan 可用 nodeTime 参数覆盖;
    非法 nodeTime 抛 ValueError (不静默回退, 参照操作符白名单原则).
    """
    node = draft_params.get("approveNode")
    if not isinstance(node, dict) or not node.get("id"):
        return []

    timing = str(draft_params.get("triggerTiming", "")).strip().casefold()
    node_time = str(draft_params.get("nodeTime", "1")).strip() or "1"

    #   create(提交)/submitted → 仅发起节点(0); approve(批准确认) → 仅中间节点(1/2/5)
    node_type = node.get("nodeType")
    submit_timings_set = {"submitted", "submitted_after", "workflow_started", "submit"}
    approve_timings_set = {"approve_passed", "approve_node_passed", "approvepass", "approve", "审批通过"}
    if timing in submit_timings_set and node_type not in (None, 0):
        raise ValueError(
            f"triggerTiming='{timing}' (流程创建时) 只支持发起节点(nodeType=0), "
            f"当前指定节点 nodeType={node_type}"
        )
    if timing in approve_timings_set and node_type not in (None, 1, 2, 5):
        raise ValueError(
            f"triggerTiming='{timing}' (批准确认时) 只支持审批/中间节点(nodeType=1/2/5), "
            f"当前指定节点 nodeType={node_type}"
        )

    # 各 objType 的执行时间合法选项 (无值 = 该类型不渲染执行时间列)
    # 归档节点 {1,2,3,4,5,6}; 用函数动态取,  前端审阅修正.
    def _pre_exec_options(node_type) -> set:
        if int(node_type) in (3,):   # 结束/归档节点
            return {"1", "2", "3", "4", "5", "6"}
        return {"1", "2", "3", "4", "6"}

    EXEC_TIME_OPTIONS = {
        "pre": None,  # 占位, 下方按节点动态求值
        "after": {"1", "2", "3", "6"},
        "stopAndOpen": {"1", "2"},
        "cancelAndRegain": {"1", "2"},
    }

    # objType 映射 (主下拉 9 种: 节点前/节点后/出口/删除/保存/批准确认时/还原/暂停启用/撤销恢复)
    # 提交类 → pre; 审批通过 → approve; 流程结束 → pre (归档节点到达)
    type_map = {
        # submitted → pre+['1']
        "submitted":             ("pre",  ["1"]),
        "submitted_after":       ("pre",  ["1"]),
        "workflow_started":      ("pre",  ["1"]),
        "submit":                ("pre",  ["1"]),
        # approve_passed → approve (无执行时间列)
        "approve_passed":        ("approve", None),
        "approve_node_passed":   ("approve", None),
        "approvepass":           ("approve", None),
        "approve":               ("approve", None),
        "审批通过":               ("approve", None),
        # leave → after+['1']
        "leave":                 ("after", ["1"]),
        "node_leave":            ("after", ["1"]),
        "after":                 ("after", ["1"]),
        # link → link (无执行时间列)
        "link":                  ("link", None),
        "exit":                  ("link", None),
        "node_link":             ("link", None),
        # delete/save/revert → 各对应, executeTime undefined
        "delete":                ("delete", None),
        "flow_deleted":          ("delete", None),
        "process_deleted":       ("delete", None),
        "save":                  ("save", None),
        "flow_saved":            ("save", None),
        "process_saved":         ("save", None),
        "revert":                ("revert", None),
        "flow_reverted":         ("revert", None),
        "process_reverted":      ("revert", None),
        # pause → stopAndOpen+['1']
        "pause":                 ("stopAndOpen", ["1"]),
        "stop_and_open":         ("stopAndOpen", ["1"]),
        "flow_paused":           ("stopAndOpen", ["1"]),
        "process_paused":        ("stopAndOpen", ["1"]),
        # cancel → cancelAndRegain+['1']
        "cancel":                ("cancelAndRegain", ["1"]),
        "cancel_and_recover":    ("cancelAndRegain", ["1"]),
        "flow_canceled":         ("cancelAndRegain", ["1"]),
        "process_canceled":      ("cancelAndRegain", ["1"]),
        # workflow_completed → pre (归档节点到达)
        "workflow_completed":    ("pre",  ["1"]),
        "workflow_archived":     ("pre",  ["1"]),
        "workflowcompleted":     ("pre",  ["1"]),
        "end":                   ("pre",  ["1"]),
        "archived":              ("pre",  ["1"]),
        "流程结束":               ("pre",  ["1"]),
        # 不能重复定义 "审批通过" — 前面 1898 行已定义 ("approve", None),
        # 重复定义会覆盖为带执行时间, 违反"批准确认无执行时间列"契约 .
    }

    mapped = type_map.get(timing)
    if mapped is None:
        return []
    obj_type, default_exec = mapped

    # 执行时间合法性校验: nodeTime 必须在该类型的合法选项内, 否则明确报错
    # 归档节点 {1,2,3,4,5,6}(含 5 强制结束到达). after {1,2,3,6}, stopAndOpen {1,2},
    # cancelAndRegain {1,2}.
    if obj_type == "pre":
        allowed = _pre_exec_options(node.get("nodeType"))
    else:
        allowed = EXEC_TIME_OPTIONS.get(obj_type)
    if allowed is not None and node_time not in allowed:
        raise ValueError(
            f"triggerTiming='{timing}' (objType={obj_type}) 的执行时间 nodeTime='{node_time}' 不合法, "
            f"该类型支持: {sorted(allowed)}"
        )
    exec_time = [node_time] if default_exec is not None else None

    # 异步执行: plan 可传 async=true/false,
    # 对应设计器「异步执行」开关, 默认 False (同步).
    async_flag = bool(draft_params.get("async", False))

    node_ref = {
        key: node[key]
        for key in ("id", "name", "workflowName", "workflowId", "typeId", "versionId", "nodeType", "nodeAttr")
        if key in node
    }
    out = [{
        "id": f"-trigger-{node_ref['id']}",
        "objType": obj_type,
        "nodeOrLinkName": [node_ref],
        "interfaceName": "",
        "open": True,
        "async": async_flag,
    }]
    if exec_time is not None:
        out[0]["executeTime"] = exec_time
    return out
