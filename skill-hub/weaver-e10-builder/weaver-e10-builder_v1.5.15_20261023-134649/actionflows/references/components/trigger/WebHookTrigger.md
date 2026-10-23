# WebHook 请求触发（`WebHookTrigger`）

`WebHookTrigger` 对应前端 `custom-webhook` 和 Java `WebHookTriggerComponent`。它接收外部 HTTP 请求，按配置的请求参数触发动作流。

## 语义计划

```json
{
  "event": {
    "type": "WebHookTrigger",
    "params": {
      "requestUrl": "https://api.example.com/api/open-esb/server/webhook/trigger/order-created",
      "request": {
        "id": "webhook-request-1",
        "mappingId": "webhook-mapping-1",
        "tables": [
          {
            "name": "Params",
            "primaryKey": "Params",
            "tableId": "params-1",
            "tableData": [
              {
                "id": "request-id",
                "paramKey": "orderId",
                "paramName": "orderId",
                "showName": "订单 ID",
                "paramType": "string",
                "dataType": "attribute",
                "required": true
              }
            ]
          },
          {
            "name": "Header",
            "primaryKey": "Header",
            "tableId": "header-1",
            "tableData": []
          },
          {
            "name": "Body",
            "primaryKey": "Body",
            "tableId": "body-1",
            "tableData": []
          }
        ]
      },
      "authAppIds": [
        { "id": "app-1", "content": "普通应用-wull" }
      ]
    }
  }
}
```

`request` 应按设计器节点数据传入 `id`、可选 `mappingId` 和 `tables`。`tables` 的 `name` 只能是 `Params`、`Header`、`Body`；`primaryKey`、`tableId`、`customData` 等已有平台字段会原样保留，至少一个分组的 `tableData` 需要有字段，字段对象应来自前端参数设置组件。

生成时推荐直接传设计器返回的完整 `requestUrl`。如果只有 `requestCode`，编译器也会生成 `/api/open-esb/server/webhook/trigger/<requestCode>` 形式的公开地址；Java 组件保存时使用最后一段作为 code。

## 触发上下文

Webhook 请求运行时由平台解析为三个上下文分组：`Params`、`Header`、`Body`。动作参数中的上下文引用使用完整路径，例如 `Params.orderId`、`Header.Authorization`、`Body.customer.name`；不要把它们写成 `FormData.*`。

`authAppIds` 是 WebHook 触发器的必填认证应用列表，元素必须是 `{ "id": <应用ID>, "content": "<应用名称>" }`。生成前 CLI 会使用当前会话调用 `openApplicationBrowser` 并自动回填；默认使用接口返回的全部应用。如需限定范围，可在语义计划中传 `authAppNames: ["普通应用-wull"]`，CLI 会将筛选结果写入 `authAppIds`。没有认证应用时，CLI 不应生成 WebHook 触发器。

## 终止节点响应

Webhook 触发的终止节点使用 `finalOutput.params.webhookCustomParamSetting`，对应前端 `ParamGroupMappingBean`。必须包含 `Header`、`Body`、`StatusCode` 三个分组，并至少配置一个 Header 或 Body 字段；平台原生的 `id`、`mappingId`、`primaryKey`、`mappingTableId`、`customData` 和 `tableData` 直接保留。

```json
{
  "finalOutput": {
    "params": {
      "webhookCustomParamSetting": {
        "id": "response-setting-1",
        "mappingId": "response-mapping-1",
        "tables": [
          { "name": "Header", "tableData": [] },
          { "name": "StatusCode", "tableData": [] },
          {
            "name": "Body",
            "customData": "{\"dataType\":\"application/json\"}",
            "tableData": [
              { "id": "response-a", "paramKey": "ab", "paramName": "ab", "paramType": "string", "required": true }
            ]
          }
        ]
      }
    }
  }
}
```
