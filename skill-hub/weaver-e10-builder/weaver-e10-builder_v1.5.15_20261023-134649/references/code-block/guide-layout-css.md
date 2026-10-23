# 表单布局 CSS 编写指南

本篇用于**已创建的表单布局**：给指定布局的 PC 或移动端页面写 CSS。适用于表单引擎表单与流程表单的表格式、流式布局。表格式高级**模板**的 CSS 属于另一份配置，模板的网格和重复标记也不会由这里的 CSS 生成。

## 能设置什么

| 目标 | CSS 可处理的内容 | 先确认的配置或结构 |
| --- | --- | --- |
| 页面主题 | 页面区域的背景与文字颜色、主题变量、按钮和选中状态颜色 | 页面根容器及变量是否被当前组件读取 |
| 标题与分组 | 标题颜色、字重、底线，分组标题装饰、背景、内外间距 | 表格式的单元格样式或流式的分组结构 |
| 字段组件 | 输入框、文本域、下拉、日期、浏览框的背景、边框、字体、内边距；提示语和焦点状态 | 各组件实际画边框的包裹层；保留图标和操作标记 |
| 明细表 | 表头色、标题对齐、边框、隔行色、悬停与聚焦行色 | 是否存在相应明细表 DOM；固定表头是否另有一张表 |
| 响应状态 | `:hover`、`:focus-within`、`:checked` 等状态，以及 `@media` 下的样式 | PC 与移动端分别检查，不能假定结构一致 |

CSS 只改变已有元素的呈现。字段顺序、主表与明细表的迭代、合并单元格、字段组件类型和表单数据仍在布局或表单配置中处理。表格式布局的列宽、行高、单元格边框优先在网格中设置；流式布局的区域排列优先在布局设置中完成。

## 作用范围和写入

布局 CSS 按**布局 ID + 终端**保存。CSS 文件中写普通选择器，例如 `.ebpage`；CLI 会给普通规则加当前页面的 `#ebpage_<pageId>` 前缀。不要自己写这个页面 ID，也不要复制模板编译后的 `#widget_…`、`.cell_…` 等生成标识。`@media`、`@supports` 中的普通选择器同样会加作用域；`@keyframes` 保持原样。需要被这份 CSS 修饰的动态元素应放在布局页面容器内，挂在 `document.body` 下的弹层不在此作用域内。

```bash
# 先读取当前 PC 布局代码，保存现有 CSS 供修改
e10-cli form code layout read <表单objId> --app-id <应用ID> --layout-id <布局ID> --terminal PC

# 将 CSS 文件写入该 PC 布局；JS 保持原状
e10-cli form code layout set <表单objId> --app-id <应用ID> --layout-id <布局ID> --terminal PC --css <CSS文件>

# 写入后回读
e10-cli form code layout read <表单objId> --app-id <应用ID> --layout-id <布局ID> --terminal PC
```

流程表单对应 `e10-cli wf-form code layout read/set <formId> --layout-id <布局ID> --terminal PC|MOBILE [--css <CSS文件>]`，不需要 `--app-id`。移动端把 `--terminal` 改为 `MOBILE`，并针对该终端另写一份 CSS。`set --css` **整份替换**该布局、该终端原有 CSS；写入前先读出现有内容并合并到文件中。只传 `--css` 时已有 JS 保留。回读会核对源码和编译结果，随后仍需打开实际表单检查视觉效果。

## 通用写法

### 主题与选择状态

页面根节点存在 `.ebpage` 时，可集中设置主题变量；变量只对读取它的组件起作用。颜色和变量名称可参考表格式高级模板的 [CSS 指南](../form/form-template/style-templates-advanced-css-guide.md)，但应在目标布局验证实际状态。

```css
.ebpage {
  --primary: #347fcb;
  --btn-primary-hover-bg: #286daf;
  --checkbox-active-border-color: var(--primary);
  --checkbox-active-background-color: var(--primary);
  --radio-active-border-color: var(--primary);
  --radio-active-inner-background-color: var(--primary);
  --input-focus-border-color: var(--primary);
}
```

### 字段输入区域

先看实际元素是输入框自身画线，还是其外层包裹层画线。以下是**表格式 PC 页面已识别的组件路径**，仅在目标布局存在相同 DOM 时复用；流式布局先检查对应组件结构再写选择器。

```css
/* 文字输入：只清除控件边框，保留表格单元格边线。 */
.weapp-form-widget__Text .weapp-form-input-style {
  border: none;
  background: transparent;
}

/* 浏览框的额外包裹层：目标页面确有此层时使用。 */
.weapp-form-widget-content-container .ui-browser-types-select-wrap .ui-input-suffix-wrap {
  border: none;
}
```

多行文本、日期、下拉、浏览框可能由 `textarea`、`.ui-input-wrap`、`.ui-select-input`、`.ui-browser` 或更外层绘制边框；逐个定位实际画线元素。避免对 `.ebpage input` 或 `.ebpage *` 一次性去边框，这会误伤选择标记、上传区和表格线。

### 表格式布局的明细表

以下规则针对已识别的表格式 PC 明细表结构。流式明细表只有在实际存在这些类和表格元素时才可复用。

```css
.weapp-form-detail-table-wrapper .excelTableView-content-excel-table tbody tr[data-id]:nth-child(even) > td {
  background: #f7f9fc;
}

.weapp-form-detail-table-wrapper .excelTableView-content-excel-table tbody tr[data-id]:hover > td {
  background: #e9f2fc;
}

.weapp-form-detail-table-wrapper .excelTableView-content-excel-table tbody tr[data-id]:focus-within > td {
  background: #daebfa;
}
```

明细表标题对齐与基础边框先用布局网格设置。需要 CSS 补充表头配色时，同时检查内容表与固定表头 `.excelTableView-content-excel-table-fixed-first-row`。把背景写到 `td` 上，是为了避免单元格自带背景遮住整行状态色。

## 表格式与流式如何选规则

| 对象 | 表格式布局 | 流式布局 |
| --- | --- | --- |
| 页面主题变量 | 可从 `.ebpage` 开始，检查组件是否读取变量 | 同样从实际页面根节点检查 |
| 字段控件 | 核对 `.weapp-form-widget__…` 与内部包裹层 | 核对实际组件路径；相同 DOM 才复用 |
| 字段与分组位置 | 改网格、标记和单元格配置 | 改流式布局配置 |
| `table`、`td`、明细表规则 | 仅用于真实存在的表格与明细表 | 不把表格式选择器直接套到流式区域 |

## 检查顺序

1. 读取目标布局和终端的原 CSS，确认页面上确有要修改的元素及类名。
2. 明确样式应落在页面、区域、网格单元格、组件包裹层还是输入元素；优先使用对应的布局配置，再写需要补充的 CSS。
3. 写入完整 CSS 文件，回读源码与编译结果；不要把编译后的页面 ID 写回源码。
4. 在实际表单中检查普通、只读、悬停、聚焦、选中及明细表滚动状态；移动端单独检查。

模板 CSS 指南提供更多 **PC 表格式**组件路径与状态写法；它们是选择器参考，并非流式布局的 DOM 保证。布局源码的其他规则见[表单代码块配置指南](guide-code-block.md)。
