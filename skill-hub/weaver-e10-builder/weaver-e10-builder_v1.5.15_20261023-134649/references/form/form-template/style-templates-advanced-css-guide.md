# 表格式高级模板：CSS 编写指南

本篇适用于 **PC 表格式高级模板**。先在模板设置中确定字段与重复区域的位置、行列尺寸、合并和单元格样式，再用 CSS 设置页面主题、组件状态和交互效果。下述组件路径已在实际模板预览页中找到；不同字段类型的内部元素不同，使用规则前应确认目标表单含有该元素。

## 一、样式写在哪一层

| 目标 | 首选位置 | 原因 |
| --- | --- | --- |
| 字段顺序、重复区域、列宽、行高、合并 | 模板结构与网格 | CSS 不能改变占位组件及迭代关系 |
| 某个模板单元格的文字、底色、对齐、边框、缩进 | `grid.main`／`grid.detail` 或完整配置的 `workbook` | 样式随字段占位单元格迭代，位置明确 |
| 所有普通字段或明细字段的输入框／浏览框边框与背景 | `layoutStyle.field`／`layoutStyle.detailFields` | 设计器为相应组件生成样式，无需逐个字段写 CSS |
| 主题色、按钮与选择状态、隔行色、悬停色、特定控件的额外包裹层 | CSS 源码 | 一套选择器可用于整个模板 |
| 单个业务字段的专属外观 | 目标表单的组件设置 | 模板内没有稳定的业务字段 ID，不应把预览页的 `#widget_…` 写入通用 CSS |

源码直接写 `.ebpage`、`.weapp-form-detail-table-wrapper` 等选择器。平台会给编译结果加当前模板作用域，如 `#ebpage_…`；不要手写这类 ID。布局规则还会出现 `#weapp-form-layout__…`，具体字段规则可能带 `#widget_…`。这两类 ID 也不适合作可复用选择器。

## 二、页面结构与组件选择器

页面根容器为 `.weapp-de-excel-render.ebpage.ebpage-pc`。主网格是 `table.weapp-de-excel-render-main`，分组内另有 `table.weapp-de-excel-sheet-render-main`。表格 `td` 是**单元格边线**所在层，字段控件在 `td` 内。分组容器为 `.weapp-form-widget__Collapse`，明细表容器为 `.weapp-form-detail-table-wrapper`。

| 对象 | 页面中可用的类或路径 | 样式关注点 |
| --- | --- | --- |
| 单行文本、数字、金额 | `.weapp-form-widget__Text`、`.weapp-form-widget__Number`、`.weapp-form-widget__Money` 下的 `.weapp-form-input-wrapper` 与 `.weapp-form-input-style` | 输入区边框、背景、字体；金额单位在旁边，应保留 |
| 多行文本 | `.weapp-form-widget__TextArea .weapp-form-textarea-wrapper textarea` | 边框、背景、内边距、高度与换行 |
| 邮箱、电话、手机、身份证 | 对应字段类下的 `.ui-input-wrap.ui-input-suffix-wrap` | 输入包裹层边框；保留 `.ui-input-suffix` 图标 |
| 日期、日期区间 | `.weapp-form-date-wrapper .ui-input-wrap`；`.weapp-form-date-range-wrapper .ui-date-picker-rangeWrap` | 日期包裹层边框；保留日历图标和“至” |
| 下拉、级联 | `.weapp-form-widget__Select .ui-select-input`；`.weapp-form-widget__Cascader .ui-cascader-picker` | 输入外观；选项面板和箭头是其他元素 |
| 人员、部门及组织浏览 | `.weapp-form-widget__Employee`、`.weapp-form-widget__Department`、`.weapp-form-widget__EmployeeOrganization`、`.weapp-form-widget__EmployeeScope` 下的 `.ui-browser` | 浏览输入和已选内容；人员范围还有 `.ui-browser-types-select-wrap` |
| 树形、分部、收发文单位选择 | `.weapp-form-widget__TreeSelect`、`.weapp-form-widget__SubCompany`、`.weapp-form-widget__ODocReceive` 下的 `.ui-browser` | 与人员浏览结构相近，仍应逐个核对包裹层 |
| 单选、复选 | `.weapp-form-widget__RadioBox`、`.weapp-form-widget__CheckBox` 下的 `.ui-radio`／`.ui-checkbox` | 选中态和间距；圆点、方框是可操作标记 |
| 附件、图片 | `.weapp-form-widget__File`、`.weapp-form-widget__Image` 下的上传包裹层和 `.ui-upload` | 上传区域尺寸、底色；保留虚线框及按钮 |
| 其他可见组件 | `Paragraph`、`Rate`、`Position`、`ProgressBar`、`Switch`、`Sign`、`Monitor`、`SerialNum`、`DivideLine` 等字段类 | 描述、评分、位置、进度、开关、签名、编号及分割线需分别处理，不能假定都使用 `.weapp-form-input-style` |
| 分组 | `.weapp-form-widget__Collapse` 下的 `.weapp-form-collapse-title`、`.weapp-form-collapse-content` | 标题装饰和内容区域；标题也可用 `layoutStyle.group` 设置 |

