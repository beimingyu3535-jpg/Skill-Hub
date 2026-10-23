# 表单代码块配置指南

本指南用于把表单引擎 JSSDK 作为一项可规划、可实施的表单功能配置。适用于 EB 表单和原生工作流程表单的布局源码；表单级 ecode、流程级或应用级 ecode 须按实际入口和生效范围另行选择。先确定代码放置层级、布局与终端，再按专题读取写法。各专题包含必要参数和可改用的代码，不依赖原始技术文档。

## 适用场景

平台内置的字段联动、公式、查重、校验、视图和流程配置能表达需求时，优先用平台配置；以下情况适合使用表单代码块：

- 内置配置无法表达的条件组合、跨字段计算、动态属性或状态流转；
- 需要在用户输入、明细增删、保存等动作前后实时响应、校验、提示或阻断；
- 需要对明细行做即时汇总、占比、分组、父子归属或按条件筛选；
- 需要控制选项、日期范围、浏览参数、页签等控件行为；
- 需要复写字段组件渲染、追加字段内容或处理字段区域事件；
- 需要在表单载入时做初始化、补全、规范化或默认值处理。

## 代码放在哪一层

| 需求范围 | 入口 | 特点 |
|---|---|---|
| 只对某个布局、某个终端生效 | 布局源码：`form code layout set` / `wf-form code layout set` | 随布局和终端加载；CSS 自动限定在 `#ebpage_<pageId>`；JS 带 `pageId` 生效条件 |
| 同一表单的所有布局/终端都要生效 | 表单级 ecode：`form code ecode ...` | 不随布局切换；需要自己判断当前表单/数据上下文 |
| 应用级或全局页面逻辑 | 全局 ecode / 页面入口 | 不在本指南的表单布局命令范围内；使用 `onFormReady` 等全局事件并按 formId/module 限定 |

选择原则：能用布局源码完成的不要放大到表单级，能用表单级完成的不要放大到全局。

## 能实现什么

| 场景 | 可形成的效果 | 关键 API（示例） | 专题 |
|---|---|---|---|
| 加载初始化 | 默认值、状态初始化、数据补全/规范化 | 直接执行 + `getFieldValue` / `changeFieldValue` | [基础与字段](ref-foundations-fields.md) |
| 字段联动 | A 变化写 B；跨字段计算；空值/清空；防循环 | `bindFieldChangeEvent`、`getFieldValue`、`changeFieldValue`、`triggerFieldAllLinkage` | [基础与字段](ref-foundations-fields.md)、[事件与校验](ref-events-validation.md) |
| 动态属性 | 按状态/角色/条件切换只读、可编辑、必填、隐藏、隐藏行 | `changeFieldAttr`、`changeSingleField`、`changeMoreField` | [基础与字段](ref-foundations-fields.md) |
| 保存前校验 | 阻断保存并提示；通过/失败回调；异步校验 | `registerCheckEvent(OPER_SAVE)`、`stop({msg})` | [事件与校验](ref-events-validation.md) |
| 明细计算 | 金额合计、占比、分组汇总、父子明细回写 | `getDetailData`、`getDetailAllRowIndexStr`、`addDetailRow` / `delDetailRow` | [明细操作](ref-details.md) |
| 明细事件 | 增行/删行/改值后重算；行显示、勾选、排序 | `ACTION_ADDROW` / `ACTION_DELROW`、`controlDetailRowDisplay`、`checkDetailRow` | [明细操作](ref-details.md) |
| 控件行为 | 日期范围、选项过滤/禁用、浏览参数、页签切换 | `controlDateRange`、`controlSelectOption`、`controlOptionDisable`、`appendBrowserDataUrlParam`、`switchTabItem` | [特定控件](ref-controls.md) |
| 交互反馈 | 消息、确认框、加载、必填检查、刷新、关闭提示 | `window.WeFormSDK.showMessage/showConfirm/getLoadingGlobal`、`verifyFormRequired`、`reloadPage` | [组件与全局操作](ref-ui-global.md) |
| 字段组件复写 | 替换/追加字段内容、局部渲染、字段区域事件 | `proxyFieldComp`、`afterFieldComp`、`proxyFieldContentComp`、`bindFieldAction` | [组件与全局操作](ref-ui-global.md) |
| 扩展通信 | 插件接口、父子页面 `postMessage`、跨组件协作 | `pluginGet` / `pluginExecute`、`window.opener`、`postMessage` | [组件与全局操作](ref-ui-global.md) |
| 现成业务模式 | 明细人员汇总去重、按条件合并、分组同步、占比 | 见案例组合 | [效果案例](ref-recipes.md) |

