# 表格式布局：高级模板（PC）

高级模板用字段占位符、重复区域和网格定义表单的排列与外观。本篇适用于 **PC 表格式布局**。模板的选择、保存、预览和应用原则见[样式模板总览](style-templates.md)；简易模板与流式模板分别见[简易模板](style-templates-easy.md)、[流式模板](style-templates-flow.md)。

## 先判断设置范围

| 设置范围 | 用来修改 | 当前 CLI 入口 |
| --- | --- | --- |
| 模板设置：结构 | 主表字段组数、重复标记、分组和明细表的位置 | 新建配置可选主表、分组、明细表；复杂结构可复制或导入完整布局 |
| 模板设置：网格 | 主表或明细表的整行、整列、指定单元格 | `advanced grid show/update`；新建时可写 `grid` |
| 组件设置 | 选中的某个具体组件 | 尚未开放通用编辑命令 |
| CSS 源码 | 当前模板页面的视觉样式、组件状态和高亮 | `advanced css show/update`；新建时可用 `--css-file` |
| 布局样式 | 页面、所有普通字段、明细字段或分组的通用配置 | `advanced style show/update`；新建时可写 `layoutStyle` |

修改时先选**模板设置**：结构、行列、单元格及组件关联由模板本身保存；外观与交互状态优先写**CSS**。只有需要设计器的通用属性、行为设置，或模板设置与 CSS 不能准确表达时，再用**布局样式**。同一外观尽量只在一处定义，避免层叠覆盖后难以判断来源。布局样式不按单元格坐标设置；网格中的 `rowHeights` 修改整行，`columns` 修改整列，`cells` 才修改指定单元格，重复区域内的单元格样式会随字段一起迭代。

## 一、模板设置

### 结构与重复规则

| 内容 | 必需性与放置规则 | 基础新建配置 |
| --- | --- | --- |
| 主表字段重复开始、结束标记 | **必需且成对**。两者之间是主表字段的重复单元 | 自动生成 |
| 主表字段标题和主表字段 | **至少一组**，标题与字段一一对应，均位于主表重复标记之间；可用 1–4 组，按模板中的排列与样式迭代所有主表字段 | 简单等宽排列用 `fieldPairsPerRow: 1/2`；混合行数用 `fieldRows`；标题、字段分别定位及跨列用 `fieldPlacements` |
| 分组开始、结束标记及分组名称 | **可选**。使用分组时两个标记必须成对，分组名称位于其中且只放一次；分组标记不可插在主表重复标记之间 | `group: {"enabled": true}` 自动生成；省略则无分组区域 |
| 明细重复开始、结束标记及明细表区域 | **可选**。使用时两个标记成对，明细表区域位于其中；多个实际明细表按该区域的设计迭代 | `detailTable: {"enabled": true}` 自动生成；省略则无明细区域 |
| 明细表头、表尾标识 | 明细表**子网格必有**，分别占独立行；它们与主网格的明细重复开始、结束标记不是同一层内容 | 启用 `detailTable` 后自动生成；可设置其所在行 |
| 明细字段标题、字段迭代 | 位于明细表子网格；字段迭代在横向、纵向中选一种，同一模板不同时放两种 | 默认生成字段标题和横向迭代；可设置方向和位置 |
| 明细标题描述、操作按钮、全选、行选中、序号列头、行序号 | 位于明细表子网格，各自占一个单元格；位置可根据表头、数据行结构调整 | 默认全部生成；可分别设置坐标 |
| 表单标题、静态文字 | **可选**，可放在空白单元格中，不能覆盖已有字段组件 | `headerTitle: "formTitle"`、`sectionTitle` 或 `grid.main.cells` 的 `text` / `systemParameter` |

基础新建按下面的顺序放置。标有“可选”的区域可以整段省略；分组和明细区域互不依赖：

```text
表单标题、静态文字（可选）
分组开始 → 分组名称（可选分组区域的开头）
主表字段重复开始
  标题1 → 字段1 → 标题2 → 字段2（每行按需要排列 1–4 组）
主表字段重复结束
分组结束（可选分组区域的结尾）
明细重复开始（可选明细区域的开头）
  明细表区域
    明细表头、表尾；标题描述、按钮、勾选、序号等系统位置
    明细字段标题；横向或纵向字段迭代
明细重复结束（可选明细区域的结尾）
```

