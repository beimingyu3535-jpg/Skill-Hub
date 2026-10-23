"""新建会议 (MeetingCreate)

流程触发后自动创建会议 (会议系统集成).
前端组件类名 MeetingCreate (目录 createPendingMeeting).

说明:
  - 真实 1068 条动作流中 0 条使用 (会议系统集成组件, 依赖远程会议服务)
  - 前端通过 getMeetingField/getCustomMeetingField 获取会议基础字段、选项及自定义字段；
    Skill 的只读 meeting-fields 命令调用同源接口，不假定本地静态字段清单
  - 保存结构: operators(操作人公式)/moduleType(workflow)/type(会议状态)/setting(会议信息)/flag(关联标识)
  - save() 与 DateTrigger 同规则: 新组件插入不带 data.id
"""

COMPONENT = {
    "type": "MeetingCreate",
    "nodeRole": "action",
    "description": "流程触发后自动创建会议。"
                   "用于会议联动等场景。"
                   "操作人通过 recipient-search 查到真实人员 id + name。",

    "display": {
        "typeName": "新建会议",
        "componentName": "新建会议",
        "componentDesc": "流程触发后自动创建会议",
        "icon": "Icon-eb-mcolor",
    },

    "params": {
        "operators": {
            "required": True,
            "description": "会议创建人（操作人）。用 recipient-search 查到真实人员，plan 传 {\"id\":\"<人员id>\",\"name\":\"<姓名>\"}。",
            "valueType": "platform_reference",
            "referenceType": "user_assignment",
            "valueShape": "object",
        },
        "moduleType": {
            "required": False,
            "default": "workflow",
            "description": "关联业务类型（前端 selectModuleData 只有 workflow）。",
            "valueType": "string",
        },
        "flag": {
            "required": False,
            "description": "关联标识。前端为 workflow/wfcRequest Browser，仅支持固定选择的流程实例对象 {id,name}，用于把新会议关联到该流程实例。",
            "valueType": "platform_reference",
            "referenceType": "workflow_request",
            "valueShape": "object",
        },
        "meetingType": {
            "required": True,
            "description": "会议状态/类型（前端 FormSwitch 标记必填；值来自 meeting-fields 命令返回的 mtType/type 当前租户选项）。",
            "valueType": "string",
        },
        "meetingTitle": {
            "required": False,
            "description": "会议标题（会议信息 setting.name，固定值；等同于 meetingFields.name）。与 meetingFields.name 二选一必填。",
            "valueType": "string",
        },
        "secretLevel": {
            "required": False,
            "description": "会议密级。必须使用当前租户的真实枚举值；Skill 不猜选项 id。与 meetingFields.secretLevel 二选一必填。",
            "valueType": "select_value",
            "optionsSource": "meeting-fields.meetingFields.items.secretLevel",
        },
        "caller": {
            "required": False,
            "description": "会议召集人。传 recipient-search 的完整人员 Browser 对象；只给 {id,name} 时，生成前会按 id 回查并补全。等同于 meetingFields.caller。二者二选一必填。",
            "valueType": "platform_reference",
            "referenceType": "user",
        },
        "contacter": {
            "required": False,
            "description": "会议联系人。传 recipient-search 的完整人员 Browser 对象；只给 {id,name} 时，生成前会按 id 回查并补全。等同于 meetingFields.contacter。",
            "valueType": "platform_reference",
            "referenceType": "user",
        },
        "meetingFields": {
            "required": False,
            "description": "会议信息完整命名字段。仅固定值；人员/部门/会议室/客户传平台选择器返回的对象或对象数组。支持 name, mtType, secretLevel, caller, contacter, mtDesc, mtAccessorys, repeatRuleEx, beginDatetime, endDatetime, address, customizeAddress, remindType, 提醒细项, hrmMembers, orgMembers, totalMember, otherMembers, crmMembers, crmTotalMember。实时字段以 meeting-fields 返回为准。",
            "valueType": "object",
            "valueShape": "object",
            "fieldsSource": "meeting-fields",
        },
        "customFormSetting": {
            "required": False,
            "description": "会议自定义表单数据，使用平台原生 {main,detail} 结构；字段和明细表必须先从 meeting-fields.customMeetingFields.data.main / data.detail 实时读取。",
            "valueType": "object",
            "valueShape": "ActionDataProps",
            "fieldsSource": "meeting-fields.customMeetingFields",
        },
        "constants": {
            "required": False,
            "description": "兼容旧格式：会议信息字段 key → 固定值。新 plan 优先用 meetingFields；两者不能为同一字段给不同值。"
                           "⚠️ 上下文引用暂不支持（后端 saveCommonForm 对 type=3 bean 500，仅固定值 type=1 可保存）。",
            "valueType": "object",
            "valueShape": "object",
        },
    },

    "dataMapping": {
        # MeetingCreate 走专用转换 _map_meeting_create (draft_to_real.py):
        #   setting 是 Map<字段key, FormulaBean> 非表单结构, 通用 dataMapping 无法表达.
        "operators": "_meetingOperators",
        "moduleType": "moduleType",
        "meetingType": "type",
        "flag": "_meetingFlag",
    },

    "defaultData": {
        "moduleType": "workflow",
        "ebActionId": "-1",
    },

    "runtimeContext": {
        "inputs": ["FormData"],
        "outputs": [],
    },

    "dataFields": {
        "operators": {"type": "object", "required": True, "platformRef": "user_assignment"},
        "moduleType": {"type": "string", "required": True, "default": "workflow"},
        "type": {"type": "string", "required": False},
        "setting": {"type": "object", "required": True},
        "formSetting": {"type": "object", "required": False},
        "flag": {"type": "object", "required": False},
        "settingId": {"type": "string", "required": False},
        "flagId": {"type": "string", "required": False},
        "ebActionId": {"type": "int|str", "required": True, "platformRef": "actionConfig"},
        "id": {"type": "string", "required": False, "platformRef": "actionConfig"},
    },
}
