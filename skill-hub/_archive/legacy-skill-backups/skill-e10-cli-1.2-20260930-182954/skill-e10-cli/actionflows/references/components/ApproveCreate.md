# 新建流程（`ApproveCreate`）

## 用途

发起一个全新的独立流程（不是子流程）。用于流程结束后自动发起新流程、数据变动后发起流程等场景。目标流程必须通过 workflow-browser-list 查到真实 id + createFlowId + name。

## Plan 位置

作为动作流的动作（action）使用。

## 最小示例

```json
{
  "type": "ApproveCreate",
  "params": {
    "workflowPath": "<按 describe 填写>",
    "operator": "<按 describe 填写>",
    "requestName": "<按 describe 填写>"
  }
}
```

参数的完整类型、默认值、动态必填和平台对象形状，使用 `component-search` 选型后再调用 `describe` 获取。
