# 浏览数据定义

浏览数据定义控制浏览弹窗的默认高级搜索、可选数据范围和显示 Tab。先查询表单中哪些浏览字段可配置，再查看指定字段由数据源提供的条件与选项，最后只配置已开放的项目。不同浏览来源可能仅开放其中一部分。

## 操作顺序

```bash
# EB 表单传 formId 和 appId
e10-cli form-engine browser-definition inspect <formId> --module ebuilderform --app-id <appId>
e10-cli form-engine browser-definition describe <formId> <fieldId> --module ebuilderform --app-id <appId>

# 工作流程从「流程引擎 → 工作流管理 → 工作流程 → 高级设置 → 浏览数据定义」进入
e10-cli form-engine browser-definition inspect <流程关联的formId> --module workflow --workflow-id <流程ID>
e10-cli form-engine browser-definition describe <formId> <fieldId> --module workflow --workflow-id <流程ID>
```

`inspect` 对每个字段分别输出 `search/scope/tabs` 的 `platform`（平台是否开放）、`cli`（CLI 是否有该数据源适配）和 `configured`（已配置标记）。`describe` 返回字段原始元数据、支持项的当前配置及候选条件／范围／Tab。只在 `platform=true, cli=true` 时执行对应写入；`platform=true, cli=false` 表示数据源允许设置，但该浏览来源的保存结构尚未纳入 CLI。字段名重名时使用字段 ID。

EB 表单可从表单引擎的表单设置进入。工作流程表单的表单引擎设置页没有独立的“浏览数据定义”；它跟随所属工作流程配置，入口是「流程引擎 → 工作流管理 → 工作流程 → 高级设置 → 浏览数据定义」。先确定工作流程及其关联的表单，再传该表单 ID 和 `--workflow-id <流程ID>`。流程接口使用 `module=ebuildercard`，浏览配置的 `businessId` 是流程 ID，`formId` 是流程关联的表单 ID；同一表单若用于不同流程，应按目标流程分别读取和设置。流程表单预览不会按此配置过滤，应在流程实际使用场景核对。其他表单引擎模块按各自入口和实际开放能力配置。

## 高级搜索

```bash
e10-cli form-engine browser-definition search get <formId> <fieldId> --module <module> [--app-id <appId>]
e10-cli form-engine browser-definition search set <formId> <fieldId> --module <module> [--app-id <appId>] --config @search.json
```

`get` 同时返回数据源提供的搜索布局与当前配置。`set` 使用该布局构造完整配置，至少给 `lines/cells/commonLines/commonCells/searchValue`；可保留或设置 `aliasName/disableList/config/filterIsNull`。关联 EBuilder、人员、部门、分部和自定义浏览框均按各自数据源实时返回的布局填写，保存后重新读取配置。

- `commonLines/commonCells` 是常用条件，`lines/cells` 是自定义添加的其他条件；其他条件可重复出现，行顺序即前台显示顺序。
- 常用条件展示数据源提供的项目；若用户在前台自行调整常用条件，前台以个人设置为准。
- 条件 `visible=false` 是前台隐藏但条件仍生效；`readOnly=true` 是显示但不允许前台修改。隐藏时不再设置只读。
- `disableList` 用于禁用前台搜索条件，影响常用、其他和个人设置中的该条件；它与“隐藏但仍执行”不同。
- `searchValue` 保存浏览弹窗打开时采用的默认搜索值。操作符及值形状按 `get` 返回的 `layout.items` 构造，不能对所有浏览类型套用同一字段名。
- “快捷搜索使用默认条件”仅在该浏览来源实际开放时配置。关联流程有此能力；其他来源即使保存结构含 `enableQuickSearch`，也不据此推定功能生效。

当前 `search set` 接收完整搜索配置，由 `get` 的布局和现值指导编写；不把平台复杂的单元格结构隐含成未经验证的简化条件语法。

## 数据范围

