"""结束节点 (Output) — 编译器自动补充，模型不写入 semantic_plan。"""

COMPONENT = {
    "type": "Output",
    "nodeRole": "action",
    "description": "动作流主链结束节点。由编译器自动补充，模型不需要写入 semantic_plan。",

    "display": {
        "typeName": "终止",
        "componentName": "终止",
        "componentDesc": "动作流结束节点",
        "icon": "Icon-termination-1",
        "iconColor": "var(--danger)",
    },

    "params": {
        "outputStatus": {
            "required": False,
            "default": "1",
            "description": "输出状态: 1=成功(默认), 0=失败。真实数据主流 1 (×612)。失败时会触发 reminder 提醒配置。",
            "valueType": "enum",
            "options": [
                {"value": "1", "label": "成功"},
                {"value": "0", "label": "失败"},
            ],
        },
        "pageAction": {
            "required": False,
            "default": "0",
            "description": "结束后的页面动作: 0=无(默认, ×591), 1=跳转链接, 2=关闭窗口, 3=自定义跳转。",
            "valueType": "enum",
            "options": [
                {"value": "0", "label": "无"},
                {"value": "1", "label": "跳转链接"},
                {"value": "2", "label": "关闭窗口"},
                {"value": "3", "label": "自定义跳转"},
            ],
        },
    },

    "dataMapping": {
        "outputStatus": "outputStatus",
    },

    "defaultData": {
        "outputStatus": "1",
        "reminder": "0",
        "triggerFlag": False,
        "pageAction": "0",
        "nextAction": False,
        "fixedData": [],
        "reminderMsgFormula": "",
        "customOutputData": "",
    },

    "runtimeContext": {
        "inputs": [],
        "outputs": [],
    },

    "dataFields": {
        "outputStatus": {"type": "string", "required": False, "default": "1"},
    },
}
