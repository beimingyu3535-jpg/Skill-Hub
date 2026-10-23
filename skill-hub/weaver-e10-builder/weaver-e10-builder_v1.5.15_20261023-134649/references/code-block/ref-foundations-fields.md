# JSSDK 基础、字段定位与赋值

## 实例与时机

- 布局源码和表单级 ecode（250101 及以后基线）使用当前作用域的 `formSdk`。旧方式 `window.WeFormSDK.getWeFormInstance()` 可能在多表单页面取错实例。
- 早期基线可通过 `pageSdk.on('formReady', callback)` 等待表单加载，再调用 `window.WeFormSDK.getWeFormInstance(moduleKey?, formId?, dataId?)`；条件允许时传入更细的模块、表单、数据 ID，避免页面同时打开多份表单时取错。全局 ecode 用 `window.addEventListener('onFormReady', e => { const {formSdk, formId, module}=e.detail; ... })`，按 `formId/module` 限定作用范围；这个全局事件每打开一份表单都会触发，不放在单布局源码中重复监听。
- 字段和明细行尚未渲染时不要操作其组件。注册事件通常在表单 ready 后进行，动态新增明细行须在添加行事件后处理。

## 字段标识与读取

`formSdk.convertFieldNameToId(dataKey, location?, prefix?)` 将数据 Key 转为字段标识，`prefix` 默认 `true`，即返回带 `field` 前缀的标识；传 `false` 时返回纯数字 ID。主表用 `location='main'`；明细字段用明细表标识作为 location。260601 及以后也可用明细表数据 Key 作 location。字段数据 Key 在字段管理“数据 Key”列或设计器选中字段后的右侧查看；明细表 Key 在设计器选中明细表后查看，高级版可能要双击明细表。明细某行标识为 `${detailField}_${rowId}`，`rowId` 是运行时行 ID，不是显示序号。

```js
const amount = formSdk.convertFieldNameToId('amount', 'main');
const table = formSdk.convertFieldNameToId('payment_detail', 'main');
const rate = formSdk.convertFieldNameToId('rate', table);
const firstRowId = formSdk.getDetailRowIdByIndex(table, 1);
const value = firstRowId ? formSdk.getFieldValue(`${rate}_${firstRowId}`) : undefined;
```

| 读取 API | 用途 |
|---|---|
| `getFieldValue(fieldMark)` | 取单个字段简化值；文本返回内容，选项/浏览一般返回 ID，取显示名用控件专题方法 |
| `getFieldObj(fieldMark)` | 取原始数据对象，可含 `value/specialObj/longitude/latitude/type/contentObj`；不确定控件结构时先看它；240701 起 |
| `getFieldInfo(fieldMark)` | 字段元数据，可含 `fieldId/dataKey/name/componentKey/isSingle`；实际对象还可能有其他属性 |
| `listFieldInfo()` | 当前表单所有字段信息，含 `readOnly/required` 等 |
| `getFieldAttr(fieldMark)` | 当前读写属性，返回 1～5 的属性码 |
| `getFieldCom(fieldMark)` | 字段组件信息，含 `id/type/config`；240701 起。原文示例误调用 `getFieldInfo` |

## 赋值结构

`changeFieldValue(fieldMark, valueInfo, config?)` 修改字段值。普通文本、数字、日期传 `{value: '...'}`；浏览和动态选项传 `{specialObj:[{id,name,data?}]}`，清空浏览传 `{specialObj:[]}`。固定选项可传 `{value: optionId}`；选项模板使用 `specialObj`。日期区间的值可为 `开始日期,结束日期`。人员范围对象可带 `type`，如 `user/dept/subcompany/organization/group/role/position/all`。附件除 id/name 外还需要来自附件模块的完整 `data` 对象，不能凭文件名伪造可预览附件。地理位置可附 `latitude/longitude`；某些特殊字段还用 `type/contentObj`。

```js
formSdk.changeFieldValue(amount, {value: '120.00'});
formSdk.changeFieldValue(customer, {specialObj: [{id: customerId, name: customerName}]});
formSdk.changeFieldValue(customer, {specialObj: []});
formSdk.changeFieldValue(`${rate}_${firstRowId}`, {value: '0.13'});
```

第三参数可控制随赋值触发的处理：`dataLinkage`（字段联动、公式、钻取）、`viewLinkage`（显示联动）、`optionLinkage`、`dataValidate`、`jsApiChange`；对应值 `false` 表示不执行，默认按系统行为。该参数在 241001 及以后基线适用。需要在赋值后明确再次运行联动时，用 `triggerFieldAllLinkage(fieldMark)`，它会触发字段联动、函数公式、显示属性联动、数据钻取、选项联动等；明细字段须指定某行。250901 及以后可等待其 Promise。避免监听 A 又写 A 形成循环。

## 显示属性与批量修改

`changeFieldAttr(fieldMark, viewAttr)` 的属性码：`1` 只读、`2` 可编辑、`3` 必填、`4` 隐藏、`5` 隐藏行。明细字段标识作用于整列，`${field}_${rowId}` 作用于指定行。流程节点或权限锁定的只读状态，不能依靠此 API 强行变为可编辑。EXCEL 布局隐藏明细列时还要留意冻结标题/列。

`changeSingleField(fieldMark, valueInfo, {viewAttr})` 同时改值和属性。`changeMoreField(changeDatas, changeVariable?)` 批量修改，两参数都是以字段标识为键的对象：

```js
formSdk.changeMoreField(
  {[amount]: {value: '120.00'}, [customer]: {specialObj: [{id: customerId, name: customerName}]}},
  {[amount]: {viewAttr: 1}}
);
```

运行前检查标识非空、字段在当前布局可用、数据 Key 所在主/明细位置正确。读取 `getFieldObj` 对照实际值结构，再决定使用 `value` 还是 `specialObj`。