```bash
e10-cli form-engine browser-definition scope get <formId> <fieldId> --module <module> [--app-id <appId>]
e10-cli form-engine browser-definition scope candidates <formId> <fieldId> --module <module> [--app-id <appId>] --kind resource|department|subcompany --keyword <名称>
e10-cli form-engine browser-definition scope matrix-options <formId> <fieldId> --module <module> [--app-id <appId>] --matrix-id <矩阵ID>
e10-cli form-engine browser-definition scope set <formId> <fieldId> --module <module> [--app-id <appId>] --config @scope.json
```

数据范围按浏览来源选择适配器：

| 来源 | `--config` 结构 | 说明 |
|---|---|---|
| 人员 `hrm/resource` | `{"rules":[...],"range":"any"}`；完整报文亦可用 `itemDatas[]` | `get` 返回当下布局码表、表单字段候选、矩阵选项和现存范围。`rules[]` 按当前布局校验并转换，与已有项按范围来源合并。 |
| 部门 `hrm/department` | `{"rules":[...]}`；完整报文亦可用 `records[]` | 已核对指定部门／分部、创建人、当前操作者、表单部门字段。 |
| 分部 `hrm/subcompany` | `{"rules":[...]}`；完整报文亦可用 `records[]` | 已核对指定分部、创建人、当前操作者、表单分部字段。 |
| 关联 EBuilder `ebuilder/form/ebuilder` | `{"records":[{"scopeType":"scopeSql","scopeInfoRender":"..."}]}` | `scopeInfoRender` 为条件树 JSON 字符串；已有 `form ebuilder-scope` 提供按字段名编译的简便方式。 |
| 自定义浏览框 `bcw/customBrowser_*` | `{"records":[{"scopeType":"scopeSql","scopeInfoRender":"..."}]}` | `scope get` 返回该浏览框自己的 `conditionLayout`，从其中选择字段与操作符，按完整条件树写入；字段和操作符在保存前校验。 |
| 行政区域 `bcw/city` | `{"records":[{"scopeType":"normal_country","scopeInfo":"国家ID","scopeInfoRender":"{...}","type":"normal"}]}` | 例：指定国家为中国；国家 ID 从实际候选列表取得。 |

`records` 是完整范围记录，按 `get` 回读的 ID 更新既有项。人员范围与流程操作者的选项概念相近，但并非全量相同，必须以 `describe` 返回的可选布局为准。加入多项范围时，其可选数据取并集；未设置范围时不应把它误判为“空范围”。

### 自定义浏览框

先用 `inspect` 找出目标字段及其 `bcw/customBrowser_*` 来源，再用 `describe` 或 `scope get` 读取当前配置和 `conditionLayout`。候选布局按当前浏览框动态返回，每个字段提供 `id/text/type/compType/conditionType` 等信息；条件树叶节点的字段 ID 与操作符须来自这份布局。`scopeInfoRender` 使用平台的完整条件树 JSON 字符串，组节点的 `datas` 可嵌套 AND／OR 条件。日期区间在候选操作符中记作 `between`，已见保存条件采用 `conditions.func="range"` 且 `value` 为两个日期值；其他操作符和值结构按该字段实际候选及现有配置填写。高级搜索同样先读该浏览框返回的 `layout.items`，再构造 `commonLines/commonCells/lines/cells/searchValue`。Tab 是否可配以 `inspect` 的 `tabs.platform` 为准。

### 关联 EBuilder 的嵌套条件

关联 EBuilder 的数据范围使用 `scopeType=scopeSql` 的条件树。`form ebuilder-scope set --rules ... --logic and|or` 适合一层平铺条件；需要 `A OR (B AND C)` 等混合逻辑时，使用本命令的完整 `records[].scopeInfoRender`。先用 `scope get` 读取原配置，按目标表实际字段、字段类型和可选操作符调整条件树，再保存并回读。

