# 字段联动（跨表带出赋值）指南

## 概述

本指南汇总字段值的带出与赋值：关联 EBuilder 字段直接带出、HRM 属性带出，以及跨表查询赋值（`FormDataLinkage`）。先按来源选择配置方式，再看对应命令。

其中 `FormDataLinkage` 可按触发字段值查询另一张表，把结果赋给本表主表或明细字段；背后由 ESB FieldLinkage 动作流执行，CLI 自动完成创建和绑定。支持两种方式：快捷配置（`--condition` / `--assign`，任意条件、多查询字段与多赋值）和旧单跳/多跳（`--source-form` / `--query-field` / `--hops`，固定按数据 ID 过滤）。

## 选择带出方式

| 需求 | 配置方式 | 命令或入口 |
|---|---|---|
| 关联 EBuilder 记录后直接复制该记录的一个字段 | 字段级 `ffRelateField` | 建表时 `relateFrom`；建表后 `form edit-field --relate-from` |
| 人员或部门字段变化后带出 HRM 属性 | 字段级 `ffRelateField` | `form relate` |
| 按条件查询另一张表，单跳或多跳赋值 | `FormDataLinkage`，由 ESB 动作流实现 | `form field-linkage`（快捷配置或旧单跳/多跳） |

这些都改变字段**值**。按条件改变隐藏、只读、必填等**显示属性**，使用 `form linkage`，见 [显示属性联动指南](guide-form-linkage.md)。

> 本文讲的是**跨表**带出。本表字段之间用公式互相计算赋值的是**函数联动**（eb 表 `form formula-linkage`、流程表单 `wf-form formula-linkage`），见 `guide-formula-linkage.md` —— 两者 `linkageType` 不同（`excel` vs `template`），`form field-linkage list/delete` 看不到也删不掉函数联动。

## 关联 EBuilder 字段直接带出（`ffRelateField`）

当 EBuilder 关联字段选中某条记录后，自动将该记录的一个字段值复制到当前字段。例如：选客户后带出联系人；选合同后带出合同金额。

### 建表时配置

`form create --fields` 里用 `relateFrom` 定义，CLI 在创建字段后配置 `ffRelateField`：

```json
{ "componentKey": "Text", "fieldName": "联系人",
  "relateFrom": { "ebuilderField": "关联客户", "sourceFieldId": "1296220571782152194" } }
```

### 建表后补配

```bash
e10-cli form edit-field <objId> <appId> <fieldId> \
  --relate-from <EBuilder字段名> \
  --relate-from-source <目标表单源字段fieldId>
```

`sourceFieldId` 和 `--relate-from-source` 必须是关联目标表单中源字段的数字 `fieldId`，不能写字段名。先用 `form read <目标表objId> --app-id <appId>` 查实际 ID。`--relate-from` 是本表单中的 EBuilder 关联字段名。

## HRM 属性带出（`form relate`）

本表单的人员或部门字段变化后，自动向目标字段填入 HRM 属性。源字段必须是 Employee 或 Department 类型。Employee 源的 `ffRelateField` 带 `module:"hrm"`，Department 源不带。

```bash
# 申请人（Employee）变化 → 向申请人工号填入邮箱
e10-cli form relate <appId> <objId> 申请人工号 --from 申请人 --key email

# 所属部门（Department）变化 → 向申请人工号填入部门编号
e10-cli form relate <appId> <objId> 申请人工号 --from 所属部门 --key code
```

| 参数 | 说明 |
|---|---|
| `<targetField>` | 被填充的目标字段，名称或 `fieldId` |
| `--from <field>` | 表单中的源字段，必须是 Employee 或 Department 类型 |
| `--key <key>` | 带出的 HRM 属性；默认 Employee=`department`、Department=`name`；不传 `--title` 时自动取属性中文名 |

