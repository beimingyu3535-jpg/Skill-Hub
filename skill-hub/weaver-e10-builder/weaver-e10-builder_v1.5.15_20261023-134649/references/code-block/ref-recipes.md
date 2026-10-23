# 按效果查代码模式

本页覆盖原案例中的独立做法。字段 Key、接口和字段对象均需替换为目标表单真实数据；示例中出现的模拟接口、固定附件对象和测试 ID 不能作为正式值。

| 想要的效果 | 组合方法 | 关键检查 |
|---|---|---|
| 保存前汇总明细人员到主表并去重 | `registerCheckEvent(OPER_SAVE)` → `getDetailAllRowIndexStr` → 逐行 `getBrowserOptionEntity` → 按 id 去重 → `changeFieldValue(...,{specialObj})` → `successFn` | 空行、重复人员、失败回调；仅拦表单保存 |
| 附件字段回填且可预览 | 从附件模块/现有字段取完整对象 → `changeFieldValue(...,{specialObj:[{id,name,data,type:'file'}]})` | 文件权限、预览/下载入口；不可只传 id/name |
| 多级选项等复杂值赋值 | 先 `getFieldObj` 观察已有对象 → 按 `data.content` 或 `data.dataOptions` 等原结构写 `specialObj` | 选项模板、次级选项正确显示 |
| 将明细富文本显示为按钮或链接 | `getDetailAllRowIndexStr` 遍历每行 → `proxyFieldComp` 替换该行内容；添加行事件补新行 | 点击跳转地址与作用范围 |
| 按两个维度分类、累加到另一明细表 | `getDetailData` 建组合 Key → 对目标行更新/新增/删除 → 监听来源值变化和增删行 | 组合 Key 唯一、消失分组删除、重复事件 |
| 全表单跨模块识别字段并回填外部数据 | 全局 ecode `onFormReady` 取当前实例并限制 module/formId → 字段事件 → 调受支持接口 → `changeMoreField` | 权限、数据范围、主表/明细位置、失败与清空逻辑 |
| 明细数字合计并算各行占比 | 读取明细每行数值 → `reduce` 求和 → 主表回写 → 逐行占比赋值；监听值变化及增删行 | 空值、非数字、总额 0、精度 |
| 联动带出后再汇总并触发后续联动 | 对带出字段监听联动 scope → 汇总 → 写主表 → 必要时 `triggerFieldAllLinkage` | 避免循环；确认事件是否实际触发 |
| 合并多个主表浏览/选项字段 | 多字段 `getBrowserOptionEntity` → 合并或按 id 去重 → 主表 `specialObj` 赋值 | 是否保留重复项、空字段 |
| 按同行条件选择明细人员合并到主表 | `getDetailData` → 判断同行选项值 → 取人员对象 → 去重 → `changeFieldValue` | 条件变化、增删行后重算 |
| 子明细按父行汇总金额 | 父、子关系字段匹配 → 筛子表数据 → 合计 → 回写父表指定 `rowId` | 父标识唯一、子行归属、父行删除后的处理 |
| 按显示序号生成明细值 | 明细行数组按显示顺序 `map((row,index)=>...)` → `changeDetailData`；监听增删行 | 排序后重新计算，避免把序号当 rowId |
| 某字段为空时触发另一字段联动 | `getFieldValue` 判空 → `triggerFieldAllLinkage(target)`；载入与源字段变化均执行 | 空字符串、0 与未选择的判定 |
| 自定义页面参数传递/组件换肤 | 全局 ecode `regOvProps` 或表单字段 `proxyFieldContentComp`，按生效范围选择 | 组件名/props 契约、编译入口 |

上述模式涉及的完整 API、参数与风险分别见 [事件](ref-events-validation.md)、[字段](ref-foundations-fields.md)、[明细](ref-details.md)、[控件](ref-controls.md) 和 [组件交互](ref-ui-global.md)。原案例存在重复与少量不完整代码：例如重复的“保存前汇总人员”，附件数据依赖文档模块，组件 props 示例有语法笔误，数字合计示例用 `eval`，全局回填示例包含模拟数据。这里保留其实现思路，代码应按专题中可运行的结构重新组装。

