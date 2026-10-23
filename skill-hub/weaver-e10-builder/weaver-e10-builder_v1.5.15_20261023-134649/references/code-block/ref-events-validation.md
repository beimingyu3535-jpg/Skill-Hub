# 事件、校验与联动

## 动作前拦截与动作后钩子

`registerCheckEvent(action, (successFn, failFn, data) => {...})` 在动作前执行。校验通过调用 `successFn()`；不通过调用 `failFn({msg:'原因'})` 由系统提示，或自行提示后调用 `failFn()`。异步逻辑必须在所有路径调用其中之一；超过约 25 秒未回调会超时。可多次注册，按注册顺序执行。`window.WeFormSDK` 提供动作常量：`OPER_SAVE`、`OPER_ADDROW`、`OPER_DELROW`、`OPER_BEFOREVERIFY`、`OPER_EDITDETAILROW`、`OPER_FD_LINKAGE`（240601 起）。针对某明细表的添加/删除动作在常量后拼接明细表标识。

```js
formSdk.registerCheckEvent(window.WeFormSDK.OPER_SAVE, (ok, stop) => {
  const v = Number(formSdk.getFieldValue(amount) || 0);
  if (v > 0) ok();
  else stop({msg: '金额必须大于 0'});
});
```

`OPER_SAVE` 是表单数据保存动作，不等于工作流程节点的提交按钮校验。若需求是流程提交拦截，应选择流程相应能力及入口，不应把本例当作已覆盖。

`OPER_EDITDETAILROW` 是移动端编辑明细的拦截事件。`OPER_FD_LINKAGE` 拦截字段联动执行，回调 `data` 可含 `actionType/triggerFields/triggerRowIds`；过滤指定触发字段后调用 `successFn` 或 `failFn`，字段 ID 要与真实返回类型一致。`OPER_BEFOREVERIFY` 在必填校验前触发。

`registerAction(action, callback)` 是动作完成后的通知，可注册多个回调，按注册顺序执行。常量包括 `ACTION_ADDROW`、`ACTION_DELROW`（后拼明细标识）、`ACTION_FORM_SAVE`、`ACTION_DATA_LINKAGE`、`ACTION_DATA_RELATE`、`ACTION_VIEW_LINKAGE`。新增/删除明细行后的回调接收行下标集合和 `data`，下标从 0 开始，不可直接当 `rowId`；需要行身份时再查询。明细导入也可能触发添加行事件，`data.type` 可帮助区分。`ACTION_DATA_LINKAGE` 表示顶部字段联动/函数公式执行后，`data.runData` 可含 `actionType/resultFields/triggerFields/triggerRowIds`（240601 起）；`ACTION_DATA_RELATE` 表示关联字段钻取、字段右侧函数或运算控件后，回调可含 `fieldIds/rowIds/tableId`。

## 字段变化与交互

| API | 触发与用途 |
|---|---|
| `bindFieldChangeEvent('字段标识,字段标识', callback, options?)` | 主表或明细字段值变化；`data` 中可取 `rowId` |
| `bindDetailFieldChangeEvent('明细字段标识', callback)` | 专门处理明细字段值变化 |
| `bindFieldAttrChangeEvent('字段标识', callback)` | 字段读写属性变化 |
| `bindFieldAction(type, '字段标识', callback)` | 字段区域交互；`onblur/onfocus/onclick/ondbclick/mouseover/mouseout` |

字段事件可指定 `scope` 区分用户修改与联动带出，常量为 `window.WeFormSDK.CHANGE_EVENT_SCOPE`（主表事件至少 250401；明细专用事件至少 250901）及 `window.WeFormSDK.CHANGE_EVENT_LINKAGE`。回调 `data` 可含 `id/value/rowId`；值变化不包括明细增删行，因此仍须注册行事件。联动修改不一定自动触发 JS 值变化事件，必要时通过赋值配置的 `jsApiChange` 或 `triggerFieldAllLinkage` 明确触发。251101 起可设置全局 `window.__FORM_JS_LINKAGE_EVENT_CHANGE__ = true` 扩展联动事件触发范围，可能使既有监听再次运行；只在确有需要时使用。

```js
formSdk.bindFieldChangeEvent(detailAmount, ({rowId}) => {
  if (!rowId) return;
  const value = Number(formSdk.getFieldValue(`${detailAmount}_${rowId}`) || 0);
  formSdk.changeFieldValue(`${detailTax}_${rowId}`, {value: String(value * 0.13)});
});
formSdk.registerAction(`${window.WeFormSDK.ACTION_ADDROW}${table}`, () => recalculate());
formSdk.registerAction(`${window.WeFormSDK.ACTION_DELROW}${table}`, () => recalculate());
```

编写校验时先定触发动作、允许/阻断条件、提示内容及异步失败路径；编写联动时同时覆盖载入、字段变化、明细增删，并防止监听目标再触发自身。保存后分别验证通过与不通过两条路径。
