# 彻底删除流程（`ApproveCompletelyDelete`）

## 重要说明

这是 CLI 提供的独立组件类型，CLI 不会修改前端或后端代码。当前前端/后端若未注册该类型，生成的设计保存请求可能被平台拒绝；请先确认目标平台支持。

## 参数

- `requestIds`：一个或多个流程实例 ID。按前端参考结构编译为 `type=8`、`formulaType=json` 的 `multipleSelect` FormulaBean；支持动态赋值对象、固定值和已构造的 FormulaBean。
- `operator`：操作人。按人员动态赋值规则编译为人员 FormulaBean。

示例里的上下文对象是语义输入；实际生成时，CLI 优先使用 `getComponentContext` 返回的真实字段元数据补齐 `frontId`、`paramKey` 等信息，不会根据字段名凭空生成 `frontId`。

## 示例

```json
{
  "requestIds": {
    "kind": "context",
    "paramKey": "requestIds",
    "label": "流程ID列表"
  },
  "operator": {
    "kind": "context",
    "paramKey": "form-1.operator",
    "label": "操作人"
  }
}
```
