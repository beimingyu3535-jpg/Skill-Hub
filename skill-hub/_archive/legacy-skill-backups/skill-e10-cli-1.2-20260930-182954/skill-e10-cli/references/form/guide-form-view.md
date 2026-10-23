# 表单视图：新建与验收

表单创建后已有默认台账；只有用户明确需要额外视图时才创建。表格视图是 `nListView` 数据列表，和普通 `formView` 是两条不同链路。

## 需求判别

- “新建表单” → `form create --fields`。
- “在已有表单下新增表格视图” → `form table-view create`；命令必须同时保存显示列并回读。
- “在已有表单下新增表单视图” → `form view create --type formView`，随后必须 `form view populate`；不得新建另一张表单。

## 命令

```bash
# 查询表单下全部视图
e10-cli form view list <objId> <appId>

# 创建可用表格视图；默认放入全部已有字段
e10-cli form table-view create <objId> <appId> "审批数据表格" --pc-only

# 创建看板视图（默认 PC + FLOW 布局）
e10-cli form view create <objId> <appId> "按状态看板" --type kanbanView

# 创建详情 formView
e10-cli form view create <objId> <appId> "审批详情" --type formView

# 按目标布局类型把已有字段放入新建 formView
e10-cli form view populate <objId> <appId> <viewId>

# 创建移动端日历视图
e10-cli form view create <objId> <appId> "交付日历" \
  --type calendarView --terminal MOBILE --layout-type FLOW
```

`formView` 创建后是空布局，必须继续执行 `form view populate`。该命令以原表单 `formId` 读取字段，以新视图 `viewId` 作为 `layoutMultiId` 读取目标布局，再按目标的 FLOW/EXCEL 类型重新生成字段组件并独立回读。不得把默认布局的 EXCEL 定位直接复制到 FLOW 视图，也不得把视图的 `versionId` 或 `pageLayoutId` 当成 `formId`。

看板、日历、思维导图目前只确认创建实体和视图列表回读，尚不能据此宣称设计器已有可用组件。

普通 `form view create --type` 只接受：

- `formView`：详情视图
- `kanbanView`：看板视图
- `calendarView`：日历视图
- `mindMapView`：思维导图视图

`tableView`/`nListView` 不得传给普通视图命令。真实表格视图固定使用 `form table-view create`。

## 表格视图固定闭环

```bash
# 1. 确认目标表单和同名列表不存在
e10-cli form list <appId>
e10-cli form list-view <objId> <appId>

# 2. 创建 nListView、写入全部业务显示列和隐藏数据主键、独立回读
e10-cli --json form table-view create <objId> <appId> "<表格视图名>" --pc-only

# 3. 再次独立查询表单下列表
e10-cli --json form list-view <objId> <appId>
```

命令先用 `viewType=nListView` 创建，再以新 `listId` 读取 PC 配置；业务列必须取自 `/api/ebuilder/common/ds/fields` 的完整字段对象，不能只拼字段 ID。保存时保留服务端配置和隐藏主键 `id=5`，最后回读 `tableField` 和列表实体。已有同名视图时停止，不盲目重建。

`--pc-only` 只用于已确认本次验收为 PC 的场景。未指定时，命令必须取得真实 MOBILE 配置，禁止用 PC 配置推导移动端。

服务器通过必须同时满足：

- 创建后按返回 `listId` 找到同名列表。
- `persisted=true`。
- `visibleFieldCount` 等于目标业务字段数。
- `tableFieldCount` 还包含隐藏主键。
- 再查 `form list-view` 仍能按相同 ID 和名称找到。

前端无数据时可以没有数据行，但必须看见业务字段列头；否则仍是空壳，不能验收。

## 表格视图展示样式

```bash
e10-cli --json form table-view style <objId> <appId> <listId> <style>
```

`style` 使用前台语义，不直接让使用者猜内部 `mode`：

| style | 前台展示样式 | mode |
|---|---|---|
| `table` | 表格式 | `1` |
| `list` | 列表式 | `2` |
| `left-diagram` | 左图式 | `3` |
| `horizontal-list` | 横向列表式 | `4` |
| `above` | 上图式 | `5` |
| `grid` | 网格列表式 | `7` |
| `editable` | 可编辑表格（编辑态） | `11` |

可编辑表格内部还有数据态 `8` 和只读态 `9`；用户要求“改成可编辑表格”时必须使用编辑态 `11`，不得把只读态 `9` 当成完成。

命令先确认 `listId` 属于目标 `objId`，分别读取完整 PC/MOBILE 配置，只修改 PC 顶层 `mode`，保存后重新读取 PC 配置。移动端配置必须原样保留；读取不到时，只有明确 `--pc-only` 才允许继续。

前端验收：重新进入“基础设置 → 展示样式”仍显示“可编辑表格”，并且列表进入可编辑状态。

## 常用搜索显示方式

```bash
# PC 常用搜索显示为高级搜索；filter 表示筛选
e10-cli --json form table-view search-style <objId> <appId> <listId> advanced
```

显示方式固定为 `advanced → commonSearchType="0"`、`filter → commonSearchType="1"`，不得直接猜内部值。

