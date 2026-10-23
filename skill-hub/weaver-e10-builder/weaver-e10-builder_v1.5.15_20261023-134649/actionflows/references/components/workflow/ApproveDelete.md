# 删除流程（`ApproveDelete`）

## 何时使用

将指定流程实例移入回收站。`requestId` 会按前端协议生成一个 `type=8` 的 `multipleSelect` JSON FormulaBean 容器，容器子项可以是固定流程实例或动态公式。

`ApproveDelete` 只负责移入回收站。CLI 另提供 `ApproveCompletelyDelete` 类型，但它是 CLI 新增类型，不代表当前前端和后端已经注册；使用前需要确认目标平台版本支持该动作。

## 先查询

确认真实实例和操作人。

## 不可猜测

删除实例具有副作用，实例来源必须可追溯。

## 最小计划

`requestId`、`operator`。