同一行列出的不同字段类型需分别指定，或用逗号列出完整选择器。页面中可见组件结构，并不等于其全部样式属性都已验证；先使用已确认的通用配置，再核对特殊组件。

## 三、主题变量

把主题色集中写在 `.ebpage`。蓝色和红色主题可沿用同一组变量，只改 `--primary` 及需要区分的悬停色。

| 变量 | 对应状态 |
| --- | --- |
| `--primary`、`--btn-primary-hover-bg` | 主题色与主按钮悬停色 |
| `--checkbox-active-border-color`、`--checkbox-active-background-color` | 复选选中边框与背景 |
| `--radio-active-border-color`、`--radio-active-inner-background-color` | 单选选中边框与圆点 |
| `--switch-checked-bc`、`--switch-checked-border` | 开关开启态背景与边框 |
| `--input-focus-shadow`、`--input-focus-border-color` | 输入区聚焦强调色 |
| `--title-icon-border` | 标题边线；已有写法为 `calc(var(--hd) * 1) solid var(--primary)`，使用前确认页面定义了 `--hd` |
| `--m-chk-check-bc`、`--m-chk-check-border-color`、`--m-switch-checked-bc` | 另一组选择与开关状态变量；具体组件和终端范围需在实际页面核对 |

```css
.ebpage {
  --primary: #347FCB;
  --btn-primary-hover-bg: #286DAF;
  --checkbox-active-border-color: var(--primary);
  --checkbox-active-background-color: var(--primary);
  --radio-active-border-color: var(--primary);
  --radio-active-inner-background-color: var(--primary);
  --switch-checked-bc: var(--primary);
  --switch-checked-border: var(--primary);
  --input-focus-border-color: var(--primary);
}
```

变量只有被当前组件读取时才改变显示；不能仅凭变量名称断定其已覆盖某个组件的全部状态。应查看选中、悬停和聚焦后的实际效果。

## 四、边框的层级与去边框方法

截图中的双列信息表需要**单元格边线**，明细表需要**外框和内部分隔线**；文本、日期、下拉和浏览输入本身通常不再画一层框。单行文本的结构是 `td` → `.weapp-form-widget__Text` → `.weapp-form-widget-content-container` → `.weapp-form-input-wrapper` → `input.ui-input.weapp-form-input-style`。有边框时先判断画在哪一层：

1. `td` 或明细表的 `th`、`td`：这是表格线，通常保留。
2. `.weapp-form-input-style`、`.ui-input-wrap`、`.ui-select-input`：字段输入框，可按类型去掉。
3. 浏览组件可能还有 `.ui-input-suffix-wrap`：通用浏览框设置未消掉它时，再加定向 CSS。
4. 单选／复选标记、附件／图片上传虚线框是操作提示，不应套用文本框去边框规则。

模板配置优先用以下结构去掉通用输入与浏览框边线：

```json
{
  "layoutStyle": {
    "field": {
      "input": { "backgroundColor": "#FFFFFF00", "border": "none" },
      "browser": { "backgroundColor": "#FFFFFF00", "border": "none" }
    },
    "detailFields": {
      "content": { "border": "none" },
      "input": { "backgroundColor": "#FFFFFF00", "border": "none" },
      "browser": { "backgroundColor": "#FFFFFF00", "border": "none" }
    }
  }
}
```

当前页面可见，文本类 `.weapp-form-input-style`、日期 `.ui-input-wrap`、日期区间 `.ui-date-picker-rangeWrap`、下拉 `.ui-select-input` 和部分浏览输入会获得 `border: 0px none transparent`。由于结构不同，不要写 `.ebpage input, .ebpage * { border: none; }` 这种全局清除规则。

人员范围与共享浏览输入存在额外包裹层时，可补：

```css
.weapp-form-widget-content-container .ui-browser-types-select-wrap .ui-input-suffix-wrap,
.weapp-form-widget-content-container .ui-browser-share-select-wrap .ui-input-suffix-wrap {
  border: none;
}
```

第二个选择器是已有模板中的写法；目标页面是否含共享浏览组件，应按页面结构核对。其他浏览类型仍有边框时，应先定位真正画线的元素，再添加该类型的规则。

## 五、明细表表头、网格与行状态

实际页面中明细表不只一张表：固定表头使用 `.excelTableView-content-excel-table-fixed-first-row`，内容表使用 `.excelTableView-content-excel-table`。内容表中有 `thead`、`tbody`；数据行可通过 `tr[data-id]` 选择。滚动后固定表头也需保持配色时，应同时核对两张表。下例给内容表设置边框与行色，并同时覆盖固定表头的表头颜色：