## 边界与不适用场景

- 代码块不是后端逻辑：不能绕过字段/数据权限、流程节点只读或接口鉴权，也不能替代服务端校验。
- `OPER_SAVE` 拦截的是**表单数据保存**，不是工作流节点提交；流程提交拦截应使用流程相应入口。
- 布局源码只作用于当前布局和终端；跨布局、跨终端的逻辑用表单级 ecode，并明确作用范围。
- 字段、表单、流程、视图、权限等资源本身用对应 CLI/设计器配置，不要用代码块临时改结构。
- 附件、人员、浏览对象必须来自平台真实对象/接口；不能只拼 `id/name` 伪造可预览附件或可选项。
- 布局源码只使用编辑器可编译的语法和平台暴露的 API；不要直接套用独立 `.ecode` 项目的 `import`、JSX 或 npm 依赖。

## 最小示例

字段联动 + 动态只读 + 保存前校验：

```js
const status = formSdk.convertFieldNameToId('status', 'main');
const amount = formSdk.convertFieldNameToId('amount', 'main');

function applyStatus() {
  const submitted = String(formSdk.getFieldValue(status) || '').trim() === '已提交';
  formSdk.changeFieldAttr(amount, submitted ? 1 : 2);
}
applyStatus();
formSdk.bindFieldChangeEvent(status, applyStatus);

formSdk.registerCheckEvent(window.WeFormSDK.OPER_SAVE, (ok, stop) => {
  const value = Number(formSdk.getFieldValue(amount) || 0);
  if (value > 0) ok();
  else stop({ msg: '金额必须大于 0' });
});
```

明细金额合计：

```js
const table = formSdk.convertFieldNameToId('cost_detail', 'main');
const detailAmount = formSdk.convertFieldNameToId('amount', table);
const total = formSdk.convertFieldNameToId('total', 'main');

function recalculate() {
  const rows = formSdk.getDetailData(table) || [];
  const sum = rows.reduce((n, row) => n + Number(row[detailAmount]?.value || 0), 0);
  formSdk.changeFieldValue(total, { value: String(sum) }, { jsApiChange: false });
}

formSdk.bindFieldChangeEvent(detailAmount, recalculate);
formSdk.registerAction(window.WeFormSDK.ACTION_ADDROW + table, recalculate);
formSdk.registerAction(window.WeFormSDK.ACTION_DELROW + table, recalculate);
recalculate();
```

> 示例中的 `status` / `amount` / `cost_detail` 等是字段数据 Key 的占位，实施时必须换成目标表单真实 Key，并从已建资源读取。

## 按效果查专题

| 要实现的效果 | 必读文档 |
|---|---|
| 初始化、定位字段、值结构、环境基线 | [基础与字段](ref-foundations-fields.md) |
| 保存前校验、明细行拦截、字段变化与联动事件 | [事件与校验](ref-events-validation.md) |
| 明细行增删改查、批量处理、父子明细 | [明细操作](ref-details.md) |
| 浏览、选项、日期、附件、选项卡 | [特定控件](ref-controls.md) |
| 字段组件渲染、页面消息、弹窗、加载、插件、跨页面交互 | [组件与全局操作](ref-ui-global.md) |
| 从业务描述找现成实现模式 | [效果案例](ref-recipes.md) |
| 指定布局的页面、字段和明细表外观 | [表单布局 CSS 编写指南](guide-layout-css.md) |
| 代码不生效、版本与事件问题 | [排查与边界](ref-troubleshooting.md) |

## 配置顺序

1. 在 plan 中记录目标表单、布局、终端、代码层级、触发时机、涉及字段/明细数据 Key、期望效果及检查方式。布局源码只作用于当前布局及终端；跨布局或全表单逻辑选择表单级 ecode，并明确范围判断。
2. 从已建资源读取真实字段数据 Key、明细表 Key 和布局 ID。用 `convertFieldNameToId` 定位运行时字段；同名 Key 可能同时存在于主表和明细表，必须传位置。
3. 根据效果组合专题中的 API。代码应处理初始化、空值、明细增删、重复注册与事件循环；不要从旧案例直接复制固定 ID、测试 URL 或示例数据。
4. 在对应入口保存 JS/CSS 后读回，并以一个正常场景和一个边界场景验证运行结果。保存成功只能证明代码存储，不代表事件执行或业务效果正确。

## CLI 写入入口

先用下表中的 JSSDK 专题确定代码写法，再用对应命令写入。JS、CSS 分别读取文件；只提供其中一项时保留另一项。布局源码须指定实际布局 ID 与终端，表单级 ecode 使用独立配置，不随布局切换。

