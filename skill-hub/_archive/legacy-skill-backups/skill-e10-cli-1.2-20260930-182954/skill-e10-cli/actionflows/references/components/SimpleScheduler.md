# 简单定时器（`SimpleScheduler`）

## 用途

按定时规则触发动作流（每天/每周/每月等）。

## Plan 位置

作为动作流的触发器（event）使用。

## 最小示例

```json
{
  "type": "SimpleScheduler",
  "params": {
    "rate": "<按 describe 填写>"
  }
}
```

参数的完整类型、默认值、动态必填和平台对象形状，使用 `component-search` 选型后再调用 `describe` 获取。
