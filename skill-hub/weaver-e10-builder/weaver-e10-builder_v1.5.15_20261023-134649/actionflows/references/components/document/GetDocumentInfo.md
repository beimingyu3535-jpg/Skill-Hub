# 获取文档信息（`GetDocumentInfo`）

## 何时使用

读取文档详情供后续节点使用。

## 先查询

确认文档 ID 来源与操作人。固定文档名称会通过当前租户的 `doc/document` Browser 接口补全为真实文档对象；动态 `docId` FormulaBean 不走 Browser 查询。

## 不可猜测

固定文档应使用真实 Browser 对象，上游值使用真实上下文。

## 最小计划

`docId`、`operatorId`。
