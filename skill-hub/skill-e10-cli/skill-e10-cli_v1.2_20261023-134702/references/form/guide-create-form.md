# 新建 Ebuilder 表单

通过 `e10-cli form create` 创建表单。

> **重要**：字段定义一次性写全（含选项、默认值等）。不要先建空表再逐个 `add-field` —— add-field 只用于罕见补救。

## 基本用法

```bash
e10-cli form create {应用ID} "表单名" --fields @fields.json
# 建表后自动加「台账菜单」（VIEWPORT，指向数据列表页）；加 --no-menu 可跳过
```

不传 `--fields` 时使用默认字段：名称(Text)、数量(Number)、日期(Date)、状态(Select)。

### 布局类型（流式/表格式）

```bash
e10-cli form create {应用ID} "表单名" --fields @fields.json --layout FLOW   # 流式
e10-cli form create {应用ID} "表单名" --fields @fields.json --layout EXCEL  # 表格（缺省）
```

| 要点 | 说明 |
|------|------|
| **布局类型建表时定死** | 平台建表后不可切换（流式↔表格式），只能创建时选。`--layout` 写在建表请求里（`layoutType` + `isAdvance:false`） |
| **流式模板** | FLOW 用特殊模板 `820000000000000001`（非通用版本 id，跨环境一致）；CLI 自动配 |
| 缺省 | 不传 `--layout` 时缺省 `EXCEL`（表格，行为不变） |

## 自定义字段

```bash
e10-cli form create {应用ID} "表单名" --fields @fields.json
```

字段 JSON 格式（保存在 `fields.json` 中）：

```json
[
  {"componentKey": "Text", "fieldName": "客户名称"},
  {"componentKey": "Phone", "fieldName": "联系电话"},
  {"componentKey": "Employee", "fieldName": "负责人"},
  {"componentKey": "Department", "fieldName": "所属部门"},
  {"componentKey": "Date", "fieldName": "签订日期"},
  {"componentKey": "Money", "fieldName": "合同金额"},
  {"componentKey": "Select", "fieldName": "客户等级", "fieldOptions": [{"name":"A级"},{"name":"B级"}]}
]
```

> **明细表（DetailTable）放最下面**：主表字段在前、明细表放数组末尾。布局/铺列按数组顺序处理，明细在前会打乱主表字段排布。
> ```json
> [
>   {"componentKey":"Text","fieldName":"合同名称"},
>   {"componentKey":"Money","fieldName":"合同金额"},
>   {"componentKey":"DetailTable","fieldName":"付款明细","formFields":[
>     {"componentKey":"Text","fieldName":"付款条件"},
>     {"componentKey":"Number","fieldName":"付款金额","precision":2}
>   ]}
> ]
> ```

> **`valueKey` 可选**：Select/RadioBox/CheckBox 的 `fieldOptions` 只需写 `name`，`valueKey` 由 CLI 自动生成。也可以手动指定短码如 `"valueKey":"a"`。

**字段读写属性**：`required` 必填 / `readOnly` 只读 / `hidden` 隐藏（字段不展示但保留参与计算，如运算/派生字段）：
```json
{"componentKey":"Number","fieldName":"请假时长(小时)","readOnly":true,"hidden":true},
{"componentKey":"FileComponent","fieldName":"证明材料","required":true}
```
> `hidden:true` → 布局属性"显示"取消（show:false）；`readOnly` → 布局"禁止手工编辑"；`required` → 布局"必填"。这些是**布局属性**（优先级：字段在布局中的设置 > 字段管理中字段设置 > 模块默认），建表时一次配好，勿依赖平台默认值。

**Number/Money 精度**：用 `precision` 指定小数位数（缺省 Number=0 整数、Money=2）：
```json
{"componentKey":"Number","fieldName":"单价","precision":2},
{"componentKey":"Money","fieldName":"金额"}
```
> 不设 precision 时 Number 建出来是整数（pointSize=0）、Money 是 2 位小数。主表/明细子字段都支持。

**Number 百分比显示**：`"percent":true` → `numberType=percentage`（缺省 pointSize=1，可再配 `precision`）：
```json
{"componentKey":"Number","fieldName":"付款比例","percent":true,"precision":1}
```
> ⚠️ **百分比字段的公式要 ×100**：平台百分比字段是「数值直接拼 %」（不自动 ×100）。如 付款比例=付款金额/项目金额，10000/20000=0.5，会显示「**0.5%**」而非 50%。公式必须 ×100：
> ```json
> {"componentKey":"Number","fieldName":"付款比例","percent":true,"precision":1,"formula":"{付款信息.付款金额}/{主表.项目金额}*100"}
> ```
> 这样 0.5×100=50 → 显示「50%」。累加校验「比例累加=100%」也基于百分比数（50+50=100），不是比值。