`group` 和 `detailTable` 可以单独启用，也可以同时启用。主表字段占位符编号为 1–4，每个标题和同号字段组成一对。先确定**一次重复单元**需要几对，再选择一种结构写法：

| 写法 | 可以配置的排列 | 配置方法 |
| --- | --- | --- |
| `fieldPairsPerRow` | 一行放一对或两对 | 写 `1` 或 `2`；省略时为一对 |
| `fieldRows` | 1–4 对按多行排列；每行 1–4 对，标题与字段相邻 | 外层数组按行排列，内层数组按从左到右的占位符编号排列；例如 `[[1], [2,3], [4]]` |
| `fieldPlacements` | 每对标题、字段可独立选行、列、跨列；可同排、错排或分行 | 每对写一个 `pair`，分别设置 `title` 和 `field` 的 `row`、`col`、可选 `colSpan` |

三种写法只选一种，编号从 1 开始连续使用，不能重复或跳号。`fieldPlacements` 的 `row` 从**主表重复开始标记后的第一行**算起，`col` 从主网格第 0 列算起，`colSpan` 是占用的列数，省略时为 1。标题与字段可在不同的行和列；各自的单元格或跨列范围不能重叠。写 `fieldPlacements` 时还须给出完整的 `columnWidthsPercent`：数组项数就是主网格列数，所有列宽百分比合计 100，每个位置及跨列范围都必须在网格之内。需要留白时在两端预留列；需要给某项更多宽度时，增加对应列的百分比或使用 `colSpan`。CLI 会根据最后一个字段所在行设置重复结束标记，并生成组件与单元格的关联。

配置顺序建议为：① 画出重复单元的行列网格，标注每对标题与字段要占的格子；② 确定列宽总和为 100；③ 根据是否需要错排、跨列选择上述写法；④ 如启用分组或明细表，再设置其区域；⑤ 保存后用应用预览核对字段迭代顺序、宽度和跨列。仅供对照的完整配置见[逐行排列样例](../../../assets/form-template/style-templates-advanced-structure-example.json)与[独立定位样例](../../../assets/form-template/style-templates-advanced-placements-example.json)。任意跨行合并及其他组件位置仍需以已有模板为底稿或编辑完整布局；手工修改时要同步维护组件坐标、单元格关联、子网格和合并区域。

明细表的推荐默认结构是：第 0 行放标题描述和操作按钮，第 1 行放全选、序号列头和明细字段标题，第 2 行为表头标识，第 3 行放行选中、行序号和字段横向迭代，第 4 行为表尾标识。表头、表尾各占独立行。需要纵向排列字段时，把 `fieldRepeatDirection` 设为 `vertical`；位置可以通过 `detailTable.controlPositions`、`fieldTitlePosition`、`fieldRepeatPosition` 调整。`controlPositions` 只修改指定项目，其余位置沿用上述默认值；所有位置均为从 0 开始的子网格行、列坐标，不能重叠。展开行暂没有经过验证的基础新建配置项；已有模板若带有该结构，应使用底稿或完整布局配置保留，不凭名称自行构造。

`controlPositions` 中的名称与作用如下：

| 名称 | 对应内容 | 默认位置（行，列） |
| --- | --- | --- |
| `de_title`、`de_tail` | 表头标识、表尾标识；两者必有，各占独立行 | `(2,0)`、`(4,0)` |
| `de_titletext`、`de_btn` | 明细表标题描述、操作按钮 | `(0,0)`、`(0,2)` |
| `de_checkall`、`de_checksingle` | 明细行全选、明细行选中 | `(1,0)`、`(3,0)` |
| `de_serialtitle`、`de_serialnum` | 序号列头、行序号 | `(1,1)`、`(3,1)` |

`fieldTitlePosition` 默认 `(1,2)`，`fieldRepeatPosition` 默认 `(3,2)`。它们与上表共享同一明细子网格，坐标不能相撞。移动表头或表尾后，再按实际位置设置 `grid.detail.cells` 的颜色、边框等；设置固定列宽时，`columnWidthsPx` 数量要覆盖最右侧坐标。若要移动整个明细表区域，应修改**主网格**中的区域位置与跨列范围，而非只改这张子网格。

基础新建会把分组名称和明细表区域放在内容列，并跨过中间的字段列。手工修改完整布局时，也应为它们保留足够宽度；放进窄留白列会使预览文字和组件挤成竖排。

#### 预览被压成一列时

