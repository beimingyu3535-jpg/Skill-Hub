# 新建文档（`DocumentSave`）

## 何时使用

在目标目录新建一篇文档。

## 先查询

查询目录、操作人及文档属性设置 DTO。固定 `fileFolder` 会由 CLI 调用文档目录 Browser 接口 `esbCreateFolderComponentFolder`，使用当前登录租户返回的真实文件夹对象；动态 `fileFolder` FormulaBean 不走目录查询。

## 不可猜测

标题、目录、操作人和 `setting` 缺一不可；正文与附件只接受真实 DTO 或文件引用。

## 最小计划

`docTitle`、`fileFolder`、`operatorId`、`setting`。
