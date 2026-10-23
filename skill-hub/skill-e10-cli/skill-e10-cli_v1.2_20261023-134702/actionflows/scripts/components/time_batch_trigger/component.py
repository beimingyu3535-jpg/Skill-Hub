"""定时批量触发 (TimeBatchTrigger)

定时扫描数据源中符合条件的数据, 批量触发动作流.
平台数据 8 条样本 (询价单状态批量任务 / 物料成本分析月度年度).

与 DateTrigger 同样的两个坑:
  1. 新组件插入不能带 data.id (save() 里 data.getId() null 走新增分支, 非 null 走更新会 NPE)
  2. event.triggerType 必须是 'TimerTrigger' (缺省回退 WorkflowTrigger → 500)
"""

COMPONENT = {
    "type": "TimeBatchTrigger",
    "nodeRole": "event",
    "description": "定时扫描数据源符合条件的数据并批量触发动作流。"
                   "用于定时批量更新/处理符合条件的数据等场景。"
                   "数据源必须通过 form-applications + form-list 查到真实 id/groupId/text/type。",

    "display": {
        "typeName": "定时批量触发",
        "componentName": "定时批量触发",
        "componentDesc": "定时扫描数据源符合条件的数据并触发动作流",
        "icon": "Icon-scheduled-batch-triggering-mcolor",
        "componentNameLabel": 162622,
        "componentDescLabel": 214828,
    },

    "params": {
        "dataSource": {
            "required": True,
            "description": "要扫描的数据源（表单）。标准格式为 groupId/id；兼容 appId/tableId 别名，生成前会按当前租户实时补齐表名。",
            "valueType": "platform_reference",
            "referenceType": "ebuilder_form",
            "valueShape": "object",
        },
        "rate": {
            "required": True,
            "description": "触发频率类型（plan 语义，编译器转为真实 rate）：1=每天, 2=每周, 3=每月, 4=一次性, 5=Cron。",
            "valueType": "enum",
            "default": "1",
            "options": [
                {"value": "1", "label": "每天"},
                {"value": "2", "label": "每周"},
                {"value": "3", "label": "每月"},
                {"value": "4", "label": "一次性"},
                {"value": "5", "label": "Cron表达式"},
            ],
        },
        "hour": {
            "required": False,
            "description": "触发时间（小时，0-23），如 [\"2\",\"8\"]。",
            "valueType": "array",
            "valueShape": "array",
        },
        "cycle": {
            "required": False,
            "description": "间隔周期（真实数据 cycle=0/1，cycleNum 同值）。",
            "valueType": "string",
            "default": "1",
        },
        "day": {
            "required": False,
            "description": "rate=2(每周) 时指定星期几（1-7），rate=3(每月) 时指定几号（1-31）。",
            "valueType": "array",
            "valueShape": "array",
        },
        "month": {
            "required": False,
            "description": "rate=3(每月) 时指定月份（真实样本 1-12 全选）。",
            "valueType": "array",
            "valueShape": "array",
        },
        "startTime": {
            "required": False,
            "description": "开始时间（如 '2024-07-04 10:10'）。",
            "valueType": "string",
        },
        "endTime": {
            "required": False,
            "description": "结束时间（可选）。",
            "valueType": "string",
        },
        "cornString": {
            "required": False,
            "description": "Cron 表达式（rate=cron 时使用，真实样本如 '0 0 * * * ?'）。",
            "valueType": "string",
        },
        "radioVal": {
            "required": False,
            "description": "真实调度细分方式。仅在需要精确复刻时使用：cycle/hour/week/day/atWeek/lastWeek；与 rate 对应，不能和 day/week 等字段矛盾。",
            "valueType": "enum",
        },
        "week": {"required": False, "description": "按周时的星期数组（1-7）。", "valueType": "array", "valueShape": "array"},
        "atWeek": {"required": False, "description": "按月时第几周数组。radioVal=atWeek 时必填。", "valueType": "array", "valueShape": "array"},
        "atWeekDetail": {"required": False, "description": "按月第几周的星期数组。radioVal=atWeek 时必填。", "valueType": "array", "valueShape": "array"},
        "lastWeek": {"required": False, "description": "按月最后一周的星期数组。radioVal=lastWeek 时必填。", "valueType": "array", "valueShape": "array"},
        "queryFields": {"required": False, "description": "批量查询输出字段；不提供时自动读取数据源全部字段。", "valueType": "array", "valueShape": "array"},
        "orderFields": {"required": False, "description": "查询排序字段的真实对象数组。", "valueType": "array", "valueShape": "array"},
        "openRetryFlag": {"required": False, "description": "是否启用失败重试。", "valueType": "boolean"},
        "filterCondition": {
            "required": False,
            "description": "批量筛选条件（真实结构 filterInput）。日期字段可使用系统日期值 {today}/{yesterday}/{tomorrow} 等，运行时解析，禁止生成时写死日期。",
            "valueType": "object",
            "valueShape": "object",
        },
        "operator": {
            "required": True,
            "description": "操作人。plan 传单个对象 {\"id\":\"<人员id>\",\"name\":\"<姓名>\"}（编译器内部转数组）；前端保存必填，必须来自 recipient-search。",
            "valueType": "platform_reference",
            "referenceType": "user_assignment",
            "valueShape": "object",
        },
    },

    "dataMapping": {
        "dataSource": "_timeBatchDataSource",
        "rate": "rate",
        "startTime": "startTime",
        "endTime": "endTime",
        "cycle": "cycle",
        "hour": "hour",
        "day": "day",
        "month": "month",
        "cornString": "cornString",
        "radioVal": "radioVal",
        "week": "week",
        "atWeek": "atWeek",
        "atWeekDetail": "atWeekDetail",
        "lastWeek": "lastWeek",
        "queryFields": "queryFields",
        "orderFields": "orderFields",
        "openRetryFlag": "openRetryFlag",
        "filterCondition": "filterInput",
        "operator": "operator",
    },

    "defaultData": {
        "radioVal": "cycle",
        "rate": "3",
        "cycle": 1,
        "openRetry": False,
        "openRetryFlag": False,
        "physical": True,
        "hourDb": "",
        "dayDb": "",
        "weekDb": "",
        "monthDb": "",
        "atWeekDb": "",
        "atWeekDetailDb": "",
        "lastWeekDb": "",
        "cornString": "",
        "queryFields": [],
    },

    # 关键: 真实 TimeBatchTrigger event.triggerType='TimerTrigger'.
    "triggerType": "TimerTrigger",
    "triggerTypeName": "定时批量触发",

    "runtimeContext": {
        "inputs": [],
        "outputs": ["FormData", "queryFields"],
    },

    "dataFields": {
        "dataSource": {"type": "object", "required": True, "subfields": ["id", "groupId", "text", "type"]},
        "filterInput": {"type": "object", "required": True},
        "rate": {"type": "string", "required": True, "default": "3"},
        "radioVal": {"type": "string", "required": True, "default": "cycle"},
        "cycle": {"type": "int|str", "required": True, "default": 1},
        "hour": {"type": "array<string>", "required": False},
        "day": {"type": "array<string>", "required": False},
        "month": {"type": "array<string>", "required": False},
        "startTime": {"type": "string", "required": False},
        "endTime": {"type": "string", "required": False},
        "cornString": {"type": "string", "required": False},
        "operator": {"type": "array", "required": True},
        "queryFields": {"type": "array", "required": False},
        "orderFields": {"type": "array", "required": False},
        "week": {"type": "array<string>", "required": False},
        "atWeek": {"type": "array<string>", "required": False},
        "atWeekDetail": {"type": "array<string>", "required": False},
        "lastWeek": {"type": "array<string>", "required": False},
        "openRetryFlag": {"type": "boolean", "required": False},
        "physical": {"type": "boolean", "required": True, "default": True},
    },
}
