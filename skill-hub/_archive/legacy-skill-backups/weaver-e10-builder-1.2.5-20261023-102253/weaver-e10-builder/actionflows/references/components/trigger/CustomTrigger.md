# 自定义事件触发（`CustomTrigger`）

## 何时使用

需求明确要求由平台自定义事件主动触发动作流时使用。它不是 e-builder 表单数据变化触发，也不是按钮触发。

## 参数

唯一必填参数是 `customData`，新建时必须按后端 `CustSetFormDto` 组装。顶层字段为 `customId`、`formType`、`businessModule`、`tableList`、`deleteTableIds` 和 `appId`：`customId` 必须传空字符串，由 `CustSetFormService#saveCustSetForm` 生成组件关联 ID；`formType` 为 `input`；`deleteTableIds` 新建传空数组；`appId` 由编译器注入当前动作流应用 ID。不要使用旧的 `tables`/`SETTING` 结构。

`tableList` 的主表需要 `id`、`formId`、`showName`、`isMain: true`、`orderNum` 和 `fields`；明细表需要 `id`、`showName`、`isMain: false`、`orderNum` 和 `fields`，不设置 `formId`。字段需要 `id`、`paramName`、`showName`、`paramType`、`isRequired`、`fieldComments`。缺少 ID 时由编译器生成；字段 `paramName` 不能为空。

```json
{
  "event": {
    "type": "CustomTrigger",
    "params": {
      "customData": {
        "customId": "",
        "formType": "input",
        "businessModule": "",
        "tableList": [{
          "id": "<可选，缺失时生成>",
          "formId": "<主表可选，缺失时生成>",
          "showName": "",
          "isMain": true,
          "orderNum": 0,
          "fields": [{
            "id": "<可选，缺失时生成>",
            "paramName": "payload",
            "showName": "",
            "paramType": "string",
            "isRequired": false,
            "fieldComments": ""
          }]
        }],
        "deleteTableIds": []
      }
    }
  }
}
```

自定义参数的字段定义是业务特定的。根据需求新建时可以直接提供 `tableList` 和字段；`tableList` 或其中的 `fields` 为空时，设计器“输入参数设置”就是空白。已有组件的更新场景如需保留平台生成的 `customId`，应使用平台回读 DTO，不要把更新 DTO 当作新建 DTO。

根触发器图标不是 `Icon-custom-trigger`，编译器统一保存为 `Icon-N-Triggerrul`。

## 上下文

触发后业务字段上下文根为 `SelectParams`，可引用 `SelectParams.<主表/明细表路径>`；同时可使用平台提供的 `FormField`、`SettingInfo`、`accessId` 和 `monitorId`。不要将自定义触发字段编译为 `FormData`。