**Number/Money 默认值**：`"defaultValue":1000` → 存 `content` + `isDefault:true`（如 工时单价默认 1000 元）：
```json
{"componentKey":"Number","fieldName":"工时单价","defaultValue":1000}
```
> 平台机制：设默认值必须连 `isDelimiter/stepMode/step/isCapital` 一起发，否则默认值不落库（CLI 已处理）。
> 单位没有独立字段属性 —— 显示单位直接写在字段名里，如 `"fieldName":"工时数量（天）"`。
> **台账列单位显示**（绕法）：平台字段无单位属性，但台账列可配显示后缀，用 `form list-unit <objId> <appId> <listId> <fieldId> "（元）"` 设置（走列表列配置 `showTrans.ruleConfig.suffix`，极简结构平台即接受）。

## 支持的字段类型

| componentKey | 说明 |
|---|---|
| Text | 文本 |
| TextArea | 多行文本 |
| Number | 数字 |
| Money | 金额 |
| Date | 日期 |
| Employee | 人员选择 |
| Department | 部门选择 |
| FileComponent | 附件上传（**注意是 FileComponent 不是 File**） |
| Select | 下拉选择 |
| RadioBox | 单选按钮 |
| CheckBox | 多选按钮 |
| EInvoice | 电子发票（创建后无需额外配置，平台自动处理） |
| AudioRecord | 语音（极简字段，无特殊配置。注意不是 FileComponent 附件） |
| VideoRecord | 视频（极简字段，无特殊配置） |
| DetailTable | 明细表 |
| DateRange | 日期区间 |
| Time | 时间 |
| EBuilder | 关联 EB 表单（见下节） |
| Flow | **浏览-流程**（关联流程，如"数据来源"来自项目立项流程；`--sform-id` 为目标流程绑定的表单 objId，点击自动跳流程） |

正常情况下，人相关的 都是用Employee
Time 的格式固定为 HH:mm:ss 如 17:00:00

## EBuilder 关联字段

关联其他表单记录（下拉选择/搜索），选中后展示目标表单的某个字段值。

