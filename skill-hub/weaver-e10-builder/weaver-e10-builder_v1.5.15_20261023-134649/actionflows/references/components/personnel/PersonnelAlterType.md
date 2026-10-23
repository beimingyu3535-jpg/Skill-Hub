# 人员状态变更

组件类型：`PersonnelAlterType`。先运行 `component-describe PersonnelAlterType`。

## 何时使用

用于提交试用、入职、续签、调动、解雇、退休、离职和返聘等人员状态变更表单。只修改简单的在职/离职账号状态时，使用 `AlterPersonStatus`。

## 生成前查询

1. 使用 `recipient-search` 取得操作人的当前租户 Browser 原对象；也可以使用当前用户或上游人员上下文。
2. 使用 `hrm-alter-type-fields {"personnelType":"redeploy"}` 按目标状态读取当前租户实时字段。不同 `personnelType` 的字段不能混用。

## 业务边界

- `personnelType` 是后端实体中的普通字符串，只支持 `trial`、`hire`、`extend`、`redeploy`、`dismiss`、`retire`、`quit`、`rehire`。
- plan 只传 `fieldAssignments`，格式为 `{ "字段ID或唯一字段名": 值 }`；不要手写后端 `setting` 或 `FormulaBean` DTO。
- 字段定义来自 `/api/bs/esb/setting/component/getHrmTypeField`，生成器会按实时 `items` 校验字段并使用真实字段 ID。字段名重名时必须传字段 ID。
- 文本字段生成前端 `textarea#...#` 容器，多选字段生成 `multipleSelect#...#` 的 JSON 容器，Browser 字段保留真实选择对象的 ID、名称和原始值。
- 后端 `save` 将 `operators` 保存为操作人公式，将 `setting` 保存为 CommonForm；因此本组件的 `setting` 是 `Map<String, FormulaBean>`，不属于 `EsbFormDataDto`，不会生成新增/更新表单的 `main/detail` 骨架。
- 至少提供一个字段赋值；字段定义或动态引用无法解析时停止生成。

## 语义计划形状

```json
{
  "type": "PersonnelAlterType",
  "params": {
    "operators": {"id": "<真实人员ID>", "name": "<真实姓名>"},
    "personnelType": "redeploy",
    "fieldAssignments": {
      "switchDate": "1",
      "newDepartment": {"id": "<部门ID>", "name": "<部门名称>"},
      "notice": ["同步薪资", "通知直属上级"]
    }
  }
}
```
