# JSSDK 排查、版本与边界

## 代码不生效时

1. 确认保存的是目标表单的目标布局及目标终端，或正确的表单级/全局 ecode；JS 编译通过且代码已启用，CSS 单独保存。浏览器打开的是最新布局而非另一设备布局。
2. 确认 `formSdk` 取自当前表单实例；全局 ecode 用 `onFormReady` 的事件实例并限定 formId/module。较早基线的 `pageSdk.on('formReady')` 与新基线闭包方式不要混用到未支持的入口。
3. 用 `getBaseInfo`、`convertFieldNameToId`、`getFieldInfo` 检查当前表单和字段；数据 Key 不是字段名或物理表名。明细字段要指定明细表位置，行操作要取得真实 `rowId`。
4. 用 `getFieldObj` 对照目标类型的数据形状。文本/数字/日期常用 `{value}`；浏览/动态选项/附件常用 `{specialObj}`。附件预览还依赖完整 `data`。
5. 检查事件是否属于“表单保存”“流程提交”“用户改变”“联动改变”中的哪一种；必要时分开绑定。拦截回调必须调用通过或阻断函数；异步超时约 25 秒。
6. 检查权限和组件边界。流程节点默认只读或权限锁定的字段，不能仅靠 `changeFieldAttr(2)` 放开；JS 渲染也不改变后端权限。

开发调试时可按环境入口临时屏蔽不同层级二开：ecode 平台、全局初始化代码、布局源码对应不同入口。调试开关仅用于定位，不作为正式配置。对含多表单、父子页面、明细新行的场景，还要检查实例、`postMessage` 来源与渲染时机。

## 设计器源码面板为空 / ECode decode failed

- **症状**：打开布局源码时控制台报 `ECode decode failed, SyntaxError: Expected ':' after property name in JSON at position 5`，源码面板为空，预览按钮失效。
- **原因**：`sourceCode.ecode` 被 `encodeURIComponent` 写入。设计器用 `JSON.parse(decodeURI(ecode))` 读取，而 `decodeURI` 不还原 `%3A`（冒号），JSON 变成 `{"js"%3A...}`。
- **处理**：用 `form code layout set` / `wf-form code layout set` 重新写入（CLI 已使用 `encodeURI`，并在写入前、回读后按设计器路径自检）。临时恢复可把 `sourceCode.ecode` 置为空字符串，再用空 JS/CSS 文件重写。
- **手工调接口**：必须用 `encodeURI(JSON.stringify({js, css}))`，不要用 `encodeURIComponent`。

## 基线速查

| 功能 | 原技术资料标注的最低基线 |
|---|---|
| `changeFieldValue` 的联动控制参数 | 241001 |
| `valueInfo.type/contentObj` 特殊字段 | 241201 |
| 字段联动拦截及联动动作的 `runData` | 240601 |
| 字段变化事件的联动 `scope` | 250401；明细专用事件的扩展参数 250901 |
| 明细批量添加 `addDetailData` | 241201 |
| 布局/表单代码直接取得当前 `formSdk` | 主体说明标注 250101；另有一处写 241201，稳妥按 250101 判断 |
| 明细批量更新 `changeDetailData` | 250101 |
| `changeTabItemAttr` | 20250501 |
| `controlOptionDisable` | 20250501 |
| `convertFieldNameToId` 用明细表数据 Key 定位明细字段 | 260601 |
| `getDetailData` 按当前明细筛选条件取数 | 260401 |
| `triggerFieldAllLinkage(...).then(...)` | 250901 |
| 联动赋值导致的明细行变化事件扩展 | 251101 |
| `pluginGet/pluginExecute` | 260201 |

先确认目标环境版本和实际 API 可用性；未达到基线时不要假设同名功能可用。

## 原案例中需纠正的写法

- 字段赋值示例声明 `textFieldMark` 后却调用 `fieldMark`，日期示例声明 `dateFieldMark` 后调用 `selectFieldMark`；按真正声明的目标字段写。
- 字段属性示例的明细行模板字符串缺少引号闭合；正确形式为 `` `${detailField}_${rowId}` ``。
- `getFieldCom` 章节示例调用了 `getFieldInfo`；两者用途不同，前者为组件引用，后者为字段信息。
- 明细“默认使用末行”章节的示例实际调用 `setDetailAddUseCopy`；先确认所需是复制末行，而非仅控制默认光标或位置。
- 案例中的 `eval(numbers.join('+'))`、测试 URL、固定附件元数据、模拟外部查询结果不能直接用于业务配置。数值合计用显式转换与 `reduce`，外部接口须有真实契约。
- 全局 ecode 的 `import`、JSX、`regOvProps` 示例不要直接粘入布局源码；按目标编辑器支持的语法重写。布局源码中的局部字段组件复写则按其 API 单独处理。