如果主表字段、分组名称或明细表在预览中挤成一条窄列，先检查**主网格列宽、组件所在列和跨列范围**，不能只增大明细表内部的字段宽度。双列主表建议用 `columnWidthsPercent` 为六列一次设置完整的百分比宽度，顺序是左留白、第一组标题、第一组字段、第二组标题、第二组字段、右留白，总和为 100。例如 `[4, 12, 34, 12, 34, 4]`。不要把整张主表或明细表区域放在只有 4% 宽度的留白列，也不要将预期的百分比数值按固定 px 列宽写入。

明细表有两层宽度：主网格中，**明细表区域**放在内容列并横跨各组标题、字段列；明细子网格中，再用 `detailTable.columnWidthsPx` 或 `grid.detail.columns` 设置表头和字段列的固定 px 宽度。分组名称同样要在主网格中跨过内容列。基础新建会完成区域放置和跨列；使用现有底稿或完整布局配置时，需同时核对组件坐标、`spans`、主网格列宽与明细子网格列宽。修改后用不落库的应用预览检查：标题和输入区应横向排列，分组及明细区域应占据内容宽度，文字不应逐字竖排。

### 网格与单元格

`grid` 分为 `main`（主表网格）和 `detail`（已有明细表的子网格）：

| 配置 | 作用 |
| --- | --- |
| `rowHeights` | 按从 0 开始的行号设置行高，单位 px |
| `columns` | 按列号设置 `fixed` 固定宽度（px）或 `percent` 百分比宽度；全百分比列宽之和须为 100 |
| `cells` | 按行列坐标设置静态文字或已支持的系统参数、字体、颜色、对齐、换行及四侧边框 |
| `merge`、`split` | 合并连续单元格；按合并区域左上角坐标拆分 |

`cells` 的可用设置如下，均针对模板中的指定单元格：

| 用途 | 配置 |
| --- | --- |
| 文字与参数 | `text` 写静态文字；`systemParameter: "formTitle"` 插入表单标题参数；两者不能同时写 |
| 字体 | `fontFamily`、`fontSizePx`、`bold`、`italic`，或单独使用完整的 `font` 值；`underline` 控制下划线 |
| 颜色与对齐 | `textColor`、`backgroundColor`、`horizontalAlign`（`left/center/right`）、`verticalAlign`（`top/middle/bottom`） |
| 文字排版 | `wordWrap` 控制自动换行；`textIndent` 设置单元格文字缩进量，填写非负整数。它是网格样式值，不写 `px` 后缀 |
| 四侧边框 | `borders.top/right/bottom/left` 分别指定颜色和线型；支持 `thin`、`medium`、`thick`、`dashed`、`dotted`、`double`，用 `none` 清除该侧边框 |

字体、字号等独立项只修改指定部分；完整 `font` 值与这些独立项不能同时写。颜色可用 `#RGB`、`#RRGGBB` 或 `#RRGGBBAA`。只能向**没有字段组件**的单元格写静态文字或系统参数。合并范围不能覆盖字段组件、重复标记或非左上角文字；拆分按现有合并区域的左上角定位，不能拆分包含组件的区域。修改单元格样式始终保留原有的字段组件关联。完整示例见[网格配置示例](../../../assets/form-template/style-templates-advanced-grid-example.json)。

为标题和字段内容留出相同的左侧空隙时，在主表重复行的四个占位单元格分别写 `style.textIndent`。[基础双列完整模板](../../../assets/form-template/style-templates-advanced-base-example.json)的 `layoutInfo.pageLayouts[0].config.workbook.Sheet1.cells` 中，第 4 行的第 1、2、3、4 列均设为 `2`，依次对应标题 1、字段 1、标题 2、字段 2。修改完整配置时，找到这四个单元格各自的 `style`，按所需缩进量调整 `textIndent`；不要把属性写到 `cellType` 中，也不要删掉 `cellType.comId`。重复行内的样式会随字段对迭代。分组名称也可另设缩进；行列坐标取决于模板结构，调整分组或字段排布后，应按实际网格重新定位。

## 二、组件设置

组件设置作用于选中的一个具体组件，例如某个字段占位组件或明细表组件。它与“所有普通字段”的通用布局样式不同。当前 CLI 尚未提供针对组件属性的专用配置项；完整布局配置及 `layout update` 的 `edits` 可以修改已有组件属性，修改时须保持组件与所在单元格、字段占位符及明细区域的关联。

