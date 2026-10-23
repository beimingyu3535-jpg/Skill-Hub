"""消息提醒 (SendMessage)"""

COMPONENT = {
    "type": "SendMessage",
    "nodeRole": "action",
    "description": "发送站内消息提醒给指定人员。接收人必须通过 recipient-search 查到真实人员 ID + name。",

    "display": {
        "typeName": "消息提醒",
        "componentName": "消息提醒",
        "componentDesc": "向指定用户、群或渠道发送消息提醒",
        "componentNameLabel": 221877,
        "componentDescLabel": 211370,
        "icon": "Icon-Message-center-o",
    },

    "params": {
        "channelSetting": {
            "required": False,
            "description": "推送渠道的设计器原生配置数组（可选）。当前平台已有成功 SendMessage 节点可不含该字段；提供时必须来自平台渠道选择器/回读 JSON，Skill 不伪造渠道 ID 或结构。",
            "valueType": "array",
            "valueShape": "array",
        },
        "receiver": {
            "required": True,
            "description": "消息接收人。类型对应设计器「提醒对象」。type=user 时：单人用 {\"type\":\"user\",\"id\":\"<人员ID>\",\"name\":\"<姓名>\"}，多人用 {\"type\":\"user\",\"persons\":[{id,name},...]}（两者二选一，勿混用）。其他类型: 人员, 可加 userType (1当前人员/2直接上级/3所有上级/4本部门/5本分部/6当前岗位); 部门 {\"type\":\"department\",id,name, +departmentAttribute:[include_superior|subordinate|partTimeStaff]}; 分部 {\"type\":\"subcompany\",+同上附加}; 角色 {\"type\":\"role\",id,name, +roleLevel:\"0\"|\"1\"|\"2\" (0总部/1分部/2部门)}; 群组 {\"type\":\"group\"}; 岗位 {\"type\":\"position\",id,name, +positionLevel:\"1\"|\"2\"|\"3\" (1总部/2指定分部+positionLevelSubcompany/3指定部门+positionLevelDepartment), +positionAttribute:[\"partTimeStaff\"]}; 外部联系人 {\"type\":\"external\"}; 所有人 {\"type\":\"all\"}; 人员范围选择 {\"type\":\"employeeScope\"}; 人力资源条件 {\"type\":\"employeeShare\"}; 人员组织多选 {\"type\":\"employeeOrganization\"}。所有类型可加 seclevel:{\"min\":0,\"max\":100} 或简写 [0,100] 表示安全级别范围。人员/部门等具体对象须通过 recipient-search 等查询到真实 id+name。",
            "valueType": "platform_reference",
            "referenceType": "user_assignment",
            "valueShape": "object",
        },
        "msgTitle": {
            "required": True,
            "description": "消息标题。",
            "valueType": "string",
        },
        "msgContent": {
            "required": True,
            "description": "消息正文。可以使用上下文变量如 FormData.字段名。",
            "valueType": "string",
        },
        "pcLink": {"required": False, "description": "PC 端固定链接或上游公式值。", "valueType": "string"},
        "mobileLink": {"required": False, "description": "移动端固定链接或上游公式值。", "valueType": "string"},
        "senderType": {"required": False, "description": "发送者类型，默认 system；传平台已有节点回读的原始字符串。", "valueType": "string", "default": "system"},
        "customParams": {"required": False, "description": "自定义参数原生对象数组；必须使用设计器/回读的真实结构。", "valueType": "array", "valueShape": "array"},
    },

    "dataMapping": {
        "channelSetting": "channelSetting",
        "receiver": "_person",
        "msgTitle": "msgTitle",
        "msgContent": "msgContent",
        "pcLink": "pcLink",
        "mobileLink": "mobileLink",
        "senderType": "senderType",
        "customParams": "customParams",
        "workflowModule": "workflowModule",
        "workflowId": "workflowId",
    },

    "defaultData": {
        "moduleEvent": "8",
        "remaindModule": [{"id": "209", "content": "esb"}],
        "channelSetting": [{"channel": 1, "config": {"code": "", "aid": 110}}],
    },

    "runtimeContext": {
        "inputs": ["FormData"],
        "outputs": [],
    },

    "dataFields": {
        "channelSetting": {"type": "array", "required": False},
        "person": {"type": "object", "required": True},
        "shareList": {"type": "array", "required": False},
        "msgContent": {"type": "string", "required": True},
        "msgTitle": {"type": "string", "required": True},
        "pcLink": {"type": "object", "required": False},
        "mobileLink": {"type": "object", "required": False},
        "senderType": {"type": "string", "required": False, "default": "system"},
        "customParams": {"type": "array", "required": False},
    },
}
