"""简单定时器 (SimpleScheduler)"""

COMPONENT = {
    "type": "SimpleScheduler",
    "nodeRole": "event",
    "description": "按定时规则触发动作流（每天/每周/每月等）。",

    "display": {
        "typeName": "简单定时器",
        "componentName": "简单定时器",
        "componentDesc": "按定时规则触发动作流",
        "icon": "Icon-simple-timer-mcolor",
    },

    "params": {
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
            "description": "触发时间（小时，0-23），如 [\"2\",\"8\"] 表示凌晨2点和早上8点。",
            "valueType": "array",
            "valueShape": "array",
        },
        "cycle": {
            "required": False,
            "description": "间隔周期。如 cycle=2, rate=1(每天) 表示每隔2天执行；rate=3(每月) 时配合 day 指定几号。",
            "valueType": "string",
            "default": "1",
        },
        "day": {
            "required": False,
            "description": "rate=2(每周) 时指定星期几（1-7），rate=3(每月) 时指定几号（1-31）。",
            "valueType": "array",
            "valueShape": "array",
        },
        "startTime": {
            "required": False,
            "description": "开始时间（可选）。",
            "valueType": "string",
        },
        "endTime": {
            "required": False,
            "description": "结束时间（可选）。",
            "valueType": "string",
        },
        "cornString": {
            "required": False,
            "description": "Cron 表达式（rate=cron 时使用）。",
            "valueType": "string",
        },
    },

    "dataMapping": {
        "rate": "rate",
        "startTime": "startTime",
        "radioVal": "radioVal",
        "cycle": "cycle",
        "hour": "hour",
        "day": "day",
        "week": "week",
        "month": "month",
        "cornString": "cornString",
        "endTime": "endTime",
        "openRetry": "openRetry",
    },

    "defaultData": {"rate": "1", "openRetry": False},

    "runtimeContext": {
        "inputs": [],
        "outputs": [],
    },

    "dataFields": {
        "rate": {"type": "string", "required": True, "default": "1"},
        "cycle": {"type": "string", "required": False},
        "hour": {"type": "array<string>", "required": False},
        "day": {"type": "array<string>", "required": False},
        "startTime": {"type": "string", "required": False},
        "endTime": {"type": "string", "required": False},
        "cornString": {"type": "string", "required": False},
        "openRetry": {"type": "boolean", "required": False, "default": False},
    },

    # 定时器是事件节点，触发类型需要特殊标记
    "triggerType": "TimerTrigger",
    "triggerTypeName": "定时或指定时间触发",
}