| 范围 | 读取 | 写入 |
|---|---|---|
| EB 表单布局 | `form code layout read <objId> --app-id <appId> --layout-id <id> --terminal PC|MOBILE` | `form code layout set <objId> --app-id <appId> --layout-id <id> --terminal PC|MOBILE --js <文件> [--css <文件>]` |
| 原生工作流程表单布局 | `wf-form code layout read <formId> --layout-id <id> --terminal PC|MOBILE` | `wf-form code layout set <formId> --layout-id <id> --terminal PC|MOBILE --js <文件> [--css <文件>]` |
| EB 表单级 ecode | `form code ecode list <objId> --app-id <appId>`；`form code ecode read <objId> <ecodeId> --app-id <appId>` | `form code ecode add <objId> --app-id <appId> --name <名称> --js <文件> [--css <文件>]`；`form code ecode edit <objId> <ecodeId> --app-id <appId> --js <文件>`；`form code ecode status <objId> <ecodeId> --app-id <appId> --state on|off` |
| 原生工作流程表单级 ecode | `wf-form code ecode list <formId>`；`wf-form code ecode read <formId> <ecodeId>` | `wf-form code ecode add <formId> --name <名称> --js <文件> [--css <文件>]`；`wf-form code ecode edit <formId> <ecodeId> --js <文件>`；`wf-form code ecode status <formId> <ecodeId> --state on|off` |

`set`/`add`/`edit` 保存后会读回确认；`edit` 可单独提供 `--js` 或 `--css`，保留另一部分。先用 `read` 核对已有代码和作用范围。

布局源码写入时，CLI 按当前终端页面的 `pageId` 生成 JS 生效条件，并把 CSS 选择器限定在当前 `#ebpage_<pageId>` 内。需要由 JS 动态插入且使用布局 CSS 的元素，应挂在该页面容器内；挂到 `document.body` 的元素不受这份布局 CSS 修饰。写入后用 `layout read` 核对 JS/CSS 原文、页面条件和编译结果，再打开实际表单页面检查运行效果。

布局 CSS 的可设置内容、表格式与流式布局的选择器边界及完整写入示例，见[表单布局 CSS 编写指南](guide-layout-css.md)。

布局源码的 JS 与 CSS 分别保存；重建布局时分别确认两者是否保留。表单级 ecode 是另一份配置，不会随布局源码同步。表单源码中的 `formSdk` 可直接使用；全局 ecode 监听 `onFormReady` 并从事件取得对应实例，避免多表单页面取错实例。涉及审批节点提交的校验，先区分表单数据保存与流程提交：`OPER_SAVE` 拦截的是前者。

本指南及其 JSSDK 专题负责代码的编写与效果判断；上述 CLI 命令负责定位资源、保存和读回。独立 `.ecode` 项目、流程级和应用级 ecode 不使用这些表单布局命令。

## 布局源码存储与编码（设计器同源）

- **不要手改 `sourceCode.ecode`。** CLI 负责编码；如果绕过 CLI 直接调接口，必须使用 `encodeURI(JSON.stringify({js, css}))`。
- 设计器读取路径是 `JSON.parse(decodeURI(ecode))`。`encodeURIComponent` 会把冒号编码成 `%3A`，而 `decodeURI` 不还原它，结果是 `{"js"%3A...}`，浏览器报 `ECode decode failed, SyntaxError: Expected ':' after property name in JSON`，源码面板为空、预览失效。`form code layout set` / `wf-form code layout set` 已内置写入前和回读后的同路径校验。
- 布局源码保存走 `saveFormAndLayout` 的 `pageLayoutEncodes` / `formStyleEncodes`（LZW 压缩），不要用裸 `pageLayouts` 写源码。`js` 需带 `content`、`compiledContent`、`pageId`（`if (<pageId> == String(props.pageId))`）、`name: "index"`、`state: "n"`；`css` 需带 `content`、`compiledContent`、`name`、`state`；`cssCache.ebd_page` 缺失时由 CLI 补平台默认值。
- 布局源码运行时由平台外壳提供 `pageId`、`ebSdk`、`pageSdk`、`formSdk`。250101 及以后基线可直接使用 `formSdk`；拿不到时用 `pageSdk.on('formReady')` 配合 `window.WeFormSDK.getWeFormInstance()`。实际可用性以目标环境为准。
- 写入后 CLI 会回读并校验 JS/CSS 原文、`compiledContent`、`pageId` 和 CSS 作用域；设计器解码自检失败时命令会报错，不会静默成功。
