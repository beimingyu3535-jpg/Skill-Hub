# 终止（`Output`）

## 用途

动作流主链结束节点。由编译器自动补充，模型不需要写入 semantic_plan。

## Plan 位置

作为动作流的结束节点；由编译器补充，不要手写进 semantic_plan使用。

## 最小示例

```json
{
  "type": "Output",
  "params": {}
}
```

参数的完整类型、默认值、动态必填和平台对象形状，使用 `component-search` 选型后再调用 `describe` 获取。