## 保存前汇总明细人员并去重

先定位明细、明细人员字段和主表目标字段；仅在表单数据保存前执行。需要流程“提交”时改用流程 SDK 的节点提交事件。

```js
const table = formSdk.convertFieldNameToId('people_detail', 'main');
const detailPerson = formSdk.convertFieldNameToId('person', table);
const mainPeople = formSdk.convertFieldNameToId('all_people', 'main');
formSdk.registerCheckEvent(window.WeFormSDK.OPER_SAVE, (ok, stop) => {
  try {
    const rowIds = (formSdk.getDetailAllRowIndexStr(table) || '').split(',').filter(Boolean);
    const unique = new Map();
    for (const rowId of rowIds) {
      for (const item of formSdk.getBrowserOptionEntity(`${detailPerson}_${rowId}`) || []) {
        if (item?.id) unique.set(String(item.id), item);
      }
    }
    formSdk.changeFieldValue(mainPeople, {specialObj: [...unique.values()]});
    ok();
  } catch (error) {
    stop({msg: '人员汇总失败，请检查明细数据'});
  }
});
```

## 明细数值汇总并计算占比

值变化、增行、删行和初次载入都要重新计算；`getDetailData` 的每行包含 `rowId`。示例以数值 0 处理空值，业务若要求空值报错，应另作校验。

```js
const table = formSdk.convertFieldNameToId('cost_detail', 'main');
const detailAmount = formSdk.convertFieldNameToId('amount', table);
const detailShare = formSdk.convertFieldNameToId('share', table);
const mainTotal = formSdk.convertFieldNameToId('total', 'main');
function recalculate() {
  const rows = formSdk.getDetailData(table) || [];
  const total = rows.reduce((sum, row) => sum + Number(row[detailAmount]?.value || 0), 0);
  formSdk.changeFieldValue(mainTotal, {value: String(total)}, {jsApiChange: false});
  for (const row of rows) {
    const amount = Number(row[detailAmount]?.value || 0);
    formSdk.changeFieldValue(`${detailShare}_${row.rowId}`, {value: String(total ? amount / total : 0)}, {jsApiChange: false});
  }
}
formSdk.bindFieldChangeEvent(detailAmount, recalculate);
formSdk.registerAction(`${window.WeFormSDK.ACTION_ADDROW}${table}`, recalculate);
formSdk.registerAction(`${window.WeFormSDK.ACTION_DELROW}${table}`, recalculate);
recalculate();
```

如汇总源值本身来自字段联动，普通字段变化事件可能不触发；依目标基线使用 `scope: window.WeFormSDK.CHANGE_EVENT_LINKAGE` 或监听 `ACTION_DATA_LINKAGE`。占比输出为 0～1 还是 0～100，须按目标字段的百分比显示方式确定。不要直接打开全局联动事件开关而不检查既有监听是否形成循环。

## 父子明细按关系字段回写

父、子明细的关系字段值相同才能归属同一父行。先配置真实二级明细关系，再对每个父行筛选对应子行。这里的业务主键与 `rowId` 分开。

```js
const parentTable = formSdk.convertFieldNameToId('parent_detail', 'main');
const childTable = formSdk.convertFieldNameToId('child_detail', 'main');
const parentKey = formSdk.convertFieldNameToId('parent_key', parentTable);
const parentTotal = formSdk.convertFieldNameToId('parent_total', parentTable);
const childKey = formSdk.convertFieldNameToId('child_parent_key', childTable);
const childAmount = formSdk.convertFieldNameToId('child_amount', childTable);
function recalculateParents() {
  const children = formSdk.getDetailData(childTable) || [];
  for (const parent of formSdk.getDetailData(parentTable) || []) {
    const key = parent[parentKey]?.value;
    const total = children.filter(row => row[childKey]?.value === key)
      .reduce((sum, row) => sum + Number(row[childAmount]?.value || 0), 0);
    formSdk.changeFieldValue(`${parentTotal}_${parent.rowId}`, {value: String(total)}, {jsApiChange: false});
  }
}
formSdk.bindFieldChangeEvent(childAmount, recalculateParents);
formSdk.registerAction(`${window.WeFormSDK.ACTION_ADDROW}${childTable}`, recalculateParents);
formSdk.registerAction(`${window.WeFormSDK.ACTION_DELROW}${childTable}`, recalculateParents);
recalculateParents();
```

