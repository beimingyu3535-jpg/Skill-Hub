# 按日期字段触发（`DateTrigger`）

## 用途

根据数据源中指定数据的日期字段定时触发动作流。用于定时触发（按表单日期字段 → 发起新流程/更新数据）等场景。数据源必须通过 form-applications + form-list 查到真实 id/groupId/text。

## Plan 位置

作为动作流的触发器（event）使用。

## 最小示例

```json
{
  "type": "DateTrigger",
  "params": {
    "dataSource": "<按 describe 填写>",
    "dateField": "<按 describe 填写>",
    "operator": "<按 describe 填写>"
  }
}
```

参数的完整类型、默认值、动态必填和平台对象形状，使用 `component-search` 选型后再调用 `describe` 获取。
