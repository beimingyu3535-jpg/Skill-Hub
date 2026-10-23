"""数据源查询 (EnquiryForm)"""

COMPONENT = {
    "type": "EnquiryForm",
    "nodeRole": "action",
    "description": "查询指定数据源下的数据。用于校验拦截（先查台账是否已有记录）、数据准备等场景。"
                   "数据源必须通过 form-list / 数据源接口查到真实 id + text。",

    "display": {
        "typeName": "数据源查询",
        "componentName": "数据源查询",
        "componentDesc": "查询指定数据源下面的数据",
        "icon": "Icon-Data-preprocessing",
        "componentNameLabel": 240694,
        "componentDescLabel": 240695,
    },

    "params": {
        "dataSource": {
            "required": True,
            "description": "要查询的数据源（表单/数据集）。表单标准格式为 groupId/id；兼容 appId/tableId 别名，生成前会按当前租户实时补齐表名。"
                           "例（表单）：{\"groupId\":\"<应用id>\",\"id\":\"<表单id>\"}；数据集/系统数据源：{\"id\":\"<数据源id>\",\"text\":\"<名称>\",\"type\":\"<类型>\"}",
            "valueType": "platform_reference",
            "referenceType": "ebuilder_form",
            "valueShape": "object",
        },
        "person": {
            "required": True,
            "description": "查询操作人。用 recipient-search 查到真实人员，plan 传 {\"id\":\"<人员id>\",\"name\":\"<姓名>\"}；"
                           "EnquiryForm 真实 data.person 必填，不能留空公式。",
            "valueType": "platform_reference",
            "referenceType": "user_assignment",
            "valueShape": "object",
        },
        "filter": {
            "required": False,
            "description": "过滤条件（可选）。[{field, operator, value}]，value 可引用流程上下文 FormData.xxx。",
            "valueType": "array",
            "valueShape": "array",
            "itemSchema": {"requiredKeys": ["field", "operator", "value"]},
        },
        "queryFields": {
            "required": False,
            "description": "要返回的字段列表 [{id, content}]。不填默认返回全部。",
            "valueType": "array",
            "valueShape": "array",
            "itemSchema": {"requiredKeys": ["id"]},
        },
        "opType": {
            "required": False,
            "default": "list",
            "description": "返回模式：list=列表，groupFields=分组汇总。数量不是模式，使用 countFlag=true 后从 Response.response.count 读取。",
            "valueType": "enum",
            "options": [
                {"value": "list", "label": "返回数据列表"},
                {"value": "groupFields", "label": "分组汇总"},
            ],
        },
        "countFlag": {
            "required": False,
            "default": False,
            "description": "是否返回总数。",
            "valueType": "boolean",
        },
        "nodataFlag": {
            "required": False,
            "default": True,
            "description": "无数据处理开关：开启时无数据仍继续，关闭时无数据失败。不可把它当作“查到数据即报错”的重复校验能力。当前平台 Condition 左值只接受流程表单字段，不能使用 Response.response.count；此类查重拦截必须明确报未支持。",
            "valueType": "boolean",
        },
        "authorityFlag": {"required": False, "default": "0", "description": "数据权限：0=全部数据，1=操作人权限数据。", "valueType": "enum", "options": [{"value":"0","label":"全部数据"},{"value":"1","label":"操作人权限数据"}]},
        "parseMark": {"required": False, "default": True, "description": "返回字段名称开关。", "valueType": "boolean"},
        "orderFields": {"required": False, "description": "排序字段原生数组；字段必须来自实时 form-fields。", "valueType": "array", "valueShape":"array"},
        "formPageNo": {"required": False, "description": "当前页。", "valueType": "integer"},
        "formPageSize": {"required": False, "description": "每页条数。", "valueType": "integer"},
        "groupFields": {"required": False, "description": "分组字段原生数组，仅 opType=groupFields 使用。", "valueType": "array", "valueShape":"array"},
        "groupMessage": {"required": False, "description": "汇总内容原生数组，仅 opType=groupFields 使用。", "valueType": "array", "valueShape":"array"},
    },

    "dataMapping": {
        "dataSource": "_enquiryDataSource",
        "person": "_person",
        "filter": "_enquiryFilter",
        "queryFields": "queryFields",
        "opType": "opType",
        "countFlag": "countFlag",
        "nodataFlag": "nodataFlag",
        "authorityFlag": "authorityFlag",
        "parseMark": "parseMark",
        "orderFields": "orderFields",
        "formPageNo": "formPageNo",
        "formPageSize": "formPageSize",
        "groupFields": "groupFields",
        "groupMessage": "groupMessage",
        "person": "_person",
        "workflowModule": "workflowModule",
        "workflowId": "workflowId",
    },

    "defaultData": {
        "opType": "list",
        "countFlag": False,
        "nodataFlag": True,
        "parseMark": True,
        "authorityFlag": "0",
    },

    "runtimeContext": {
        "inputs": ["FormData", "dataSource"],
        "outputs": ["queryFields", "dataOneOptions", "count"],
    },

    "dataFields": {
        "dataSource": {"type": "object", "required": True, "subfields": ["sourceId", "groupId", "id", "text", "type", "enquiryId"]},
        "filterInput": {"type": "object", "required": True, "subfields": ["isNewFilter", "isParent", "datas"]},
        "queryFields": {"type": "array", "required": False, "subfields": ["formId", "id", "content"]},
        "person": {"type": "object", "required": True, "platformRef": "user_assignment"},
        "opType": {"type": "string", "required": True, "default": "list", "options": ["list", "groupFields"]},
        "countFlag": {"type": "boolean", "required": False},
        "nodataFlag": {"type": "boolean", "required": False},
    },
}
