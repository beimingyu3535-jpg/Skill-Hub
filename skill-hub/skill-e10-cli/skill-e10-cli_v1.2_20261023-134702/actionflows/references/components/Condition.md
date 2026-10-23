# 条件分支（`Condition`）

## 用途

根据上游字段值判断进入哪个分支。支持 if/else if/else。条件字段必须是上游节点 component-context 返回的真实 paramKey。

## Plan 位置

作为动作流的动作（action）使用。

## 最小示例

```json
{
  "type": "Condition",
  "params": {
    "branches": "<按 describe 填写>"
  }
}
```

参数的完整类型、默认值、动态必填和平台对象形状，使用 `component-search` 选型后再调用 `describe` 获取。