`--key` 从平台 `listBusinessField` 清单校验。Employee 属性包括 `username` 姓名、`email` 邮箱、`superior` 上级、`mobile` 手机、`jobNum` 工号、`hiredate` 入职时间、`department` 部门、`position` 岗位、`grade` 职级、`allSuperiors` 所有上级等。Department 属性包括 `name` 部门名称、`code` 部门编号、`parent` 上级部门、`fullname` 部门全称、`department.coadjutant` 协办人、`deptEmployee` 部门人员。

目标字段类型与带出属性不匹配时，命令只提示警告、不阻止；例如 `deptEmployee` 通常应填入 Employee 字段。

## 跨表查询赋值（`FormDataLinkage`）

## CLI 命令

```bash
# 列出
e10-cli form field-linkage list <appId> <objId>

# 回读单条
e10-cli form field-linkage read <appId> <objId> <linkageId>

# 查源表可带出字段
e10-cli form field-linkage fields <appId> <formId>

# 可用触发动作
e10-cli form field-linkage events <appId> <objId> [--effect formLayout|workFlow|includeNode]

# 删除（批量）
e10-cli form field-linkage delete <appId> <objId> <linkageId...>
```

## 快捷配置（add）

```bash
e10-cli form field-linkage add <appId> <objId> \
  --trigger <本表触发字段名> \
  --source-form <查询目标表 objId> \
  --condition "源表字段:算子:值" \
  --query-fields "源表字段1,源表字段2" \
  --assign "源表查询字段=本表目标字段"
```

### 查询条件（`--condition`）

可重复，多个为「且」。写法 `源表字段:算子:值`，算子与动作流筛选共用同一套：

| 类别 | 算子 |
|---|---|
| 比较 | 等于 / 不等于 / 大于 / 大于等于 / 小于 / 小于等于 |
| 文本 | 包含 / 不包含 / 开头包含 / 开头不包含 / 结尾包含 / 结尾不包含 |
| 集合 | 属于 / 不属于 / 被包含于 |
| 无值 | 为空 / 不为空（可不写冒号和值） |
| 区间 | 区间（写 `起始~结束`） |

值写 `@本表字段名` 表示引用本表字段；否则按字面值。示例：

```bash
--condition "测试字段C:eq:11111"
--condition "测试字段C:等于:@测试字段A"
--condition "日期字段A:区间:2026-10-20~2026-10-21"
--condition "备注:不为空"
```

### 查询字段（`--query-fields`）

逗号分隔的源表字段名。不给时会自动并入 `--assign` 的源字段和明细依据字段。

### 赋值（`--assign`）

可重复，`源表查询字段=本表目标字段`：

- 主表字段直接写字段名
- 明细表字段写 `明细表名.字段名`

```bash
--assign "测试字段C=测试字段A"
--assign "测试字段C=明细表1.明细字段1"
```

### 明细行依据（`--basis`）

`明细表名=源表字段名`。决定写入明细表时按哪一列匹配/生成行。不给则取该明细表第一个赋值的源字段；当被赋值的源字段正好是依据值时，设计器里显示为「依据值本身」。

```bash
--basis "明细表1=测试字段C"
```

### 明细配置（三个开关）

| 参数 | 取值 | 对应设计器 |
|---|---|---|
| `--detail-mode` | `add`（默认）/ `cover` / `update` | 主表联动明细表时：添加明细 / 覆盖明细 / 更新明细 |
| `--detail-add` | `override`（默认）/ `append` | 明细表添加行时：删除已联动出的明细再添加 / 累计添加明细 |
| `--fission` | `on`（默认）/ `off` | 联动出的值继续触发联动 |

### 触发动作（`--event`）

可重复，写法同函数联动：事件名或 type，可带 `类型:字段,字段`。默认 `changeField`（值改变时），字段取 `--trigger`。

```bash
--event changeField
--event onLoadForm
--event "changeField:测试字段A"
```

表单级 / 流程级事件（载入时、创建数据时…）不需要触发字段。流程事件（提交/批准、转发、保存…）需要配合 `--effect workFlow|includeNode`。

