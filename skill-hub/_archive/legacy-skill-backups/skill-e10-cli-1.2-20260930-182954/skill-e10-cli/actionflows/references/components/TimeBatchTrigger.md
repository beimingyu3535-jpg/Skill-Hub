# 定时批量触发（`TimeBatchTrigger`）

## 用途

定时扫描数据源符合条件的数据并批量触发动作流。用于定时批量更新/处理符合条件的数据等场景。数据源必须通过 form-applications + form-list 查到真实 id/groupId/text/type。

## Plan 位置

作为动作流的触发器（event）使用。

## 最小示例

```json
{
  "type": "TimeBatchTrigger",
  "params": {
    "dataSource": "<按 describe 填写>",
    "rate": "<按 describe 填写>",
    "operator": "<按 describe 填写>"
  }
}
```

参数的完整类型、默认值、动态必填和平台对象形状，使用 `component-search` 选型后再调用 `describe` 获取。
