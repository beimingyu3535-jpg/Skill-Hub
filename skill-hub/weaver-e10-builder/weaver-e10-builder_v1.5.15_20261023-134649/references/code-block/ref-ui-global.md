# 组件渲染、全局交互与扩展

## 当前表单与全局操作

`formSdk.getBaseInfo()` 读取当前表单基本信息；`formSdk.isMobile()` 判断移动端。布局级代码优先使用当前作用域 `formSdk`；提示、弹窗由全局 `window.WeFormSDK` 提供。

| 效果 | API 与要点 |
|---|---|
| 提示 | `window.WeFormSDK.showMessage(message, type?, duration?)`；type 为 `1` 警告、`2` 错误、`3` 成功；时长单位秒 |
| 确认 | `window.WeFormSDK.showConfirm(content, onOk, onCancel?, {title,okText,cancelText}?)`；title 仅 PC 有效 |
| 自定义弹窗 | `window.WeFormSDK.openCustomDialog({content,width,height,onOk,onCancel,footer?,...})`；返回对象可 `destroy()` |
| 页面刷新 | `formSdk.reloadPage(params?)` |
| 提交附加参数 | `formSdk.appendSubmitParam({customParam:{...}})`；接收端仍须能处理该参数 |
| 主动做必填检查 | `formSdk.verifyFormRequired(mustAddDetail?,fieldRequired?)` |
| 全局加载 | `window.WeFormSDK.getLoadingGlobal()` 取加载控件，调用 `start()`、`end()`、`destroy()` |
| 关闭页面提示 | `formSdk.setFormTipCloseStatus(true/false)`；只控制提示状态，不执行保存 |

自定义 footer 使用 `@weapp/ui` 的 import/JSX 是 ecode 构建环境示例；布局源码只允许其编辑器可编译的语法和已暴露对象，不能直接套用 ecode 依赖。

## 字段区域事件和局部渲染

`bindFieldAction(type, fields, handler)` 绑定失焦、聚焦、点击、双击、移入/移出；事件类型为 `onblur/onfocus/onclick/ondbclick/mouseover/mouseout`。

| 需求 | API |
|---|---|
| 将当前字段内容替换为自定义内容 | `proxyFieldComp(fieldMark, reactNode或文本, range?)` |
| 在字段后追加内容 | `afterFieldComp(fieldMark, reactNode或文本, range?)` |
| 用函数包装原字段内容并利用 props 决定样式 | `proxyFieldContentComp(fieldMark, (props, componentFn) => React.createElement(..., componentFn()))` |

`range` 省略时作用于全部读写状态；`'1'` 只读、`'2'` 可编辑、`'3'` 必填，多个值以逗号分隔。`proxyFieldContentComp` 的回调必须返回组件，第二参数 `componentFn` 可生成原字段内容。`React` 可用性和编译语法要以目标代码入口为准。明细字段不加行 ID 可作用于整列，指定行则加 `_rowId`；新添行的专门逻辑应在添加行事件后检查是否生效。此能力是当前表单字段的局部渲染，不等于发布平台级新组件，也不等于改写后端接口。

```js
const field = formSdk.convertFieldNameToId('status', 'main');
formSdk.proxyFieldContentComp(field, (props, original) =>
  React.createElement('div', {style: {backgroundColor: props?.widgetValue?.content === '1' ? '#e3f2fd' : ''}}, original())
);
```

## 插件与页面间通信

260201 及以后基线提供 `formSdk.pluginGet(fieldMark, property)` 和 `formSdk.pluginExecute(fieldMark, method, ...args)`；只能操作该插件实际公开的属性/方法。具体 WPS 或其他插件须取得该插件契约，不能从 JSSDK 通用接口推断方法名。

`window.open` 打开的子页面可通过 `window.opener` 访问父窗口；同源时可操作父页面的表单实例。跨源时用 `postMessage`，接收方检查 `event.origin` 和 `event.data.type`，发送方指定目标 origin；只发送必要数据，不传鉴权信息。

子表控件数据变化后，如需刷新相关显示，布局源码中可调用 `pageSdk.events.emit('field.change', '纯数字字段ID')`；ecode 中可调用 `window.ebuilderSDK.getPageSDK().events.emit('field.change', '纯数字字段ID')`。原资料还提到可附第三个字段数据参数：文本传文本，浏览型传以逗号分隔的 ID；按实际刷新需求决定是否传值。此处第二参数是纯数字字段 ID，不是带 `field` 前缀的标识。

全局 ecode 的 `regOvProps` 可复写特定组件 props，但其包名与目标组件名是项目级契约；它和布局内 `proxyFieldContentComp` 是不同层级。采用哪一层，应以所需生效范围为准。