### 生效维度（`--effect`）

`form`（默认，当前表单）/ `formLayout`（表单布局，可配 `--layout-id`）/ `workFlow`（当前工作流）/ `includeNode`（选择节点，配 `--workflow-id` 与 `--node`）。

### 启用状态（`--state`）

`on`（默认）/ `off`。

### 赋值前提（`--precondition`）

满足前提时才执行赋值。可重复，多个为「且」：

```bash
--precondition "rlytest:不为空"
--precondition "测试字段C:包含:@rlytest"     # @ 先查查询结果字段
--precondition "日期字段A:包含:@测试字段A"   # 查不到再按本表字段
```

前提条件保存在 ESB 条件服务里，开关它等价于重新保存动作流设计。

## 修改（update）

```bash
e10-cli form field-linkage update <appId> <objId> <linkageId> \
  [--name <名称>] [--state on|off] \
  [--event <事件...>] [--trigger <字段...>] [--effect <维度>] \
  [--detail-mode add|cover|update] [--detail-add override|append] [--fission on|off] \
  [--precondition <条件...>] [--clear-precondition]
```

- 不给 `--event` / `--trigger` 时原样沿用现有触发动作
- 只改启停时走专用接口，不重发整套联动报文
- 赋值前提不属于联动记录，由 CLI 读回动作流设计后只改 Output 节点再保存

## 旧单跳 / 多跳（兼容保留）

**单跳**：按「数据ID = 触发字段值」过滤。

```bash
e10-cli form field-linkage add <appId> <objId> \
  --trigger <触发字段名> \
  --source-form <目标表objId> \
  --query-field <目标表带出字段名> \
  --target <本表目标字段名>
```

**多跳**：`--hops "objId:字段名,objId:字段名"`，前一跳的带出值作为下一跳的过滤值。

**何时用多跳**：目标字段是 Text（要名称）而源表存的是 ID（EBuilder/Select）时，需要多跳一次到名称表取名称；目标字段本身存 ID 则单跳即可。

## 示例

**单跳（快捷配置）**：

```bash
e10-cli form field-linkage add <appId> <objId> \
  --trigger 关联合同 \
  --source-form <合同信息表objId> \
  --condition "关联合同:等于:@关联合同" \
  --query-fields "关联客户" \
  --assign "关联客户=关联客户"
```

**主表联动明细表（多值写入 + 赋值前提）**：

```bash
e10-cli form field-linkage add <appId> <objId> \
  --trigger 客户编号 \
  --source-form <订单表objId> \
  --condition "客户编号:等于:@客户编号" \
  --query-fields "订单号,金额" \
  --assign "订单号=订单明细.订单号" \
  --assign "金额=订单明细.金额" \
  --basis "订单明细=订单号" \
  --detail-mode add --detail-add override --fission on \
  --precondition "订单号:不为空"
```

## 注意事项

1. **三种明细模式**：添加/覆盖/更新由 `--detail-mode` 决定；「删除再添加 / 累计添加」是另一个开关 `--detail-add`。
2. **明细行依据**决定行匹配：写入明细表时，依据值相同的行按模式处理。
3. **赋值前提引用字段**：`@字段名` 先按查询结果字段解析（`source` = 查询节点），找不到再按本表字段（`source` = 触发事件）。
4. **算子与动作流筛选同源**：按字段类型族校验，不支持的算子会直接报错。
5. **FormData 引用格式**：本表字段 `FormData.<本表formId>.<字段id>`；查询结果 `FormData.<源表objId>[].field_<字段id>`。
6. **--source-form 的 objId 是表单 objId**（不是 formId），CLI 内部自动解析。
7. **联动名称**：不传 `--name` 时自动生成 `<本表名>.<触发字段>→<源表名>.<条件字段>`。
8. **SQL 联动类型尚未覆盖**：只支持「动作流联动」（`linkageType=template`）；设计器里的「SQL可视化配置 / SQL联动」两条支路尚未实现。
