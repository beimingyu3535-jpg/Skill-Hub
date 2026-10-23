# 表单数据触发（`EventFormData`）

## 用途

e-builder 表单数据新增/更新/删除后自动触发动作流。用于数据触发（表单数据变动 → 发起新流程/更新关联数据）等场景。目标表单必须通过 form-applications + form-list 查到真实 id/groupId/text。

## Plan 位置

作为动作流的触发器（event）使用。

## 最小示例

```json
{
  "type": "EventFormData",
  "params": {
    "targetForm": "<按 describe 填写>",
    "triggerTimes": "<按 describe 填写>"
  }
}
```

参数的完整类型、默认值、动态必填和平台对象形状，使用 `component-search` 选型后再调用 `describe` 获取。
