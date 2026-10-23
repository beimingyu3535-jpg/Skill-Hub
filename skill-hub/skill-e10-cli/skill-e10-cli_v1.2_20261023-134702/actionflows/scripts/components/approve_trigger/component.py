"""流程触发 (ApproveTrigger)"""

COMPONENT = {
    "type": "ApproveTrigger",
    "nodeRole": "event",
    "description": "流程提交、审批通过、流程结束等时机触发动作流。",

    "display": {
        "typeName": "流程触发",
        "componentName": "流程触发",
        "componentDesc": "流程触发",
        "icon": "Icon-Approval-process",
        "iconColor": "#68a5ff",
        "componentNameLabel": 131942,
        "componentDescLabel": 236889,
    },

    "params": {
        "workflowPath": {
            "required": True,
            "description": "触发流程。plan 传单个 object：{\"id\":\"<流程id>\",\"name\":\"<流程名>\",\"workflowtype\":\"<流程类型id>\",\"formIds\":[\"<表单id>\"]}（编译器内部转数组）。需优先通过 workflow-browser-list 查询真实流程 ID。",
            "valueType": "platform_reference",
            "referenceType": "workflow",
            "valueShape": "object",
        },
        "triggerTiming": {
            "required": True,
            "description": "触发时机（设计器「类型」主下拉 9 种全覆盖 + executeTime 子方向）: submitted=提交时(节点前), approve_passed=审批通过时(批准确认时), workflow_completed=流程结束时(节点前=归档节点到达), leave=离开节点后(节点后), link=出口, delete=流程删除时, save=流程保存时, revert=流程还原时, pause=流程暂停启用时, cancel=流程撤销恢复时, plus 中英文别名 (submitted_after/workflow_started/approve/node_leave/exit/flow_*/process_* 等).",
            "valueType": "enum",
            "options": [
                {"value": "submitted", "label": "流程提交时"},
                {"value": "approve_passed", "label": "审批通过时"},
                {"value": "workflow_completed", "label": "流程结束时"},
                {"value": "leave", "label": "离开节点后"},
                {"value": "link", "label": "出口"},
                {"value": "delete", "label": "流程删除时"},
                {"value": "save", "label": "流程保存时"},
                {"value": "revert", "label": "流程还原时"},
                {"value": "pause", "label": "流程暂停启用时"},
                {"value": "cancel", "label": "流程撤销恢复时"},
            ],
        },
        "nodeTime": {
            "required": False,
            "description": "执行时间子方向（executeTime 单值, 设计器「执行时间」列, **按 objType 类型不同选项不同**, 非法值会明确报错）: 节点前(pre): 1正向流转到达/2退回到达/3强制收回到达/4撤回到达/6干预到达(+归档节点5强制结束到达); 节点后(after): 1正向离开后/2退回离开后/3强制收回离开/6干预离开; 暂停启用(stopAndOpen): 1暂停时/2启用时; 撤销恢复(cancelAndRegain): 1撤销时/2恢复时; 批准确认/出口/删除/保存/还原 无执行时间列.",
            "valueType": "enum",
            "default": "1",
            "options": [
                {"value": "1", "label": "正向方向 (默认, 语义依赖类型)"},
                {"value": "2", "label": "退回/反向 (退回到达/退回离开后/启用时/恢复时)"},
                {"value": "3", "label": "强制收回方向 (仅 pre/after)"},
                {"value": "4", "label": "撤回到达 (仅节点前)"},
                {"value": "5", "label": "强制结束到达 (仅节点前+归档节点)"},
                {"value": "6", "label": "干预方向 (仅 pre/after)"},
            ],
        },
        "triggerType": {
            "required": False,
            "description": "触发器类型，默认 singleApprove。",
            "valueType": "string",
            "default": "singleApprove",
        },
        "module": {
            "required": False,
            "description": "流程模块，默认 workflow。",
            "valueType": "string",
            "default": "workflow",
        },
        "approveNode": {
            "required": False,
            "description": "触发节点（编译器根据 triggerTiming 自动选择流程节点）。",
            "valueType": "object",
            "valueShape": "object",
        },
        "async": {
            "required": False,
            "description": "是否异步执行（设计器「异步执行」开关，默认 false=同步）。",
            "valueType": "boolean",
            "default": False,
        },
        "approveList": {
            "required": False,
            "requiredWhen": {"param": "triggerType", "equals": "multiApprove"},
            "description": "多流程审批触发设置的设计器原生行数组。必须来自平台回读 JSON；当前不根据流程名称伪造行结构。",
            "valueType": "array",
            "valueShape": "array",
        },
        "approveListFormOpen": {"required": False, "description": "多流程表单选择器原生状态，仅与 approveList 回读结构一起使用。", "valueType": "boolean"},
        "approveListFormModule": {"required": False, "description": "多流程表单模块原生值，仅与 approveList 一起使用。", "valueType": "string"},
    },

    "dataMapping": {
        "workflowPath": "workflowPath",
        "module": "module",
        "triggerType": "triggerType",
        "approveList": "approveList",
        "approveListFormOpen": "approveListFormOpen",
        "approveListFormModule": "approveListFormModule",
    },

    "defaultData": {"module": "workflow", "triggerType": "singleApprove"},

    "runtimeContext": {
        "inputs": [],
        "outputs": ["FormData"],
    },

    "dataFields": {
        "module": {"type": "string", "required": True, "default": "workflow"},
        "triggerType": {"type": "string", "required": True, "default": "singleApprove"},
        "workflowPath": {"type": "array", "required": True},
        "approveList": {"type": "array", "required": False},
    },

    "triggerType": "WorkflowTrigger",
    "triggerTypeName": "流程事件触发",
    "_workflowPathArray": True,
}
