"""按日期字段触发 (DateTrigger)"""

COMPONENT = {
    "type": "DateTrigger",
    "nodeRole": "event",
    "description": "根据数据源中指定数据的日期字段定时触发动作流。"
                   "用于定时触发（按表单日期字段 → 发起新流程/更新数据）等场景。"
                   "数据源必须通过 form-applications + form-list 查到真实 id/groupId/text。",

    "display": {
        "typeName": "按日期字段触发",
        "componentName": "按日期字段触发",
        "componentDesc": "根据数据源中指定数据的日期字段触发",
        "icon": "Icon-triggering-by-date-field-mcolor",
        "componentNameLabel": 131943,
        "componentDescLabel": 214822,
    },

    "params": {
        "dataSource": {
            "required": True,
            "description": "要监听的数据源（表单）。标准格式为 groupId/id；兼容 appId/tableId 别名，生成前会按当前租户实时补齐表名。",
            "valueType": "platform_reference",
            "referenceType": "ebuilder_form",
            "valueShape": "object",
        },
        "dateField": {
            "required": True,
            "description": "触发依据的日期字段。用 form-fields 查到真实 id/name/text/type。",
            "valueType": "platform_reference",
            "referenceType": "ebuilder_field",
            "valueShape": "object",
        },
        "triggerDateTime": {
            "required": False,
            "default": "00:00",
            "description": "触发时间点（HH:mm）。",
            "valueType": "string",
        },
        "repeatType": {
            "required": False,
            "default": 1,
            "description": "重复类型：1=每日 / 2=每周 / 3=每月。",
            "valueType": "enum",
            "options": [
                {"value": "1", "label": "每日"},
                {"value": "2", "label": "每周"},
                {"value": "3", "label": "每月"},
            ],
        },
        "triggerDateType": {
            "required": False,
            "default": "3",
            "description": "提醒类型：0=准时 / 1=提前 / 2=延迟 / 3=当天。(真实数据 '1'/'2'/'3' 均为字符串)",
            "valueType": "string",
        },
        "beforeOrAfterNum": {
            "required": False,
            "default": 1,
            "description": "提前/延迟的天数（DTO 是 Integer）。",
            "valueType": "integer",
        },
        "beforeOrAfterGrade": {
            "required": False,
            "default": "0",
            "description": "提醒粒度：0=天 / 4=小时 / 5=分钟。DTO 是 Integer 但真实数据混用 str '0' 与 int 4/5。",
            "valueType": "string",
        },
        "numConstOrField": {
            "required": False, "description": "提前/延迟数量来源：numConst 固定整数，numField 表单整数字段。", "valueType": "enum",
            "options": [{"value": "numConst", "label": "固定值"}, {"value": "numField", "label": "字段值"}],
        },
        "numField": {"required": False, "description": "numConstOrField=numField 时的整数字段真实引用。", "valueType": "platform_reference", "referenceType": "ebuilder_field", "valueShape": "object"},
        "timeConstOrField": {
            "required": False, "description": "触发时间来源：timeConst 固定时间，timeField 日期时间字段；非日期字段可用 currentDateFix/currentDateField。", "valueType": "enum",
            "options": [
                {"value": "timeConst", "label": "固定时间"}, {"value": "timeField", "label": "字段时间"},
                {"value": "currentDateFix", "label": "当前日期固定时间"}, {"value": "currentDateField", "label": "当前日期字段时间"},
            ],
        },
        "timeField": {"required": False, "description": "timeConstOrField 为 timeField/currentDateField 时的时间字段真实引用。", "valueType": "platform_reference", "referenceType": "ebuilder_field", "valueShape": "object"},
        "remindFinishWay": {"required": False, "description": "repeatType=2 时结束方式：endDate/runDate；未设置表示不额外限制。", "valueType": "enum"},
        "remindEndDataVal": {"required": False, "description": "remindFinishWay=endDate 时的结束日期。", "valueType": "string"},
        "remindRunDayVal": {"required": False, "description": "remindFinishWay=runDate 时的持续次数。", "valueType": "integer"},
        "remindRunDayUnit": {"required": False, "description": "持续次数单位（前端枚举原值）。", "valueType": "string"},
        "executeMethod": {"required": False, "description": "日期到达后的执行方式，真实前端枚举原值，默认 1。", "valueType": "string"},
        "queryFields": {"required": False, "description": "触发后输出字段；不提供时自动读取数据源全部字段。", "valueType": "array", "valueShape": "array"},
        "operator": {
            "required": True,
            "description": "操作人。plan 传单个对象 {\"id\":\"<人员id>\",\"name\":\"<姓名>\"}（编译器内部转数组）；必须使用当前租户人员浏览器返回的真实对象。",
            "valueType": "platform_reference",
            "referenceType": "user_assignment",
            "valueShape": "object",
        },
        "filter": {
            "required": False,
            "description": "日期触发前的数据筛选条件。格式 [{field, operator, value}]；field 为字段 ID，operator 见 condition_branch_rules.md 操作码，value 支持字符串或上下文引用。",
            "valueType": "array",
            "valueShape": "array",
        },
    },

    "dataMapping": {
        "dataSource": "_dateDataSource",
        "dateField": "dateField",
        "triggerDateTime": "triggerDateTime",
        "repeatType": "repeatType",
        "triggerDateType": "triggerDateType",
        "beforeOrAfterNum": "beforeOrAfterNum",
        "beforeOrAfterGrade": "beforeOrAfterGrade",
        "numConstOrField": "numConstOrField",
        "numField": "numField",
        "timeConstOrField": "timeConstOrField",
        "timeField": "timeField",
        "remindFinishWay": "remindFinishWay",
        "remindEndDataVal": "remindEndDataVal",
        "remindRunDayVal": "remindRunDayVal",
        "remindRunDayUnit": "remindRunDayUnit",
        "executeMethod": "executeMethod",
        "queryFields": "queryFields",
        "operator": "operator",
        "filter": "dataFilter",
    },

    "defaultData": {
        "triggerDateTime": "00:00",
        "repeatType": 1,
        "triggerDateType": "3",
        "beforeOrAfterGrade": "0",
        "beforeOrAfterNum": 1,
        "numConstOrField": "numConst",
        "timeConstOrField": "timeConst",
        "endTimesType": "fix",
        "remindFinishWay": "",
        "remindEndData": "",
        "remindEndDataVal": "",
        "remindRunDay": "",
        "remindRunDayVal": "",
        "remindRunDayUnit": "",
        "operator": [],
        "timeField": "",
        "executeMethod": "1",
    },

    # 关键: 真实 DateTrigger event.triggerType='TimerTrigger'.
    # 缺这个字段会回退默认 WorkflowTrigger → 后端反序列化 500 "组件内部异常".
    "triggerType": "TimerTrigger",
    "triggerTypeName": "按日期字段触发",

    "runtimeContext": {
        "inputs": [],
        "outputs": ["FormData", "queryFields"],
    },

    "dataFields": {
        "dataSource": {"type": "object", "required": True, "subfields": ["groupId", "id", "text", "type", "isPhysical"]},
        "dateField": {"type": "object", "required": True, "subfields": ["objId", "id", "name", "text", "type", "compType", "formatType"]},
        "queryFields": {"type": "array", "required": True},
        "dataFilter": {"type": "object", "required": False},
        "triggerDateTime": {"type": "string", "required": True},
        "repeatType": {"type": "int", "required": True},
        "triggerDateType": {"type": "int", "required": True, "default": 3},
        "id": {"type": "string", "required": True, "platformRef": "actionConfig"},
        "numConstOrField": {"type": "string", "required": False},
        "numField": {"type": "object", "required": False},
        "timeConstOrField": {"type": "string", "required": False},
        "timeField": {"type": "object", "required": False},
        "remindFinishWay": {"type": "string", "required": False},
        "remindEndDataVal": {"type": "string", "required": False},
        "remindRunDayVal": {"type": "int|str", "required": False},
        "executeMethod": {"type": "string", "required": False},
        "operator": {"type": "array", "required": True},
    },
}
