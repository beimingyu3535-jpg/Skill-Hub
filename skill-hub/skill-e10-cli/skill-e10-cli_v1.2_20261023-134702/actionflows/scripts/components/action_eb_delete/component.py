"""删除表单数据 (ActionEbDelete)"""

COMPONENT = {
    "type": "ActionEbDelete",
    "nodeRole": "action",
    "description": "按条件删除 e-builder 表单数据。",

    "display": {
        "typeName": "删除表单数据",
        "componentName": "删除表单数据",
        "componentDesc": "按条件删除指定e-builder应用下的表单数据",
        "icon": "Icon-eb-mcolor",
        "componentNameLabel": 221792,
        "componentDescLabel": 221247,
    },

    "params": {
        "targetForm": {
            "required": True,
            "description": "要删除数据的 e-builder 表单。标准格式为 groupId/id；兼容迁移或 CLI 的 appId/tableId 别名，生成前会按当前租户实时补齐表名。",
            "valueType": "platform_reference",
            "referenceType": "ebuilder_form",
            "valueShape": "object",
        },
        "filterCondition": {
            "required": True,
            "description": "删除条件：定位要删除的记录。格式 [{field, operator, value}]；field 为目标表单字段 ID。动态右值必须为 {type:\"context\", paramKey:\"<本次 component-context 返回的原始键>\", label:\"...\"}；禁止把 FormData.xxx/ApprovalData.xxx 设计器路径写入 plan。",
            "valueType": "object",
            "valueShape": "object",
        },
        "person": {
            "required": True,
            "description": "操作人。用 recipient-search 查到真实人员，plan 传 {\"id\":\"<人员id>\",\"name\":\"<姓名>\"}。",
            "valueType": "platform_reference",
            "referenceType": "user_assignment",
            "valueShape": "object",
        },
        "syncType": {
            "required": False,
            "default": "0",
            "description": "权限同步：0=异步，1=同步，2=无需重构。",
            "valueType": "enum",
            "options": [
                {"value": "0", "label": "异步"},
                {"value": "1", "label": "同步"},
                {"value": "2", "label": "无需重构"},
            ],
        },
    },

    "dataMapping": {
        "targetForm": "_targetForm",
        "person": "_person",
        "filterCondition": "_filterInput",
        "syncType": "syncType",
        "workflowModule": "workflowModule",
        "workflowId": "workflowId",
    },

    "defaultData": {"ebActionId": "-1", "syncType": "0", "nullOpflag": False},

    "runtimeContext": {
        "inputs": ["FormData"],
        "outputs": ["FormData", "FormField", "accessId", "monitorId"],
    },

    "dataFields": {
        "ebActionId": {"type": "int|str", "required": True},
        "targetForm": {"type": "object", "required": True},
        "tableType": {"type": "array", "required": True},
        "appType": {"type": "array", "required": True},
        "person": {"type": "object", "required": True},
        "filterInput": {"type": "object", "required": True},
        "syncType": {"type": "string", "required": False, "default": "0"},
    },
}