```css
.weapp-form-detail-table-wrapper .excelTableView-content-excel-table {
  border: 1px solid #DCE3EB;
  border-collapse: collapse;
}

.weapp-form-detail-table-wrapper .excelTableView-content-excel-table th,
.weapp-form-detail-table-wrapper .excelTableView-content-excel-table td {
  border: 1px solid #DCE3EB;
}

.weapp-form-detail-table-wrapper .excelTableView-content-excel-table thead th,
.weapp-form-detail-table-wrapper .excelTableView-content-excel-table thead td,
.weapp-form-detail-table-wrapper .excelTableView-content-excel-table-fixed-first-row thead th,
.weapp-form-detail-table-wrapper .excelTableView-content-excel-table-fixed-first-row thead td {
  background-color: #347FCB;
  color: #FFFFFF;
  text-align: center;
}

.weapp-form-detail-table-wrapper .excelTableView-content-excel-table tbody tr[data-id]:nth-child(even) > td {
  background-color: #F8FAFD;
}

.weapp-form-detail-table-wrapper .excelTableView-content-excel-table tbody tr[data-id]:hover > td {
  background-color: #E9F2FC;
}

.weapp-form-detail-table-wrapper .excelTableView-content-excel-table tbody tr[data-id]:focus-within > td {
  background-color: #DAEAFA;
}
```

给 `tr` 设背景时，已有 `td` 背景可能遮住行色；针对 `> td` 更稳妥。`:nth-child(even)` 按同一 `tbody` 的实际子元素位置计数，若插入额外行，隔行顺序可能变化。表头字段标题的基础对齐也应在明细子网格设置，不只依赖 CSS。

## 六、分组与不同字段类型

分组标题左侧蓝线、背景、字重和间距优先写在 `layoutStyle.group` 或对应网格单元格。白色分组卡片与浅灰页面底色可用模板设置和 CSS 配合。图片中的多个“分组”标题会按模板迭代；不要在 CSS 中写死第一组或第二组的业务名称。

预览页同时有分组内字段和分组外字段。仅写 `.weapp-form-widget__Collapse .weapp-form-widget__Text` 只会命中分组内单行文本；希望普通字段统一生效时，优先使用 `layoutStyle.field`。明细字段又在 `.weapp-form-custom-style__DetailTable .weapp-form-detail-table__body-wrapper` 下，应使用 `layoutStyle.detailFields` 或明细表专用选择器。

日期、下拉、级联和人员选择常由**外层包裹层**画边框，并非最内侧的 `<input>`。例如日期可定位 `.weapp-form-widget__Date .weapp-form-date-wrapper .ui-input-wrap`，下拉可定位 `.weapp-form-widget__Select .ui-select-input`。仅清除 `input.ui-input` 的边框，外层仍可能有线。应保留日历、下拉、邮件、电话等尾部图标和日期区间中间的“至”。

附件、图片、评分、进度条、开关、地理位置、签名和描述文字有各自的组件结构。先确定 `.weapp-form-widget__File`、`.weapp-form-widget__Image`、`.weapp-form-widget__Rate`、`.weapp-form-widget__ProgressBar`、`.weapp-form-widget__Switch`、`.weapp-form-widget__Position`、`.weapp-form-widget__Sign` 或 `.weapp-form-widget__Paragraph` 容器，再限定内部元素。状态色优先考虑主题变量；上传虚线框、签名区和评分星形等可操作提示应按具体需求单独调整。

## 七、覆盖顺序与验证

页面同时存在底层渲染器 CSS、模板生成的网格／字段样式、模板 CSS 和业务字段自己的样式。渲染器提供 `.weapp-de-excel-render-main`、`.weapp-de-excel-sheet-render-main` 的表格基础规则，并给 `td` 基础内边距；模板网格生成类似 `.cell_…` 的类。**不要把自动 `.cell_…` 或 `#widget_…` 写成通用规则**。具体单元格样式回到模板网格配置修改。

如果 CSS 写入后没有效果，按顺序检查：

1. 目标元素是否命中选择器。输入框、外层包裹层与表格单元格常是不同元素。
2. `advanced css show <模板ID>` 的源码与编译结果是否含该规则；源码不应手写模板 ID。
3. 实际页面是否有优先级更高的布局样式、业务字段样式或元素内联样式。先改对应设置；确需 CSS 覆盖时再补足组件上下文，不先全局加 `!important`。
4. 普通、只读、聚焦、选中、悬停及滚动固定表头状态是否符合预期。保存后的不落库预览和目标表单显示都要检查。

新建时把 CSS 存为独立文件，执行 `advanced create --config @模板.json --css-file 模板.css`；已有模板执行 `advanced css update <模板ID> --file 模板.css`，再用 `advanced css show <模板ID>` 回读。具体命令与完整配置方法见[高级模板手册](style-templates-advanced.md)。