## 三、CSS 源码

需要设置主题色、区域外观、组件状态或高亮时，可给自定义模板写入 CSS 文件：

```powershell
e10-cli form-engine layout-template advanced css show <模板ID>
e10-cli form-engine layout-template advanced css update <模板ID> --file template.css
```

CSS 文件写**源码**，例如 `.ebpage { --primary: #5d9cec; }`。CLI 会为当前模板生成带页面作用域的编译样式，保存后回读源码与编译结果；复制模板时会按新模板重新生成作用域。`css show` 可核对两者。行列宽度、单元格合并和重复区域仍由模板设置保存；CSS 负责这些结构之上的视觉效果。选择器应尽量限定在模板页面内，保存后检查应用预览及实际表单显示。

主题变量、明细表隔行／悬停样式和特定浏览组件选择器的写法见[表格式高级模板 CSS 编写指南](style-templates-advanced-css-guide.md)。

## 四、布局样式

布局样式分为**布局**和**字段**两类，作为模板设置与 CSS 之后的补充。只读方式等设计器行为属性需要在这里设置，CSS 只能改变显示效果，不能替代这些属性。下表按设计器中的设置范围列出当前已确认的 CLI 配置；未列为可配置的项目不要猜测参数。

### 布局

| 设置组 | 当前可配置内容 | `layoutStyle` 中的位置 |
| --- | --- | --- |
| 排版 | 只读方式、只读占位提示与背景、当前环境的样式 ID | `page.readOnlyType`、`page.showReadOnlyPlaceholder`、`page.showReadOnlyBackground`、`page.tabStyleConfigId` |
| 主题区域 | 页面外层的背景色、四侧边框、整体及四角圆角 | `page.outer` |
| 布局区域 | 表单内容区的背景色、四侧边框、整体及四角圆角 | `page.form` |
| 间距 | 上、右、下、左的外边距与内边距 | `page.spacing` |

边框可按 `all`、`top`、`right`、`bottom`、`left` 指定，线型为 `none`、`solid`、`dashed` 或 `dotted`。颜色使用 `#RRGGBB`、`#RRGGBBAA`，边框还可使用 `transparent`。长度使用整数 px。`tabStyleConfigId` 必须来自当前环境，不要复制其他环境的 ID。参考[页面布局配置示例](../../../assets/form-template/style-templates-advanced-page-example.json)。

### 字段

| 选项卡与对象 | 设置组 | 当前可配置内容及位置 |
| --- | --- | --- |
| 字段：所有普通字段 | 内容、间距 | 内容右间距、边框、圆角、四侧内边距及字段下间距：`field.contentRightMarginPx`、`field.content`、`field.spacingBottomPx` |
| 字段：所有普通字段 | 文本框、浏览框 | 宽度或最小宽度、背景色、无可见边框：`field.input`、`field.browser` |
| 明细表：明细表 | 间距 | 明细表四侧内边距：`detailTable` |
| 明细表：明细表内全部字段 | 内容、文本框、浏览框、间距 | 内容边框及右内边距、输入与浏览区域背景和边框、字段间距：`detailFields` |
| 分组：分组 | 标题、分组图标、内容、组件区域、间距 | 标题字重／背景／边线／间距、图标、分组背景与圆角、内容和组内间距：`group` |

面板中其余设置组仍需补充 CLI 能力：

| 对象 | 尚未接入的设置组 |
| --- | --- |
| 所有普通字段 | 标题的换行设置、描述、提示语、选项、图片、组件区域 |
| 明细表 | 描述、合计、表头 |
| 明细表内全部字段 | 提示语、选项、图片、组件区域；内容、文本框、浏览框和间距中未在上表列出的细项 |
| 明细表卡片视图 | 卡片标题、卡片主题、卡片背景、卡片序号、卡片标签 |
| 分组 | 折叠图标、描述；标题、内容、组件区域和间距中未在上表列出的细项 |
| 分组内全部字段 | 描述、内容、提示语、文本框、浏览框、选项、图片、组件区域、间距 |

分组样式只在模板包含分组区域时显示，明细样式同理。

文本框、浏览框及明细字段内容的边框目前只支持 `"none"`；分组标题边线目前为实线。`group.content` 的外边距可用负整数。参考[普通字段与分组示例](../../../assets/form-template/style-templates-advanced-standard-example.json)。

