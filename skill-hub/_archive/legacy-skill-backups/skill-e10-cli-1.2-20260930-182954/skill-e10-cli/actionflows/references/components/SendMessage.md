# 消息提醒（`SendMessage`）

## 用途

发送站内消息提醒给指定人员。接收人必须通过 recipient-search 查到真实人员 ID + name。

## Plan 位置

作为动作流的动作（action）使用。

## 最小示例

```json
{
  "type": "SendMessage",
  "params": {
    "receiver": "<按 describe 填写>",
    "msgTitle": "<按 describe 填写>",
    "msgContent": "<按 describe 填写>"
  }
}
```

参数的完整类型、默认值、动态必填和平台对象形状，使用 `component-search` 选型后再调用 `describe` 获取。
