"""更新表单数据 (ActionEbUpdate)"""

COMPONENT = {
    "type": "ActionEbUpdate",
    "nodeRole": "action",
    "description": "按条件或 ID 更新 e-builder 表单数据。支持字段映射和固定值。",

    "display": {
        "typeName": "更新表单数据",
        "componentName": "更新表单数据",
        "componentDesc": "按条件或ID更新指定e-builder应用下的表单数据",
        "icon": "Icon-eb-mcolor",
        "componentNameLabel": 221790,
        "componentDescLabel": 221246,
    },

    "params": {
        "targetForm": {
            "required": True,
            "description": "要更新的 e-builder 表单。标准格式为 groupId/id；兼容迁移或 CLI 的 appId/tableId 别名，生成前会按当前租户实时补齐表名。",
            "valueType": "platform_reference",
            "referenceType": "ebuilder_form",
            "valueShape": "object",
        },
        "person": {
            "required": True,
            "description": "操作人。用 recipient-search 查到真实人员，plan 传 {\"id\":\"<人员id>\",\"name\":\"<姓名>\"}。",
            "valueType": "platform_reference",
            "referenceType": "user_assignment",
            "valueShape": "object",
        },
        "filterCondition": {
            "required": False,
            "requiredWhen": {"param": "opType", "equals": "updateData"},
            "description": "筛选条件：定位要更新的记录。格式 [{field, operator, value}]；field 为目标表单字段 ID。动态右值必须为 {\"type\":\"context\",\"paramKey\":\"<本次 component-context 返回的原始键>\",\"label\":\"...\"}；禁止把 FormData.xxx/ApprovalData.xxx 设计器路径写入 plan。",
            "valueType": "object",
            "valueShape": "object",
        },
        "mapping": {
            "required": False,
            "description": "字段映射：源字段 paramKey → 目标字段 ID。必须来自本次 component-context；编译器校验来源字段名、作用域和类型，名称明显无关时停止。",
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
            "description": "常量赋值：目标字段 ID → 固定值。",
            "valueType": "object",
            "valueShape": "object",
        },
        "updates": {
            "required": False,
            "description": "旧格式更新数组（与 mapping/constants 二选一）。",
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
            "default": "updateData",
            "description": "更新定位方式。",
            "valueType": "enum",
            "options": [
                {"value": "id", "label": "按 ID"},
                {"value": "updateData", "label": "按条件"},
                {"value": "fieldUpdate", "label": "字段更新"},
            ],
        },
        "updateId": {
            "required": False,
            "requiredWhen": {"param": "opType", "equals": "id"},
            "description": "按数据 ID 更新时使用的 ID 公式；支持 fixed/context 语义赋值。",
            "valueType": "object",
            "valueShape": "object",
        },
        "updateFieldCondition": {
            "required": False,
            "requiredWhen": {"param": "opType", "equals": "fieldUpdate"},
            "description": "按字段匹配更新时的条件字段。对象含 updateField 数组，每项至少提供 fieldKey 和 assign。",
            "valueType": "object",
            "valueShape": "object",
        },
        "updatePolicy": {
            "required": False,
            "requiredWhen": {"param": "opType", "equals": "fieldUpdate"},
            "default": "ALL",
            "description": "字段匹配更新策略。",
            "valueType": "enum",
            "options": [
                {"value": "ALL", "label": "更新全部"},
                {"value": "FIRST", "label": "更新第一条"},
                {"value": "LAST", "label": "更新最后一条"},
                {"value": "ZERO", "label": "不更新"},
                {"value": "EXCEPTION", "label": "异常"},
            ],
        },
        "basisValueFormula": {
            "required": False,
            "description": "字段匹配更新的明细/列表依据值公式。",
            "valueType": "object",
            "valueShape": "object",
        },
        "needAdd": {"required": False, "valueType": "boolean", "description": "未匹配时是否新增。"},
        "nullOpflag": {"required": False, "valueType": "boolean", "description": "传空值时是否执行。"},
        "nodataFlag": {"required": False, "valueType": "boolean", "description": "未找到数据时的状态标志。"},
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
        "opType": "opType",
        "updatePolicy": "updatePolicy",
        "needAdd": "needAdd",
        "nullOpflag": "nullOpflag",
        "nodataFlag": "nodataFlag",
        "filterCondition": "_filterInput",
        "updateId": "_updateId",
        "updateFieldCondition": "_updateFieldCondition",
        "basisValueFormula": "_basisValueFormula",
        "updates": "_setting_main",
        "mapping": "_setting_mapping",
        "constants": "_setting_constants",
        "formula": "_setting_formula",
        "detail": "_setting_detail",
        "syncType": "syncType",
        "workflowModule": "workflowModule",
        "workflowId": "workflowId",
    },

    "defaultData": {
        "nodataFlag": False,
        "nullOpflag": False,
        "needAdd": False,
        "updatePolicy": "ALL",
        "opType": "updateData",
        "syncType": "0",
    },

    "runtimeContext": {
        "inputs": ["FormData"],
        "outputs": ["FormData", "FormField", "SettingInfo", "accessId", "monitorId", "workflowData"],
    },

    "dataFields": {
        "ebActionId": {"type": "int|str", "required": True, "platformRef": "actionConfig"},
        "opType": {"type": "string", "required": True, "default": "updateData", "options": ["id", "updateData", "fieldUpdate"]},
        "targetForm": {"type": "object", "required": True, "subfields": ["groupName", "groupId", "id", "text", "type"]},
        "setting": {"type": "object", "required": True, "subfields": ["updatePolicy", "opType", "dataDrWithCalc", "main", "detail"]},
        "tableType": {"type": "array", "required": True},
        "appType": {"type": "array", "required": True},
        "person": {"type": "object", "required": True, "platformRef": "user_assignment"},
        "syncType": {"type": "string", "required": False, "default": "0"},
    },
}