## 五、创建模板时的效果与配置落点

先确定效果是随**占位单元格**重复、作用于**整类字段或区域**，还是只在**目标表单的业务字段**上成立。按下表配置，预览时分别检查主表、分组和明细表。

| 需要呈现的效果 | 配置落点与注意事项 |
| --- | --- |
| 页面底色、内容区域背景与留白 | 页面主题色可写在 `cssSource` 的 `.ebpage`；网格内的底色用 `grid.main.cells`。需要设计器的页面区域配置时，外层用 `layoutStyle.page.outer`，内容区用 `layoutStyle.page.form`，留白用 `layoutStyle.page.spacing`。不要逐个字段填充页面背景。 |
| 各区域之间的间隙与底色 | 间隙显示其所在容器的背景色。连续白色底板应让页面及内容区的背景保持白色；独立白色卡片之间需要灰色间隔时，让外层背景为灰色、卡片区域为白色。间距由 `layoutStyle.page.spacing`、`layoutStyle.group.spacing` 或相应网格行控制；只修改分组背景不会改变间隙颜色。 |
| 表单标题的文字、字号、对齐、下边线和左右位置 | 用 `headerTitle: "formTitle"` 放置标题；`headerTitlePlacement` 决定跨列范围；标题单元格的字体、对齐和边框写入 `grid.main.cells`，并核对对应的 `spans`。 |
| 每行字段对数、标题列宽、内容列宽和行高 | 用 `fieldRows` 或 `fieldPlacements` 安排 1–4 组标题与字段；用 `columnWidthsPercent`、`grid.main.columns` 和 `grid.main.rowHeights` 设置尺寸。列宽合计须为 100%，跨列时保持组件与单元格关联一致。 |
| 标题格与内容格的底色、文字、缩进和分隔线 | 对主表重复区域内的标题及字段单元格分别设置 `grid.main.cells`；样式会随占位符迭代。需要表格线时保留单元格边框，并让输入控件本身透明、无边框。 |
| 分组标题装饰、卡片背景和组内间距 | 先启用 `group` 并放置成对标记；分组名称所在单元格用 `grid.main.cells`，卡片与特殊装饰可用 `cssSource`。需要设计器的通用分组属性时再用 `layoutStyle.group`。 |
| 明细表表头、字段标题对齐、列宽和内外边框 | 先启用 `detailTable`；明细子网格用 `grid.detail` 设置表头单元格、行列和边框。横向迭代出的列也要有分隔线时，可用明细表选择器补 CSS；滚动时还要检查固定表头。 |
| 主题色、选中态、隔行色、悬停和聚焦高亮 | 写在 `cssSource` 或 `--css-file` 中；主题变量作用于可读取它们的组件，明细行状态用限定在明细表内的选择器。不要把临时生成的组件 ID 写入通用模板。 |
| 输入框、浏览框、附件、图片和选项控件的外观 | 控件外观与状态可用 `cssSource` 的字段类型选择器；需要设计器通用输入或浏览属性时再用 `layoutStyle.field`、`layoutStyle.detailFields`。保留上传区域、单复选标记和日期图标等操作提示。 |
| 单据编号、签章栏、状态标签等特定业务内容 | 先在目标表单建立对应字段和业务状态，再应用模板并调整该表单的组件或布局；通用模板只定义可重复的占位结构与外观。 |

可先从[基础双列完整模板](../../../assets/form-template/style-templates-advanced-base-example.json)修改结构，再按需参考[表格式高级模板 CSS 编写指南](style-templates-advanced-css-guide.md)补充状态与组件选择器。

## 六、操作步骤

### 查看模板

```powershell
e10-cli form-engine layout-template advanced list
e10-cli form-engine layout-template advanced get <模板ID>
e10-cli form-engine layout-template advanced style show <模板ID>
e10-cli form-engine layout-template advanced grid show <模板ID>
```

先确认模板是 PC 表格式、是否为自定义模板，以及目标结构中是否含分组或明细表。修改网格前先用 `grid show` 确认行列坐标。

### 新建模板

```powershell
e10-cli form-engine layout-template advanced scaffold --out advanced-design.json
e10-cli form-engine layout-template advanced create --config @advanced-design.json
```

有三种配置方式，均通过 `advanced create --config @文件` 创建：

