"""创建日程 (ScheduleCreate)

流程触发后自动生成日程记录 (日程/日历系统集成).
前端组件类名 ScheduleCreate (目录 schedule/create); 后端 ScheduleCreateComponent 激活.

说明:
  - 真实 1068 条动作流中 0 条使用 (日程系统集成组件, 依赖 RemoteAgendaService)
  - ScheduleInfoDTO 字段全部是 FormulaBean (title/startTime/endTime/participants/content 等)
    + 简单字段 (allDay/placeChoice/secret)
  - save() 与 DateTrigger 同规则: 新组件插入不带 data.id (data.getId() null 走新增)
"""

COMPONENT = {
    "type": "ScheduleCreate",
    "nodeRole": "action",
    "description": "流程触发后自动生成日程记录。"
                   "用于日程联动等场景。"
                   "创建人通过 recipient-search 查到真实人员 id + name。",

    "display": {
        "typeName": "创建日程",
        "componentName": "创建日程",
        "componentDesc": "流程触发后自动生成日程记录",
        "icon": "Icon-eb-mcolor",
    },

    "params": {
        "creatorUser": {
            "required": True,
            "description": "日程创建人。用 recipient-search 查到真实人员，plan 传 {\"id\":\"<人员id>\",\"name\":\"<姓名>\"}。",
            "valueType": "platform_reference",
            "referenceType": "user_assignment",
            "valueShape": "object",
        },
        "title": {
            "required": True,
            "description": "日程标题。plan 传字符串；动态引用时传 {\"type\":\"context\",\"paramKey\":\"<本次 component-context 返回的原始键>\",\"label\":\"...\"}。",
            "valueType": "string",
        },
        "startTime": {
            "required": True,
            "description": "开始时间（格式：YYYY-MM-DD HH:mm:ss）。plan 传字符串（编译器内部转 FormulaBean 对象）。",
            "valueType": "string",
        },
        "endTime": {
            "required": True,
            "description": "结束时间（格式：YYYY-MM-DD HH:mm:ss）；前端保存必填。plan 传字符串（编译器内部转 FormulaBean 对象）。",
            "valueType": "string",
        },
        "allDay": {
            "required": False,
            "default": False,
            "description": "是否全天日程。",
            "valueType": "boolean",
        },
        "participants": {
            "required": False,
            "description": "参与人。先 recipient-search，传人员 Browser 对象数组，不能传逗号分隔 ID。",
            "valueType": "array",
            "valueShape": "array",
        },
        "manager": {"required": True, "description": "日程负责人。先 recipient-search，传 {id,name}。", "valueType": "platform_reference", "referenceType": "user_assignment", "valueShape": "object"},
        "sharedUsers": {"required": False, "description": "日程共享人。先 recipient-search，传人员对象数组。", "valueType": "array", "valueShape": "array"},
        "scheduleType": {"required": False, "description": "日程类型。使用 calendarTypeBrowser 选择器返回的资源对象；当前 Skill 未提供专用查询命令，须由用户显式提供真实资源对象，否则拒绝生成。", "valueType": "platform_reference", "referenceType": "calendar_type", "valueShape": "object"},
        "meetingRoom": {"required": False, "description": "会议室地点。使用 mt_room 选择器返回的资源对象数组；placeChoice=1 时使用。当前 Skill 未提供专用查询命令，须由用户显式提供真实资源对象，否则拒绝生成。", "valueType": "array", "valueShape": "array"},
        "otherMeetingRoom": {"required": False, "description": "其他会议地点文本；placeChoice=2 时使用。", "valueType": "string"},
        "customFormSetting": {"required": False, "description": "日程自定义信息原生 {main,detail} 结构；先读取 /schedule/getFormField。", "valueType": "object", "valueShape": "ActionDataProps"},
        "content": {
            "required": False,
            "description": "日程内容/备注。",
            "valueType": "string",
        },
        "placeChoice": {
            "required": False,
            "default": "1",
            "description": "地点类型：1=会议室 / 2=其他地点。",
            "valueType": "string",
        },
        "secret": {
            "required": False,
            "default": "1",
            "description": "可见范围：1=上级可见 / 2=仅自己可见。",
            "valueType": "string",
        },
    },

    "dataMapping": {
        # ScheduleCreate 走专用转换 _map_schedule_create (draft_to_real.py):
        #   title/startTime 等是 FormulaBean, 通用平铺无法表达.
    },

    "defaultData": {
        "ebActionId": "-1",
        "allDay": False,
        "placeChoice": "1",
        "secret": "1",
    },

    "runtimeContext": {
        "inputs": ["FormData"],
        "outputs": [],
    },

    "dataFields": {
        "creatorUser": {"type": "object", "required": True, "platformRef": "user_assignment"},
        "title": {"type": "object", "required": True},
        "startTime": {"type": "object", "required": True},
        "endTime": {"type": "object", "required": True},
        "allDay": {"type": "boolean", "required": True, "default": False},
        "participants": {"type": "object", "required": False},
        "managerFormulaId": {"type": "object", "required": True},
        "sharedFormulaId": {"type": "object", "required": False},
        "typeFormulaId": {"type": "object", "required": False},
        "meetingRoom": {"type": "object", "required": False},
        "otherMeetingRoom": {"type": "object", "required": False},
        "settingId": {"type": "object", "required": False},
        "content": {"type": "object", "required": False},
        "placeChoice": {"type": "string", "required": False, "default": "1"},
        "secret": {"type": "string", "required": False, "default": "1"},
        "ebActionId": {"type": "int|str", "required": True, "platformRef": "actionConfig"},
        "id": {"type": "string", "required": False, "platformRef": "actionConfig"},
    },
}
