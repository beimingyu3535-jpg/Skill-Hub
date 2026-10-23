# 终止（`Output`）

## 何时使用

结束主链；由编译器自动补充。需要配置成功/失败状态、结束提示或页面动作时，通过计划顶层 `finalOutput.params` 配置。

## 先查询

无需查询。

## 不可猜测

不要把 `Output` 写入 `actions`。`reminderMsgFormula` 与 `basisValue` 支持固定值、上下文、系统变量、变量、常量、查询结果和函数/公式；`jumpUrl` 在前端只允许固定文本。`fixedData`、`customOutputData` 属于平台原生高级输出结构，必须使用真实回读结构，不能猜测。

如果自定义触发动作流需要配置终止参数，在 `finalOutput.params.customParamSetting` 中使用同一套 `CustSetFormDto` 结构，`formType` 改为 `output`，新建时 `customId` 传空字符串，`deleteTableIds` 传空数组，`appId` 由编译器注入当前动作流应用 ID，关联 ID 由后端保存方法生成。

## 最小计划

```json
{
  "finalOutput": {
    "params": {
      "outputStatus": "0",
      "reminder": "1",
      "reminderMsgFormula": { "kind": "variable", "id": "<真实变量ID>", "name": "失败提示" },
      "pageAction": "0"
    }
  }
}
```