1. **从基础结构设计**：`templateName` 必填，其余结构与样式均可选。配置项见下表。[逐行排列样例](../../../assets/form-template/style-templates-advanced-structure-example.json)与[独立定位样例](../../../assets/form-template/style-templates-advanced-placements-example.json)演示不同排列方法；它们主要说明结构，没有单独的主题样式。
2. **参考完整配置设计**：先看[基础双列完整模板](../../../assets/form-template/style-templates-advanced-base-example.json)，再按需参考下列表格版、淡蓝水晶和公文样式。它们均列出完整的 `layoutInfo` 和 `cssSource`；修改名称、网格、组件及样式后创建，无需引用已有模板 ID。
3. **编辑已有模板的完整配置**：执行 `e10-cli form-engine layout-template advanced export <模板ID> --out advanced-full.json`，在导出文件的 `layoutInfo` 中修改结构和已知属性，再执行 `advanced create --config @advanced-full.json`。修改 `templateName` 以创建新模板；也可叠加 `layoutStyle`、`grid` 和 `edits`。

| 完整配置示例 | 适合的布局与外观 |
| --- | --- |
| [基础双列完整模板](../../../assets/form-template/style-templates-advanced-base-example.json) | 居中表单标题、两组主表标题与字段、分组、明细表及明细字段标题和横向迭代；统一蓝色基础样式。建议从此文件开始修改。 |
| [表格版](../../../assets/form-template/style-templates-advanced-table-example.json) | 双列主表，含分组和明细表；蓝色主题变量，分组左边线及多处强调色。适合同时需要分组和明细的表单。 |
| [淡蓝水晶](../../../assets/form-template/style-templates-advanced-blue-crystal-example.json) | 双列主表和明细表，无分组；浅蓝标题区域、蓝色强调色。适合简洁的业务录入表单。 |
| [公文样式](../../../assets/form-template/style-templates-advanced-document-example.json) | 双列主表和明细表，无分组；红色强调色、较多顶部留白。适合正式文书式表单。 |

表中的四个示例均可作为完整创建配置：`pageLayouts[0].comps` 记录占位组件，`config.workbook.Sheet1` 及其子网格记录行列、合并与单元格样式，`marks` 记录主表、分组和明细表的迭代范围，`formStyle.styleConfig` 记录通用布局样式，`cssSource` 记录页面 CSS。完整配置省去创建人和时间等记录信息，将新布局页 ID 设为 `-1`，并将 `styleConfig` 展开为对象以便阅读和修改；创建时 CLI 会将样式对象转换为模板所需的格式。调整组件位置时，应同步维护网格中的组件关联和对应标记；无需改变的内部组件 ID 保持原样。

使用基础双列样例时，先改 `templateName`；需要调整主表列宽，修改 `Sheet1.columns` 的六个百分比，保持总和为 100；需要调整行高或表头样式，修改 `Sheet1.rows`、对应 `cells` 和 `spans`。表单标题位于第 0 行第 1 列，横跨第 1–4 列；第 0、5 列作为左右边距，标题组件的 `config.excel.col`、对应单元格的 `col` 和合并区域的 `col/colCount` 要保持一致。标题行高为 52，紧随其后的分组开始标记行高为 1；标记仍保留在网格中，但不再撑出明显空隙。两组主表标题与字段分别占第 4 行的第 1–2 列、第 3–4 列（坐标从 0 起）；第 1–7 行包含分组和主表重复区域，第 9–12 行包含明细重复区域。明细字段标题和横向迭代位于以 `DetailTable` 组件 ID 命名的子网格。通用输入框、浏览框和分组标题样式在 `formStyle.styleConfig`；`cssSource` 设置主题变量，以及明细表头、首行、隔行、悬停和输入聚焦的高亮。可直接编辑[样例 CSS](../../../assets/form-template/style-templates-advanced-base.css)，再通过 `css update` 写入已有模板。不需要分组或明细时，应成组移除其组件、标记、对应网格行及子网格；仅隐藏文字不能移除迭代结构。

创建或改造模板时，按以下顺序核对：