条件树中的 `datas` 可以同时包含字段条件和子条件组；组的 `relationship` 为 `1`（AND／所有条件）或 `0`（OR／任一条件）。每个组有唯一 `key`，子项的 `parentNode` 指向直接父组的 `key`。例如 `A OR (B AND C)` 的结构是：

```json
{
  "key": "root", "relationship": "0", "isParent": true, "parentNode": "",
  "isNewFilter": true, "version": 1, "showFilterIsNull": false,
  "datas": [
    { "key": "a", "parentNode": "root", "isParent": false, "type": "condition",
      "id": "name", "fieldName": "name", "fieldType": "String", "compType": "Text", "text": "标题",
      "conditions": { "func": "eq", "value": "A", "selectValue": { "id": "manualInput", "content": "手动输入", "type": "SELECTION_CUSTOM" }, "customValue": "A", "customBrowserValue": [] } },
    { "key": "group-bc", "parentNode": "root", "relationship": "1", "isParent": true,
      "datas": [
        { "key": "b", "parentNode": "group-bc", "isParent": false, "type": "condition",
          "id": "name", "fieldName": "name", "fieldType": "String", "compType": "Text", "text": "标题",
          "conditions": { "func": "eq", "value": "B", "selectValue": { "id": "manualInput", "content": "手动输入", "type": "SELECTION_CUSTOM" }, "customValue": "B", "customBrowserValue": [] } },
        { "key": "c", "parentNode": "group-bc", "isParent": false, "type": "condition",
          "id": "name", "fieldName": "name", "fieldType": "String", "compType": "Text", "text": "标题",
          "conditions": { "func": "eq", "value": "C", "selectValue": { "id": "manualInput", "content": "手动输入", "type": "SELECTION_CUSTOM" }, "customValue": "C", "customBrowserValue": [] } }
      ] }
  ]
}
```

上面展示的是 `scopeInfoRender` **解码后的条件树**，用于说明嵌套关系；实际 `scope.json` 须把整棵树序列化为 JSON 字符串，放入 `{"records":[{"scopeType":"scopeSql","scopeInfoRender":"<序列化后的条件树>"}]}`。字段 `id/fieldName/fieldType/compType`、`conditions` 的操作符和值结构要按目标字段和 `scope get` 返回的同类条件填写；选项、表单字段、变量字段等值的报文形状与示例的手动文本值不同。更新已有规则时保留其记录 ID（CLI 在未给 ID 时也会按 `scopeType` 查找并沿用已有 ID）。保存后再次 `scope get`，核对树层级、每层 `relationship`、字段和值及记录 ID。工作流程场景还须传 `--workflow-id`，并在所属工作流程的实际使用场景核对筛选效果。

### 人员范围码表与简化规则

下表是已抓到的范围来源；同一 `groupTypeId` 的 `includeType`、组织维度等下级选项仍应以 `scope get` 实时返回的 `groups[].options` 为准。表单字段候选取 `formFieldCandidates`，矩阵候选取 `matrixOptions`；指定对象先用 `scope candidates` 查询。

| `rules[].kind` | 平台组码 | 主要参数 | 适用说明 |
|---|---:|---|---|
| `person` | 101 | `target` 为候选人员对象 | 指定人员 |
| `everyone` | 110 | 无 | 所有人 |
| `creator` | 114 | `includeType`、`virtualId` | 数据创建人及其组织关系 |
| `operator` | 121 | `includeType`、`virtualId` | 当前操作者及其组织关系 |
| `field` + `fieldType=resource` | 201 | `field`、`includeType` | 按表单人员字段值取范围 |
| `field` + `fieldType=department` | 202 | `field`、`includeType` | 按表单部门字段值取范围；抓包有本部门 `1` |
| `field` + `fieldType=subcompany` | 203 | `field`、`includeType` | 按表单分部字段值取范围；抓包有本分部 `4` |
| `matrix` | 401 | `sourceId/sourceIdType/targetId/matrixRules` 等 | 先选择矩阵并读取 `getMaTrixItems` 返回的来源、结果字段及映射项 |

