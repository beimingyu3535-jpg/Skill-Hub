# 创建日程（`ScheduleCreate`）

## 用途

流程触发后自动生成日程记录。用于日程联动等场景。创建人通过 recipient-search 查到真实人员 id + name。

## Plan 位置

作为动作流的动作（action）使用。

## 最小示例

```json
{
  "type": "ScheduleCreate",
  "params": {
    "creatorUser": "<按 describe 填写>",
    "title": "<按 describe 填写>",
    "startTime": "<按 describe 填写>",
    "endTime": "<按 describe 填写>",
    "manager": "<按 describe 填写>"
  }
}
```

参数的完整类型、默认值、动态必填和平台对象形状，使用 `component-search` 选型后再调用 `describe` 获取。
