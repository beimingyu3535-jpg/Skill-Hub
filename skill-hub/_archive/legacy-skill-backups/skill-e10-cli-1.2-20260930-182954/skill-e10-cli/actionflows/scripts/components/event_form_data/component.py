"""表单数据触发 (EventFormData)"""

COMPONENT = {
    "type": "EventFormData",
    "nodeRole": "event",
    "description": "e-builder 表单数据新增/更新/删除后自动触发动作流。"
                   "用于数据触发（表单数据变动 → 发起新流程/更新关联数据）等场景。"
                   "目标表单必须通过 form-applications + form-list 查到真实 id/groupId/text。",

    "display": {
        "typeName": "表单数据触发",
        "componentName": "表单数据触发",
        "componentDesc": "表单数据变动后触发动作流",
        "icon": "Icon-eb-mcolor",
        "componentNameLabel": 264861,
        "componentDescLabel": 264862,
    },

    "params": {
        "targetForm": {
            "required": True,
            "description": "要监听数据变动的 e-builder 表单。标准格式为 groupId/id；兼容 appId/tableId 别名，生成前会按当前租户实时补齐表名。",
            "valueType": "platform_reference",
            "referenceType": "ebuilder_form",
            "valueShape": "object",
        },
        "triggerTimes": {
            "required": True,
            "description": "触发时机（数组，可多选）：afterAdd=数据新增后 / afterUpdate=数据更新后 / "
                           "afterDelete=数据删除后 / fieldDataChange=数据更新后-值发生变化（仅物理表支持；"
                           "e-builder 表单必须使用 afterUpdate）。",
            "valueType": "array",
            "valueShape": "array",
        },
        "triggerType": {
            "required": False,
            "default": "sequence",
            "description": "同时多条数据变动时如何触发：sequence=依次触发 / merge=合并触发 / parallel=并行触发。",
            "valueType": "enum",
            "options": [
                {"value": "sequence", "label": "依次触发"},
                {"value": "merge", "label": "合并触发"},
                {"value": "parallel", "label": "并行触发"},
            ],
        },
        "changeFields": {
            "required": False,
            "description": "仅物理表且 triggerTimes 包含 fieldDataChange 时必填：需要监听的字段 ID 数组。字段必须经 form-fields 实时查询；文件/图片字段不允许作为该触发条件。",
            "valueType": "array",
            "valueShape": "array",
        },
        "filter": {
            "required": False,
            "description": "触发条件（可选）：仅满足条件的数据变动才触发。"
                           "[{field, operator, value}]，value 可引用上下文。",
            "valueType": "array",
            "valueShape": "array",
            "itemSchema": {"requiredKeys": ["field", "operator", "value"]},
        },
    },

    "dataMapping": {
        "targetForm": "_targetForm",
        "triggerTimes": "triggerTimes",
        "triggerType": "triggerType",
        "changeFields": "changeFields",
        "filter": "_filterInput",
    },

    "defaultData": {
        "triggerType": "sequence",
        "ebActionId": "-1",
    },

    "runtimeContext": {
        "inputs": [],
        "outputs": ["FormData", "FormField", "SettingInfo", "accessId", "monitorId"],
    },

    "dataFields": {
        "targetForm": {"type": "object", "required": True, "subfields": ["groupName", "groupId", "id", "text", "type"]},
        "appType": {"type": "array", "required": True},
        "tableType": {"type": "array", "required": True},
        "triggerTimes": {"type": "array", "required": True},
        "triggerType": {"type": "string", "required": False, "default": "sequence", "options": ["sequence", "merge", "parallel"]},
        "changeFields": {"type": "array", "required": False},
        "ebActionId": {"type": "int|str", "required": True, "platformRef": "actionConfig"},
        "id": {"type": "string", "required": True, "platformRef": "actionConfig"},
        "type": {"type": "string", "required": True, "default": "EventFormData"},
    },
}
