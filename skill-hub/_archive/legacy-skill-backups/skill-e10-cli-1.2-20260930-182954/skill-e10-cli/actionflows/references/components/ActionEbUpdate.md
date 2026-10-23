# 更新表单数据（`ActionEbUpdate`）

## 用途

按条件或 ID 更新 e-builder 表单数据。支持字段映射和固定值。

## Plan 位置

作为动作流的动作（action）使用。

## 最小示例

```json
{
  "type": "ActionEbUpdate",
  "params": {
    "targetForm": "<按 describe 填写>",
    "person": "<按 describe 填写>"
  }
}
```

参数的完整类型、默认值、动态必填和平台对象形状，使用 `component-search` 选型后再调用 `describe` 获取。