命令先确认 `listId` 属于目标表单，完整保留 PC 其他配置和真实 MOBILE 配置，保存后重新读取目标属性。前端验收：“常用搜索 → 基础信息 → 显示方式”能正常打开，且刷新后仍为目标方式；若配置页异常，接口回读成功也不能验收。

## 常用搜索字段

```bash
e10-cli --json form table-view search-field add <objId> <appId> <listId> <fieldId>

# 按前端字段设置面板配置搜索项
e10-cli --json form table-view search-field configure \
  <objId> <appId> <listId> <fieldId> \
  --display-name "单据名称" \
  --default-value "111" \
  --required 0 \
  --full-match 0 \
  --condition like
```

命令必须从当前数据源接口取得完整字段模型，按前端最终保存结构生成搜索项：字段 `id` 与独立的 18 位 `filterId` 不得混用，字段自身 `multiSelect` 原样保留，搜索默认配置单独写入 `listFilterDefaultSets`。保存时完整保留 PC 其他配置和真实 MOBILE 配置，再独立回读字段及条件关系。

具体配置固定映射：

- `--default-value`：固定默认值，写为 `defaultType="1"` 与 `startValue`；`--clear-default` 清除。`Select` 字段可传选项名称或选项 ID，CLI 必须从当前数据源解析为唯一真实 ID，并保留完整选项对象供前端回显。
- `--required 0|1`：条件是否必填，写为字段级 `required`。
- `--full-match 0|1`：搜索内容是否完整匹配，写入 `listFilterDefaultSets.searchContentFullMatches`。
- `--condition like|eq|...`：必须来自该字段实际允许的条件，同时更新字段层与默认设置层。
- `--display-name`：更新搜索项 `showName`；不得覆盖原字段名和字段 ID。

前端验收：打开“搜索配置”不报异常，目标字段出现在常用搜索字段中；刷新列表后可使用该字段发起搜索。只通过接口回读不能验收。

## 台账显示列/搜索/排序/统计（list-columns / list-search / list-sort / list-stats）

直接改默认台账（nListView）的显示列、搜索条件、排序、顶部统计。listId 取 `form list-view` 返回的列表视图 ID。四个命令都只改 PC 端，**保存时先读回真实移动端 mConfig 原样回传，不会清空移动端**（抓包确认：`saveNListConfig` 一次请求里 `config`→PC 端、`mConfig`→移动端，两端列集合/uid 各自独立）。只有明确目标只使用 PC、移动端配置确实不存在时，才加 `--pc-only`。

```bash
# 查看当前显示列
e10-cli form list-columns <objId> <appId> <listId>

# 追加字段到显示列 / 移除字段
e10-cli form list-columns <objId> <appId> <listId> --add <fieldId>
e10-cli form list-columns <objId> <appId> <listId> --remove <fieldId>

# 配置搜索：--add 进搜索面板，--quick 加顶部快捷筛选
e10-cli form list-search <objId> <appId> <listId> --add <fieldId>
e10-cli form list-search <objId> <appId> <listId> --quick <fieldId>

# 配置排序 / 清除
e10-cli form list-sort <objId> <appId> <listId> --field <fieldId> --order ASC
e10-cli form list-sort <objId> <appId> <listId> --clear

# 顶部统计：type=sum 求和 / count 计数 / avg 平均 / max 最大 / min 最小
e10-cli form list-stats <objId> <appId> <listId> --add '{"fieldId":"...","type":"sum","name":"合计"}'
e10-cli form list-stats <objId> <appId> <listId> --remove <statId>
```

字段 ID 来自 `form read <objId> --app-id <appId>` 或 `form list-columns` 当前列（系统列如 `2`创建者/`3`创建时间/`5`数据ID 也可增删）。保存成功后命令打印 `移动端配置: 保持原样` 即确认移动端未被触碰。

## formView 固定闭环

```bash
# 1. 确认目标表单与现有视图
e10-cli form list <appId>
e10-cli form view list <objId> <appId>

# 2. 创建视图并从输出取得 viewId
e10-cli --json form view create <objId> <appId> "<视图名>" --type formView

# 3. 填充已有字段并独立回读
e10-cli --json form view populate <objId> <appId> <viewId>
```

`populate` 只有同时满足以下条件才算服务器验证通过：

- `success=true`
- `componentCount > 0`
- `fieldComponentCount > 0`
- 重复执行返回 `alreadyPopulated=true`

服务器验证通过后仍需用户确认前端不是空画布、字段名称和特殊配置正确。

## 执行与验收

1. 计划中写明表单 objId、视图名称、类型和终端；用户确认后再写入。
2. CLI 先调用 `createView`，再查询该表单的完整视图列表；创建响应本身不是验收。`formView` 随后调用 `populate`：`原 formId + viewId(layoutMultiId)` 读取目标布局，保留目标页面元数据，按目标布局类型重建已有字段组件并保存。
3. 回读以返回的 viewId 优先；服务端未返回 ID 时，才按名称、类型和终端唯一匹配。多个候选视图时停止并让用户确认。
4. `populate` 回读组件数量和字段 ID；用户再确认新视图设计页出现表单既有字段，而非只有“未分组”的空画布。

服务器成功和独立回读成功但尚未前端确认时，只能标记为“待前端确认”。
