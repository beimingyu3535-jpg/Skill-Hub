# 明细表与嵌套明细 JSSDK

先用 `convertFieldNameToId(明细表数据Key,'main')` 取明细标识，再以其为位置取得明细字段标识。`rowId` 是一行的运行时身份，不等于序号，也不是普通业务字段。`getDetailData(table)` 返回的每行含 `rowId` 以及以字段标识为键的 `{value}` 或 `{specialObj}` 对象；复制到另一明细表时去掉原 `rowId`，否则可能写错行。

## 行与数据操作

| 目标 | API、关键参数 |
|---|---|
| 添加一行 | `addDetailRow(table, {[field]:{value:'文本'}, [browser]:{specialObj:[{id,name}]}})` |
| 批量添加 | `addDetailData(table, [{[field]:{value:'A'}}, ...], config?)` |
| 删除指定行/全部行 | `delDetailRow(table, rowId)` / `delDetailRow(table, 'all')` |
| 更新多行 | `changeDetailData(table, [{rowId, [field]: {value:'新值'}}, ...], config?)`；250101 起，无 rowId 的项会新增行 |
| 取全部行数据/某行 | `getDetailData(table, options?)` / `getDetailRowData(table, rowId)`；均至少 240601 基线 |
| 取行 ID 串/行数 | `getDetailAllRowIndexStr(table)` 返回逗号分隔的 rowId；`getDetailRowCount(table)` 返回行数（原资料类型声明写 string、示例结果写 number，使用时以实际返回为准） |
| 序号转行 ID/反向 | `getDetailRowIdByIndex(table, index)` / `getDetailIndexByRowId(table, rowId)`；index 从 1 起 |
| 按行 ID 取显示序号 | `getDetailRowSerailNum(table, rowId)`（接口拼写为 Serail） |
| 取明细字段 ID | `getDetailFieldIds(table, prefix?)`；240701 起，`prefix` 默认 `false`（不带 `field` 前缀），需要前缀时传 `true`；原示例以逗号分隔结果使用 |

```js
const rows = formSdk.getDetailData(table) || [];
const total = rows.reduce((n, row) => n + Number(row[detailAmount]?.value || 0), 0);
formSdk.changeFieldValue(mainTotal, {value: String(total)});
```

上述汇总应在页面载入、金额变化、添加行、删除行后分别触发。金额换算用 `Number` 与明确的空值处理，不用拼接表达式再 `eval`。百分比要处理总额为 0 的情况。

## 行显示、选择与菜单

| 目标 | API |
|---|---|
| 获取勾选行 | `getDetailCheckedRowIndexStr(table)`；返回行 ID 串 |
| 勾选指定行/全部 | `checkDetailRow(table, 逗号分隔的rowId或'all', needClearBeforeChecked?)`；`checkDetailRow(table, '', true)` 清空已选 |
| 禁止勾选 | `controlDetailRowDisableCheck(table, rowId或'all', true)`；`false` 恢复 |
| 隐藏/显示行 | `controlDetailRowDisplay(table, 逗号分隔的rowId或'all', needHide)`；`true` 隐藏、`false` 显示 |
| 排序显示行 | `setDetailSortRows(table, 逗号分隔的rowId, 'before'或'after')` |
| 新增时复制末行 | `setDetailAddUseCopy(table, true/false)` |
| 新增时默认使用末行数据 | `setDetailAddDefLast(table, true/false)`；至少 240701 基线，原文示例误写成 `setDetailAddUseCopy`，须区分两种设置的实际效果 |
| 顶部自定义操作 | `setDetailTopAction(table, actions)`；每项有 `id/type/title/mode` 等，按目标组件允许的动作填写 |
| 当前明细筛选条件 | `getDetailSearchCfg(table)`；可用于 `getDetailData(table,{searchValue: cfg})` |

`addDetailData` 至少 241201 基线，传入数组每项以字段标识为键、值为 `{value}` 或 `{specialObj}`；第三参数可控制 `dataLinkage/viewLinkage/optionLinkage/jsApiChange`。`changeDetailData` 至少 250101 基线，结构相同但更新项需附 `rowId`；若传入项的 `rowId` 不存在，原资料说明会生成新行，配置时不要误用。动态行使用 `registerAction(ACTION_ADDROW + table, ...)` 与删除事件更新汇总或渲染；回调首参数是从 0 开始的行下标集合，不是 rowId。原资料同时列出 `setDetailAddDefLast` 与 `setDetailAddUseCopy`，但前者的示例错误调用了后者；保留两者各自契约，目标版本行为以实测为准。

顶部操作示例：`setDetailTopAction(table,[{id:'refresh',type:'refresh',title:'刷新',mode:'text'}])`；自定义渲染项可用 `{id:'custom',type:'custom',customRender:()=>React.createElement('div',{},'操作')}`，需保证当前代码入口有 React。`setDetailSortRows(table,'rowId1,rowId2','before'|'after')` 至少 241101 基线，默认 `before`。260401 及以后，`getDetailData(table,{searchValue:formSdk.getDetailSearchCfg(table)})` 可按当前明细筛选条件取行；不传第二参数则读取整表行。

## 父子明细

给某父行增加子行时，先确保父行已存在，再把子级行标识字段写为该父行的标识值；它是父子关系字段，不是新子行的 `rowId`。通常流程：取父 `rowId` → 读取父级行标识字段的值 → `addDetailRow(childTable,{[childRelationField]:{value: parentKey}, ...})`。按父行汇总时，筛选子表关系字段等于当前父行标识的行，再汇总回该父行字段。

```js
const parentKey = formSdk.getFieldValue(`${parentRelation}_${parentRowId}`);
formSdk.addDetailRow(childTable, {
  [childRelation]: {value: parentKey},
  [childAmount]: {value: '0'}
});
```

不要把父表行 ID 直接当作子表行 ID。父子关系字段的实际值若为选项对象，先用 `getFieldObj` 检查结构，再按同类结构赋值。