1. **结构**：主表重复标记成对，标题和字段同号且位于其中；需要分组、明细表时再保留各自成对的标记和区域。不要通过改颜色来修复组件位置。
2. **宽度**：先确认主网格列宽总和与字段所占列；分组名称和明细表区域应跨过内容列，明细子网格列宽另行设置。预览出现竖排时先查区域位置、跨列和单位。
3. **外观**：先在模板网格中确定具体单元格的字体、颜色、边框，再用 `cssSource` 设置页面主题、组件状态和高亮；仍需设计器通用属性时才改 `formStyle.styleConfig` 或写 `layoutStyle`。`grid` 和 `layoutStyle` 可作为完整配置上的局部覆盖。
4. **检查**：保存后回读模板，并用不落库的应用预览检查标题、字段、分组和明细表的实际排列；再在目标表单中核对实际效果。

表中的四个示例采用六列双字段对结构：左右留白各 4%，两组标题列各 10%，两组内容列各 36%。改成其他排列时，按实际字段位置重算全部列的百分比。基础样例与表格版含分组和明细表，淡蓝水晶和公文样式含明细表但无分组。模板按占位符迭代字段，不能按字段名称让某些字段自动跨整行；这类专属位置须在应用到实际表单后调整。

新建时可在命令后追加 `--css-file template.css`；配置文件也可写 `cssSource` 字符串。若要直接沿用环境中已有模板，可用 `advanced copy <模板ID> --name <新名称>`，或在配置中填写 `sourceTemplateId` 再叠加局部设置。复制后如只需替换 CSS，可用上面的 `css update` 命令。

`edits` 用于修改尚未封装成专用配置项的布局属性。路径从 `layoutInfo` 根开始，采用 JSON Pointer；`set` 写入 `value`，`remove` 删除对象属性。数组中只能修改已有位置，不能删除数组项。修改组件或重复标记时，应保持占位符、单元格关联及成对标记一致。例如：

```json
{
  "templateName": "绿色模板副本",
  "sourceTemplateId": "原模板ID",
  "edits": [{ "op": "set", "path": "/pageLayouts/0/config/workbook/Sheet1/rows/3/size", "value": 56 }],
  "grid": { "main": { "cells": [{ "row": 3, "col": 1, "backgroundColor": "#EAF5EE" }] } }
}
```

行列与单元格先用模板的 `grid`，页面和组件视觉效果优先用 CSS；确实需要设计器通用配置时才用 `layoutStyle`。局部更新会保留未指定的属性，并在保存后核对。`edits` 和完整 `layoutInfo` 适合设计器中已存在但 CLI 尚未提供专用配置的属性。

从基础结构新建时可填写以下项目；省略分组或明细表时不会在模板中生成该区域：

| 配置项 | 作用 |
| --- | --- |
| `templateName` | 模板名称，必填 |
| `fieldPairsPerRow` | 简单结构：每行一组或两组标题与字段，默认一组；与 `fieldRows`、`fieldPlacements` 三选一 |
| `fieldRows` | 自定义一次重复单元中的行序列，字段对编号取 1–4，各用一次且不跳号；例如 `[[1], [2, 3], [4]]` |
| `fieldPlacements` | 每组分别设置 `pair`、`title`、`field`；后二者用相对行号 `row`、绝对列号 `col`、可选 `colSpan` 设置位置与跨列 |
| `headerTitle: "formTitle"` | 顶部插入表单标题参数，可通过 `grid.main.cells` 设置字号和对齐 |
| `headerTitlePlacement` | `full`（默认）使标题横跨全部主网格列；`content` 使标题从第 1 列开始、在末列之前结束，与字段区域对齐并留出左右单元格边距。仅在设置 `headerTitle` 时使用 |
| `sectionTitle` | 一行最多放两组及以上字段时的静态分区标题 |
| `columnWidthsPercent` | 使用 `fieldRows` 时，一行最多放一至四组分别提供 4、6、8、10 列百分比；`fieldPlacements` 时按实际主网格列数完整提供；各项合计 100，传统双列也可使用六列设置 |
| `rowHeight`、`titleWidthPx`、`fieldWidthPx` | 基础行高及单组字段的固定列宽，单位 px |
| `group: {"enabled": true}` | 生成分组开始、分组名称、分组结束；通用外观用 `layoutStyle.group` 设置 |
| `detailTable` | `enabled: true` 生成明细表区域及子网格；可选 `title`、`rowHeightPx`、3–20 个像素值的 `columnWidthsPx`、`fieldRepeatDirection`（`horizontal`/`vertical`）、`fieldTitlePosition`、`fieldRepeatPosition`、`controlPositions`；通用外观用 `layoutStyle.detailTable`、`layoutStyle.detailFields` 设置 |
| `layoutStyle` | 页面、字段、分组及明细字段的通用样式，见本篇“布局样式” |
| `grid` | 主表网格 `main`；启用明细表后还可设置明细子网格 `detail` |
| `coverFileId` | 已上传的封面文件 ID |
| `cssSource` | 可选 CSS 源码文字；命令行也可用 `--css-file` 读取文件 |

