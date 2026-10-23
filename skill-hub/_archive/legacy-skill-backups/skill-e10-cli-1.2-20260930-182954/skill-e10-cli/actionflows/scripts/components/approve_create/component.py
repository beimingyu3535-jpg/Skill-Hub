"""新建流程 (ApproveCreate)

组件选型更正: 真实平台"新建流程"用的是 **ApproveCreate**,
不是 BussinessFlowCreate. 后端 BussinessFlowCreateComponent.java 整文件注释停用,
ApproveCreateComponent.java 正常激活. 平台数据 14 条"发起新流程"动作流全部是 ApproveCreate.
之前用 BussinessFlowCreate 保存报"初始化组件失败"是组件选型错误, 不是平台问题.
"""

COMPONENT = {
    "type": "ApproveCreate",
    "nodeRole": "action",
    "description": "发起一个全新的独立流程（不是子流程）。"
                   "用于流程结束后自动发起新流程、数据变动后发起流程等场景。"
                   "目标流程必须通过 workflow-browser-list 查到真实 id + createFlowId + name。",

    "display": {
        "typeName": "新建流程",
        "componentName": "新建流程",
        "componentDesc": "发起一个新的业务流程",
        "icon": "Icon-approval-process01-mcolor",
        "componentNameLabel": 138973,
        "componentDescLabel": 214821,
    },

    "params": {
        "workflowPath": {
            "required": True,
            "description": "要发起的目标流程。plan 传单个 object（编译器内部转数组）：用 workflow-browser-list 查到真实 id/createFlowId/name/workflowtype/formIds。"
                           "例：{\"id\":\"<流程id>\",\"createFlowId\":\"<流程id>\",\"name\":\"<流程名>\","
                           "\"workflowtype\":\"<流程类型id>\",\"formIds\":[\"<表单id>\"]}",
            "valueType": "platform_reference",
            "referenceType": "workflow",
            "valueShape": "object",
        },
        "operator": {
            "required": True,
            "description": "流程发起人。用 recipient-search 查到真实人员，plan 传 {\"id\":\"<人员id>\",\"name\":\"<姓名>\"}。",
            "valueType": "platform_reference",
            "referenceType": "user_assignment",
            "valueShape": "object",
        },
        "mapping": {
            "required": False,
            "description": "表单字段映射：源字段 paramKey → 目标字段 ID（发起流程的表单字段）。"
                           "例：{\"<源paramKey>\": \"<目标字段id>\"}",
            "valueType": "object",
            "valueShape": "object",
        },
        "constants": {
            "required": False,
            "description": "目标流程表单固定值：目标字段 ID → 固定值。"
                           "与 mapping 可同时使用；同一目标字段不得同时配置动态映射和固定值。",
            "valueType": "object",
            "valueShape": "object",
        },
        "detail": {
            "required": False,
            "description": "明细表字段映射；目标流程表单含明细表时传。"
                           "[{detailTableId, mapping, constants?, basisValue?}]，结构与 ActionEbAdd 相同。",
            "valueType": "array",
            "valueShape": "array",
        },
        "requestName": {
            "required": True,
            "description": "新流程名称/请求标题，必填。可引用上下文。",
            "valueType": "string",
        },
        "requestLevel": {
            "required": False,
            "default": "0",
            "description": "请求级别（真实数据 14 条全部为 '0'）。",
            "valueType": "string",
        },
        "isNextFlow": {
            "required": False,
            "default": "0",
            "description": "是否发起下一流程，默认 '0'。",
            "valueType": "string",
        },
        "bizReuqestName": {
            "required": False,
            "description": "业务标题（可选）。",
            "valueType": "string",
        },
    },

    "dataMapping": {
        "workflowPath": "_bizWorkflowPath",
        "operator": "_bizOperateUser",
        "mapping": "_setting_mapping",
        "constants": "_setting_constants",
        "detail": "_setting_detail",
        "requestName": "_bizRequestName",
        "requestLevel": "requestLevel",
        "isNextFlow": "isNextFlow",
        "bizReuqestName": "bizReuqestName",
        "workflowModule": "workflowModule",
        "workflowId": "workflowId",
    },

    "defaultData": {
        "ebActionId": "-1",
        "module": "workflow",
        "secLevel": "",
        "requestLevel": "0",
        "isNextFlow": "0",
        "type": "ApproveCreate",
    },

    "runtimeContext": {
        "inputs": ["FormData"],
        "outputs": ["FormData", "FormField", "SettingInfo", "requestId", "workflowId"],
    },

    "dataFields": {
        "workflowPath": {"type": "array", "required": True, "subfields": ["id", "createFlowId", "name", "workflowtype", "formIds"]},
        "formData": {"type": "object", "required": True, "subfields": ["main", "detail"]},
        "fields": {"type": "object", "required": True, "subfields": ["main", "detail"]},
        "operator": {"type": "object", "required": True, "platformRef": "user_assignment"},
        "module": {"type": "string", "required": True, "default": "workflow"},
        "requestLevel": {"type": "string", "required": True, "default": "0"},
        "isNextFlow": {"type": "string", "required": True, "default": "0"},
        "ebActionId": {"type": "int|str", "required": True, "platformRef": "actionConfig"},
        "id": {"type": "string", "required": False, "platformRef": "actionConfig"},
        "type": {"type": "string", "required": True, "default": "ApproveCreate"},
    },
}
