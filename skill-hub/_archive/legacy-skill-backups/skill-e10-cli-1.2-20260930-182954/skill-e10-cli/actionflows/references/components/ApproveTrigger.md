# 流程触发（`ApproveTrigger`）

## 用途

流程提交、审批通过、流程结束等时机触发动作流。

## Plan 位置

作为动作流的触发器（event）使用。

## 最小示例

```json
{
  "type": "ApproveTrigger",
  "params": {
    "workflowPath": "<按 describe 填写>",
    "triggerTiming": "<按 describe 填写>"
  }
}
```

参数的完整类型、默认值、动态必填和平台对象形状，使用 `component-search` 选型后再调用 `describe` 获取。