启用分组后，主表字段单元格的行号会后移；设置 `grid.main.cells` 前可先看上述示例中的坐标。完整布局和现有模板底稿方式也支持这些区域；其已有结构不由 `group`、`detailTable` 开关重新生成。
默认明细子网格的第 0 行放标题描述和按钮，第 1 行放全选、序号与明细字段标题，第 3 行放字段迭代。设置字段标题颜色时使用 `grid.detail.cells` 的第 1 行；自定义位置后按新的坐标设置。可选位置配置示例见[交替字段与明细位置](../../../assets/form-template/style-templates-advanced-structure-example.json)。

### 修改已有自定义模板

先把结构、行列与单元格改动写入 `grid-style.json` 或 `layout-edits.json`；页面和组件的外观写入 CSS。只有需要设计器通用配置时，才把相应属性写入 `layout-style.json`：

```powershell
e10-cli form-engine layout-template advanced grid update <模板ID> --config @grid-style.json
e10-cli form-engine layout-template advanced layout update <模板ID> --config @layout-edits.json
e10-cli form-engine layout-template advanced css update <模板ID> --file template.css
e10-cli form-engine layout-template advanced style update <模板ID> --config @layout-style.json
```

`layout update` 使用上文的 `edits` 路径配置来调整已有自定义模板的结构属性；修改组件位置时，要同步修改单元格坐标和对应合并区域。保存后命令会回读改动并生成应用预览。

例如，`grid-style.json` 可只修改一行、一列和一个单元格：

```json
{
  "main": {
    "rowHeights": [{ "row": 3, "px": 50 }],
    "columns": [{ "col": 0, "unit": "fixed", "value": 160 }],
    "cells": [{
      "row": 3,
      "col": 0,
      "backgroundColor": "#FFF6F6",
      "font": "700 16px Arial",
      "borders": { "top": { "color": "#ff666a", "line": "thick" } }
    }]
  }
}
```

更新命令只修改写出的设置，保留其他设置与组件关联；系统模板不可编辑。新建和更新都会保存后回读，并生成一次**不落库**的应用预览。输出中的 `id` 是已保存的模板 ID，`preview.persisted=false` 仅表示预览未保存。要将模板用于实际表单，按[总览中的应用步骤](style-templates.md)操作。

需要拆分已有合并区域时，在网格配置中写入 `"split":[{"row":8,"col":0}]`，坐标是该合并区域的左上角。`merge` 则写入 `row`、`col`、`rowCount`、`colCount`；两者都可以与 `cells`、`rowHeights`、`columns` 一起提交。

### 启用、禁用与删除

```bash
e10-cli form-engine layout-template advanced enable <模板ID> [更多模板ID...]
e10-cli form-engine layout-template advanced disable <模板ID> [更多模板ID...]
e10-cli form-engine layout-template advanced delete <模板ID> [更多模板ID...]
```

这三项仅操作自定义高级 PC 模板；CLI 会先核对全部 ID，阻止系统模板参与批量操作。启用和禁用后回读每个模板的状态；删除前检查可删除性，删除后回读列表确认目标已消失。禁用保留模板配置，删除会移除模板；已有表单布局不会因为模板被禁用或删除而自动重建。

## 当前能力边界

- 本篇 CLI 命令仅适用于高级 **PC 表格式**模板；移动模板需要单独设计。
- 基础新建支持 1–4 组主表字段逐行排列，或对每个标题、字段分别设置位置和跨列；明细子网格支持已列出的控件位置。跨行合并、展开行等尚无已验证的专用配置项，可通过现有模板底稿、完整 `layoutInfo` 或 `layout update` 的 `edits` 保留或调整；这些方式不会自动修复错误的组件关联。CSS 源码可单独写入，但具体组件属性、背景图片／渐变、阴影、隐藏行列仍没有已验证的专用配置项。系统参数当前只确认 `formTitle`，其他参数需逐项确认。
- 图片或 Excel 还原出的真实表单布局不能整份当作模板；源样式处理见[图片和 Excel 源样式还原](../guide-form-layout-source.md)。
