# 删除流程（`ApproveDelete`）

## 何时使用

将指定流程实例移入回收站。`requestId` 会按前端协议生成一个 `type=8` 的 `multipleSelect` JSON FormulaBean 容器，容器子项可以是固定流程实例或动态公式。

当前平台只注册此删除组件；**不支持“彻底删除流程”**。不得生成或使用 `ApproveCompletelyDelete`，否则设计器保存会报组件内部异常。

## 先查询

确认真实实例和操作人。

## 不可猜测

删除实例具有副作用，实例来源必须可追溯。

## 最小计划

`requestId`、`operator`。
