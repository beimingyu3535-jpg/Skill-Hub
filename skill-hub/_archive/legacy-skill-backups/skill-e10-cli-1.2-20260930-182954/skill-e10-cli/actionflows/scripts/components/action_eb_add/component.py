"""新建表单数据 (ActionEbAdd)"""

COMPONENT = {
    "type": "ActionEbAdd",
    "nodeRole": "action",
    "description": "新增 e-builder 表单数据。支持流程字段映射（mapping）和固定值（constants）两种动态赋值方式。",

    "display": {
        "typeName": "新建表单数据",
        "componentName": "新建表单数据",
        "componentDesc": "新增指定e-builder应用下的表单数据",
        "icon": "Icon-eb-mcolor",
        "componentNameLabel": 221793,
        "componentDescLabel": 221245,
    },

    "params": {
        "targetForm": {
            "required": True,
            "description": "要新增数据的 e-builder 表单。标准格式为 groupId/id；兼容迁移或 CLI 的 appId/tableId 别名，生成前会按当前租户实时补齐表名。",
            "valueType": "platform_reference",
            "referenceType": "ebuilder_form",
            "valueShape": "object",
        },
        "person": {
            "required": True,
            "description": "新增数据的创建者。用 recipient-search 查到真实人员，plan 传 {\"id\":\"<人员id>\",\"name\":\"<姓名>\"}。",
            "valueType": "platform_reference",
            "referenceType": "user_assignment",
            "valueShape": "object",
        },
        "mapping": {
            "required": False,
            "description": "字段映射：源字段 paramKey → 目标字段 ID。必须来自本次 component-context；编译器校验来源字段名、作用域和类型，名称明显无关时停止。例：{\"<源paramKey>\":\"<目标字段id>\"}",
            "valueType": "object",
            "valueShape": "object",
        },
        "confirmSemanticMismatch": {
            "required": False,
            "description": "仅当用户明确要求名称不同的字段互相映射时设为 true；否则语义不一致会阻止暂存。",
            "valueType": "boolean",
        },
        "confirmTypeMismatch": {
            "required": False,
            "description": "仅当用户明确确认来源与目标字段类型不同但可由平台兼容转换时设为 true。",
            "valueType": "boolean",
        },
        "constants": {
            "required": False,
            "description": "常量赋值：目标字段 ID → 固定值。编译器生成 fixvalue 赋值。例：{\"<目标字段id>\": \"8\"}",
            "valueType": "object",
            "valueShape": "object",
        },
        "setting": {
            "required": False,
            "description": "旧格式字段赋值数组（与 mapping/constants 二选一）。",
            "valueType": "array",
            "valueShape": "array",
            "itemSchema": {"requiredKeys": ["field", "value"]},
        },
        "detail": {
            "required": False,
            "description": "明细表字段赋值（可选）。数组，每个元素对应一个明细表："
                           "{\"detailTableId\":\"<明细表id>\",\"mapping\":{\"<源paramKey>\":\"<明细字段id>\"},"
                           "\"constants\":{\"<明细字段id>\":\"<固定值>\"},\"deleteFields\":[\"<字段id>\"]}。"
                           "明细表 id 通过 form-fields 的 detail 分组查到。",
            "valueType": "array",
            "valueShape": "array",
            "itemSchema": {"requiredKeys": ["detailTableId"]},
        },
        "opType": {
            "required": False,
            "default": "insert",
            "description": "新增方式。",
            "valueType": "enum",
            "options": [
                {"value": "insert", "label": "新增单条数据"},
                {"value": "batchInsert", "label": "批量新增"},
            ],
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
        "basisValue": {
            "required": False,
            "description": "批量新增(一对多)的依据值: 引用上游明细表字段(流程明细表/查询结果)。plan 传 {\"paramKey\":\"<明细字段paramKey>\",\"label\":\"<明细表名>\"}，编译器据此生成 basisValue=明细表id + basisValueFormula(type=3 公式, value='FormData.{wfId}.{明细字段id}[]')。仅 opType=batchInsert 时生效。",
            "valueType": "object",
            "valueShape": "object",
        },
    },

    "dataMapping": {
        "targetForm": "_targetForm",
        "person": "_person",
        "setting": "_setting_main",
        "mapping": "_setting_mapping",
        "constants": "_setting_constants",
        "formula": "_setting_formula",
        "detail": "_setting_detail",
        "basisValue": "_basisValue",
        "opType": "opType",
        "syncType": "syncType",
        "workflowModule": "workflowModule",
        "workflowId": "workflowId",
    },

    "defaultData": {"ebActionId": "-1", "opType": "insert", "syncType": "0"},

    "runtimeContext": {
        "inputs": ["FormData"],
        "outputs": ["FormData", "FormField", "SettingInfo", "accessId", "monitorId"],
    },

    "dataFields": {
        "ebActionId": {"type": "int|str", "required": True, "platformRef": "actionConfig"},
        "opType": {"type": "string", "required": True, "default": "insert", "options": ["insert", "batchInsert"]},
        "targetForm": {"type": "object", "required": True, "subfields": ["groupName", "groupId", "id", "text", "type"]},
        "setting": {"type": "object", "required": True, "subfields": ["opType", "dataDrWithCalc", "main", "detail"]},
        "tableType": {"type": "array", "required": True},
        "appType": {"type": "array", "required": True},
        "person": {"type": "object", "required": True, "platformRef": "user_assignment"},
        "syncType": {"type": "string", "required": False, "default": "0", "options": ["0", "1", "2"]},
    },
}