```json
{
  "componentKey": "EBuilder",
  "fieldName": "关联客户",
  "sformId": "1296220571782152199",
  "dataTitle": "客户名称"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `sformId` | 是 | **目标表单的 objId**（不是 appId/formId） |
| `dataTitle` | 是 | 目标表单中用于显示的字段名，选中记录后展示该字段值。传 `"name"` 表示取目标表单首个文本字段 |

### EBuilder + 值带出（relateFrom）

选关联记录后自动带出其他字段值（如选客户→带出联系人/地址）：

```json
{
  "componentKey": "Text",
  "fieldName": "联系人",
  "relateFrom": { "ebuilderField": "关联客户", "sourceFieldId": "1296220571782152194" }
}
```

- `ebuilderField`：本表单中的 EBuilder 字段名
- `sourceFieldId`：目标表单中要复制值的字段 **fieldId（数字 ID）**。⚠️ **不能传字段名**，用 `form read --app-id` 获取

创建后补配值带出：`e10-cli form edit-field ... --relate-from <EBuilder字段名> --relate-from-source <源字段fieldId>`
> ⚠️ `--relate-from-source` 必须传字段的**数字 fieldId**，不能传字段名。

## Select/RadioBox/CheckBox 带选项

```json
{
  "componentKey": "Select",
  "fieldName": "客户等级",
  "fieldOptions": [
    {"name": "A级"},
    {"name": "B级"},
    {"name": "C级"}
  ]
}
```

## 明细表 DetailTable

明细表包含嵌套子字段，子字段写在其 `formFields` 数组内：

```json
{
  "componentKey": "DetailTable",
  "fieldName": "订单明细",
  "formFields": [
    {"componentKey": "Text", "fieldName": "商品名称"},
    {"componentKey": "Number", "fieldName": "数量"},
    {"componentKey": "Number", "fieldName": "单价"},
    {"componentKey": "Date", "fieldName": "交付日期"}
  ]
}
```

子字段也支持带选项的类型。

## 复杂编号（年份编号）：serial-mark

年份编号（如 `XM-2026-001`）走**复杂编号**机制：在任意文本字段上配编码段（固定内容 + 年 + 流水号），`form serial-mark` 一条命令完成。

```bash
# 字段用普通 Text 建（项目编号），建表后配复杂编号：
e10-cli form serial-mark <objId> <appId> <字段ID> --prefix "XM-" --year --serial 3
# 生成 XM-2026-001（固定内容 XM- + 年份 2026 + 分隔符 - + 3位流水 001）
e10-cli form serial-mark <objId> <appId> <字段ID> --prefix "KH-" --serial 4
# 无年份 → KH-0001
```

| 选项 | 说明 |
|------|------|
| `--prefix <text>` | 固定内容段（FIX_CONTEXT），如 `"XM-"` / `"KH-"`（含分隔符就写进前缀） |
| `--year` | 年份段（DATE_YEAR），生成当前年份如 2026 |
| `--serial <n>` | 流水号位数（SERIAL_NUMBER），如 4 → 0001（seqAlone=1 补零） |
| `--sep <text>` | 年→流水之间独立分隔符段（默认 `"-"`），如 `HTMC-2026-0001` 的中间 `-` |
| `--clear` | 解除该字段的编号绑定 |

**注意**：
- 被编码字段平台自动设为只读（编号自动生成，不可手工改）
- 段顺序：前缀 → 年份 → 分隔符 → 流水（position 控制，CLI 已排好）
- 流水号按 `前缀+年份+流水` 组合查重累进
- 机制：markField 复杂编号（getEbMarkTargetId → getMarkSetForm → saveSingleMarkDef → saveOrUpdate → saveMarkField），markDefId 必须用 saveSingleMarkDef 返回的

## 日期区间 DateRange

日期区间字段**必须**指定精度格式，通过 `format` 配置：

```json
{
  "componentKey": "DateRange",
  "fieldName": "出差时间",
  "format": "yyyy-MM-dd HH:mm"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `format` | 否 | 区间精度。缺省 `yyyy-MM-dd`（年-月-日）；到分钟写 `yyyy-MM-dd HH:mm`；到秒 `yyyy-MM-dd HH:mm:ss` |
| `startPlaceholder` / `endPlaceholder` | 否 | 开始/结束控件占位符。缺省按 format 自动生成中文（如 `年-月-日 时:分`） |

> **CLI 自动展开**：创建时无需手写 `start`/`end`/`rangeInterval`——CLI 会把该字段展开为平台要求的 3 字段结构（主字段 + 「(开始时间)」「(结束时间)」两个 DateComponent，各带独立 fieldId），这是之前报 `DateIntervalFieldDto.getEnd()==null` 的根因（缺了 end 组件）。
>
> **事后补加**：`e10-cli form add-field <objId> <appId> "回程时间" DateRange --format "yyyy-MM-dd HH:mm"`

## 字段公式（fields.json 的 formula 属性）

创建表单时直接给字段绑定计算公式，CLI 自动完成「创建公式 + 绑定字段」两步（字段配置会带上 `ffExpress`）：

```json
{
  "componentKey": "Number",
  "fieldName": "出差天数",
  "formula": "DAYS({主表.出差时间(开始时间)},{主表.出差时间(结束时间)})"
}
```

或对象形式指定返回类型：

```json
"formula": { "expression": "DAYS({主表.出差时间(开始时间)},{主表.出差时间(结束时间)})", "returnType": "Number" }
```

| 要点 | 说明 |
|------|------|
| 表达式语法 | 与 `form formula set --expression` 一致，用 `{主表.字段名}` 引用主表字段、`{明细表名.字段名}` 引用**明细表**字段（如 `DAYS({行程明细.行程开始时间},{行程明细.行程结束时间})`）。**fields.json create 与 formula set 两条路径都支持明细引用** |
| **明细列求和** | **`SUM({明细表名.字段})`** 可对明细表某列跨行求和（如 `SUM({付款信息.付款金额})`），实测生效。可配合 `workflow node validate` 做"明细累加=主表字段"校验 |
| **日期差** | 两个日期相减**不直接支持**，要用平台函数 **`DAYS({主表.开始},{主表.结束})`** |
| 返回类型 | 缺省 `Number`；文本/日期类用对象形式指定 |
| 事后补加 | `e10-cli form formula set <objId> <appId> --expression "..." --target <fieldId>` |

> **明细表子字段选项**：`DetailTable` 的 `formFields` 里的 `Select/RadioBox/CheckBox` 也支持 `fieldOptions`，CLI 会自动给子字段配置选项（创建时无需额外操作）。

## 完整示例

```bash
e10-cli form create 1283840156707348480 "采购合同" --fields @fields.json
```

`fields.json` 内容：

```json
[
  {"componentKey":"Text","fieldName":"合同编号"},
  {"componentKey":"Text","fieldName":"供应商名称"},
  {"componentKey":"Employee","fieldName":"采购负责人"},
  {"componentKey":"Date","fieldName":"签订日期"},
  {"componentKey":"Money","fieldName":"总金额"},
  {"componentKey":"Select","fieldName":"合同状态","fieldOptions":[{"name":"待审批"},{"name":"已审批"},{"name":"已完成"}]},
  {"componentKey":"DetailTable","fieldName":"采购明细","formFields":[{"componentKey":"Text","fieldName":"物品名称"},{"componentKey":"Number","fieldName":"数量"},{"componentKey":"Number","fieldName":"单价"}]}
]
```

## 创建成功后

- 返回表单 ID
- 用 `e10-cli form read <objId> --app-id <appId> --out fields.json` 导出字段信息（机器可读 JSON）
- 在代码中通过 `formApi.js` 读写该表单数据