关系字段若为选项而非文本，按 `getFieldObj` 的 `specialObj` 比较 ID。父行标识必须唯一；删除父行后的子行处置应由业务规则明确。用 `getDetailData` 复制子行时不要复制旧 `rowId`。

## 来源明细按两列分组，同步到目标明细

来源中按“部门 ID + 类型 ID”分组求和；目标中已有分组更新、缺失分组新增、来源已消失的分组删除。监听来源的两列条件字段、数值字段与增删行事件。下面只展示同步函数，绑定方式同上方汇总案例。

```js
function syncGroups(sourceTable, targetTable, sourceDept, sourceType, sourceAmount,
                    targetDept, targetType, targetAmount) {
  const groups = new Map();
  for (const row of formSdk.getDetailData(sourceTable) || []) {
    const dept = row[sourceDept]?.specialObj?.[0];
    const type = row[sourceType]?.specialObj?.[0];
    if (!dept?.id || !type?.id) continue;
    const key = `${dept.id}:${type.id}`;
    const item = groups.get(key) || {dept, type, total: 0};
    item.total += Number(row[sourceAmount]?.value || 0);
    groups.set(key, item);
  }
  const existing = new Map();
  for (const row of formSdk.getDetailData(targetTable) || []) {
    const deptId = row[targetDept]?.specialObj?.[0]?.id;
    const typeId = row[targetType]?.specialObj?.[0]?.id;
    if (!deptId || !typeId || !groups.has(`${deptId}:${typeId}`)) {
      formSdk.delDetailRow(targetTable, row.rowId);
    } else {
      existing.set(`${deptId}:${typeId}`, row.rowId);
    }
  }
  for (const [key, item] of groups) {
    const rowId = existing.get(key);
    if (rowId) {
      formSdk.changeFieldValue(`${targetAmount}_${rowId}`, {value: String(item.total)}, {jsApiChange: false});
    } else {
      formSdk.addDetailRow(targetTable, {
        [targetDept]: {specialObj: [item.dept]},
        [targetType]: {specialObj: [item.type]},
        [targetAmount]: {value: String(item.total)}
      });
    }
  }
}
```

这种同步会删除目标中无来源的行，只有目标表完全由来源派生时才适用；若允许用户手工维护目标行，应改为保留手工行并有明确的来源标识。跨字段 `id` 类型与数值精度须按实际表单处理。

## 根据明细同行条件筛人员，合并到主表

对每行读取条件选项，按不同条件分别取对应人员字段，再按人员 ID 去重并写入主表。初次载入、条件/人员字段变化、明细增删行均重新执行。

```js
function syncPeople(table, conditionField, firstPeopleField, secondPeopleField, mainPeopleField) {
  const people = new Map();
  for (const row of formSdk.getDetailData(table) || []) {
    const choice = row[conditionField]?.specialObj?.[0]?.id;
    const selected = choice === '0' ? row[firstPeopleField]?.specialObj :
      choice === '1' ? row[secondPeopleField]?.specialObj : [];
    for (const person of selected || []) if (person?.id) people.set(String(person.id), person);
  }
  formSdk.changeFieldValue(mainPeopleField, {specialObj: [...people.values()]}, {jsApiChange: false});
}
```

条件选项 ID `'0'/'1'` 是示例占位，须读取真实选项 ID。若人员字段由系统联动带出，还要按[事件指南](ref-events-validation.md)监听联动完成事件。
