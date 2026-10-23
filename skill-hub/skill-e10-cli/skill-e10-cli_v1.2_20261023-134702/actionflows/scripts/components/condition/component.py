"""条件分支 (Condition)"""

COMPONENT = {
    "type": "Condition",
    "nodeRole": "action",
    "description": "根据上游字段值判断进入哪个分支。支持 if/else if/else。条件字段必须是上游节点 component-context 返回的真实 paramKey。",

    "display": {
        "typeName": "条件分支",
        "componentName": "条件分支",
        "componentDesc": "如果...否则...",
        "icon": "Icon-Screening-conditions",
    },

    "params": {
        "branches": {
            "required": True,
            "description": "分支列表。第一个分支为 if，最后一个 condition.type=else 为 else。每个分支包含 condition 和 actions。例：[{\"condition\":{\"type\":\"if\",\"field\":\"<paramKey>\",\"operator\":\"eq\",\"value\":\"1\"},\"actions\":[{\"type\":\"ActionEbUpdate\",\"params\":{...}}]},{\"condition\":{\"type\":\"else\"},\"actions\":[]}]（field 为字段 paramKey，operator 见 condition_branch_rules.md 操作码 eq/neq/contains 等，actions 为动作对象数组）",
            "valueType": "array",
            "valueShape": "array",
        },
    },

    "dataMapping": {
        "branches": "branches",  # 由 build_condition_node 特殊处理
    },

    "defaultData": {"executeMethod": "1"},

    "runtimeContext": {
        "inputs": ["FormData"],
        "outputs": [],
    },

    "dataFields": {},
}