布局中还可出现指定部门 `102`、指定分部 `103`、指定角色 `104`、指定岗位 `105` 等组。它们的组织维度、包含上下级和安全级别选项因当前字段与数据源而异；先从 `get` 读取，未纳入简化规则的结构可使用完整 `itemDatas[]`，不能照搬流程操作者的全量码表。指定部门的已见关系码为 `1/2/3`（本部门／含下级／含上级），指定分部为 `4/5/6`（本分部／含下级／含上级）。

```json
{
  "rules": [
    {"kind":"field","fieldType":"department","field":"报销部门","includeType":"1"},
    {"kind":"operator","includeType":"12"}
  ]
}
```

矩阵规则示例结构为 `{"kind":"matrix","sourceId":"...","sourceIdCN":"...","sourceIdType":"2","targetId":"...","targetIdCN":"...","matrixRules":[{"sourceField":"矩阵来源字段ID","sourceType":"customBrowser","targetField":"表单字段ID"}]}`。来源和结果字段 ID 应从所选矩阵的候选接口读取，`matrixRules` 映射矩阵来源字段与当前表单字段；只提供矩阵 ID 无法完成此设置。

### 部门、分部范围码表

两者走 `browserDataScope`，浏览类型分别是 `hrm_department` 和 `hrm_subcompany`，不是人员范围的 `hrm_resource`。以下是已核对的 `rules[].type`：

| 来源字段 | 可用 `type` | 已核对的关系码／值 |
|---|---|---|
| 部门 | `targetDepartment`、`targetSubcompany`、`creator`、`operator`、`department` | 指定部门 `ownDepartment`；指定分部 `ownOrSubcompany`；创建人 `subcompanyAsCreator`；操作者 `subcompanyAsOperator`；表单部门 `ownDepartment` |
| 分部 | `targetSubcompany`、`creator`、`operator`、`subCompany` | 指定分部 `ownOrSubcompany`；创建人 `subcompanyAsCreator`；操作者 `OPERATOR_SUP_SUBCOMPANY`；表单分部 `ownSubcompany` |

`targetDepartment/targetSubcompany` 的 `target` 使用 `scope candidates` 返回的完整候选对象；`department/subCompany` 的 `field` 使用本表字段名或 ID。`creator/operator` 可给 `virtualId`（未给取已核对的行政组织 `1`）。其它上下级关系码要以相应字段的界面候选与保存报文核对后再补，不按中文含义猜码。

```json
{"rules":[{"type":"targetDepartment","target":{"id":"部门ID","name":"技术部","content":"技术部"},"mode":"ownDepartment"},{"type":"department","field":"报销部门","mode":"ownDepartment"}]}
```

## 浏览 Tab

```bash
e10-cli form-engine browser-definition tabs get <formId> <fieldId> --module <module> [--app-id <appId>]
e10-cli form-engine browser-definition tabs set <formId> <fieldId> --module <module> [--app-id <appId>] --show 1,2 [--default 1|none] [--order 2,1]
```

先查询该数据源返回的实际 Tab ID，再设显示、默认选中和顺序。可以不指定默认 Tab；若指定，则它必须显示。未传 `--default` 时保留仍可见的原默认项，`none` 清除默认项。`--order` 若给出须包含所有 Tab ID。写入时保留每个 Tab 的平台元数据，完成后重新读取。

## 支持边界

命令入口与能力发现按表单引擎模块统一；底层仅适配已核对报文的浏览来源。当前已适配关联 EBuilder、人员、部门、分部、城市行政区域及自定义浏览框对应的已开放配置项。项目、关联流程等来源会在 `inspect` 中展示平台支持情况，但保存报文未经核对的子项标为 `cli=false`。工作流程路径需同时给关联表单 ID 与 `--workflow-id`；其写入效果须在流程实际使用场景验证。
