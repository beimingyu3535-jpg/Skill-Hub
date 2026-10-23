# 发送消息（`SendMessage`）

## 何时使用

向人员、角色、全员或上游人员字段发送 IM 消息。

## 先查询

固定接收人查询当前租户人员；上游负责人等动态接收人使用本次上下文；标题和正文中的动态片段也使用本次上下文。

## 不可猜测

标题和内容按需求选固定文本或 `parts` 模板；纯字符串保持固定值，只有 `parts` 模板才进入设计器的消息专用编辑器。模板会编译成“正文文本 + `#{paramN}` 占位符 + 每个占位符的独立绑定”，对应手动配置时右侧的形式。**本 Skill 生成消息标题/内容时统一使用 `parts` 模板**，不要把通用函数/公式对象直接作为消息正文输入；这只是本 Skill 的生成约定，不代表平台其他场景不能使用函数。`parts` 的动态项支持 `context`、`system_variable`、`variable`、`constant`，后两者必须按 `references/dynamic_resources.md` 使用真实资源或计划定义。需要拼接上下文时，必须拆成 `parts`，例如：

```json
{
  "parts": [
    {"type":"text","value":"批次任务："},
    {"type":"context","paramKey":"<真实任务编号paramKey>","label":"任务编号"},
    {"type":"text","value":"，设备："},
    {"type":"context","paramKey":"<真实设备编号paramKey>","label":"设备编号"}
  ]
}
```

需要动态接收人时传 `receiver: {"type":"context","paramKey":"<真实人员字段paramKey>","label":"<字段名>"}`，不能把人员字段当固定人员 ID，也不能省略 `paramKey`。模板上下文只传 `paramKey` 和 `label`，由 CLI 按消息编辑器的动态片段结构编译，并绑定当前触发节点。对定时批量、按日期字段、表单数据等 e-builder 记录触发器，未显式提供链接时 CLI 自动生成 PC/移动端详情链接：`formId` 为触发表单 ID 固定值，`dataId` 为上游“数据ID”动态上下文。显式 `pcLink` / `mobileLink` 会覆盖该默认行为。

## 最小计划

`receiver`、`msgTitle`、`msgContent`。
