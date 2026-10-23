# 浏览、选项、日期、附件与容器控件

## 浏览字段

| 需求 | API 与处理方式 |
|---|---|
| 获取已选对象 ID/显示名 | `getBrowserOptionId(field, splitChar?)` / `getBrowserShowName(field, splitChar?)`；返回字符串，默认以逗号分隔 |
| 获取完整选项对象 | `getBrowserOptionEntity(field)`；优先用它作为复制、合并和回填来源 |
| 浏览弹窗取数增加请求参数 | `appendBrowserDataUrlParam(field, {参数名:值})`；只是向请求附加参数，数据源须识别这些参数 |
| 回填浏览字段 | `changeFieldValue(field,{specialObj:[{id,name,data?}]})`；清空传空数组 |

浏览对象中的 `data` 对自定义浏览、附件等特殊来源很重要。不要把显示名称当 ID，也不要把添加请求参数误认为已在服务端实现数据过滤。运行时打开浏览弹窗检查实际可选记录。

## 选项字段

`getSelectShowName(field, splitChar?)` 取显示名，默认以逗号分隔；`getBrowserOptionEntity(field)` 可取选项对象。固定选项可按 ID 用 `value` 回填，选项模板按 `specialObj` 回填。

| 控制 | API |
|---|---|
| 从选项中移除 | `removeSelectOption(field, '选项ID1,选项ID2')` |
| 控制可显示选项 | `controlSelectOption(field, '选项ID1,选项ID2')` |
| 禁用/恢复选项 | `controlOptionDisable(field, '选项ID1,选项ID2', true/false)`；20250501 起，省略 flag 默认禁用 |

在表单 ready 后操作选项。移除、隐藏和禁用不是同义：分别验证弹窗/下拉是否显示、能否选中及已有值如何呈现。

## 日期

`controlDateRange(field, start?, end?)` 限定可选择范围。边界可传日期字符串（如 `2023-08-20`）或相对今天的天数字符串；`'0'` 表示今天。在原 SDK 的示例中，开始端 `'5'` 表示当前日期前 5 天，结束端 `'3'` 表示当前日期后 3 天；省略一端表示不限制该端。明细字段不加行 ID 时作用于整列。根据需求同时核验边界日期和越界日期。

```js
formSdk.controlDateRange(dateField, '2023-08-20', '2023-08-25');
formSdk.controlDateRange(dateField, '5', '3');
formSdk.controlDateRange(dateField, '0');
formSdk.controlDateRange(dateField, undefined, '0');
```

## 附件与复杂值

附件回填需要 `specialObj` 中对象带实际附件 `data`，包括文件 ID、类型、预览/下载等权限与操作信息。最稳妥的来源是已有字段 `getFieldObj` 或附件模块正式返回；仅 `{id,name}` 不足以保证预览。多级选项、浏览对象的次级数据可在 `data.content` 或 `data.dataOptions`，应先读取同类字段实际对象后组装。

```js
// data 应来自附件模块或现有附件字段，不在代码中凭空生成。
formSdk.changeFieldValue(attachmentField, {
  specialObj: [{id: file.id, name: file.name, type: 'file', data: file}]
});
// 多级选项的第二级是文本时：
formSdk.changeFieldValue(cascadeField, {
  specialObj: [{id: firstId, name: firstName, data: {content: secondText}}]
});
// 第二级是选项/浏览时，按已有控件对象构造 dataOptions：
formSdk.changeFieldValue(cascadeField, {
  specialObj: [{id: firstId, name: firstName, data: {dataOptions: [{optionId: secondId, content: secondName}]}}]
});
```

原附件案例中的 `data` 含 `fileid/name/size/extName/type/img/uploadUser/uploadUserName/uploadTime/doc/docId/loadlink/options/uploadType/ban/secretLevel/validity/folderId` 等字段。哪些必填、哪些操作可见由附件来源与权限决定；复制已有对象比手填这套结构可靠。

## 选项卡容器

`switchTabItem(tabField, '序号')` 按从 1 开始的序号切换，或 `switchTabItem(tabField, tabId, 'id')` 按页签 ID 切换。`getFieldInfo(tabField).tabOptionTitle` 可检查页签信息，其中 `uid` 为 ID。20250501 及以后基线的 `changeTabItemAttr(tabField, '页签ID或序号, ...', attr)` 控制页签属性：`'1'` 禁用、`'2'` 可编辑、`'3'` 隐藏；一组调用中不要混用 ID 与序号。页签是布局容器，不当作普通选项字段写值。
