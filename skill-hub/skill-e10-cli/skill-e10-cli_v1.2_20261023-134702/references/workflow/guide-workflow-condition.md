# 流程分支条件指南

> 流程基础（建流程、节点、连线、审批人）见 `workflow/guide-workflow.md`。本指南专讲**分支/出口条件**：金额>1万走高级审批、合同类型=采购走快速通道这类路由。

## 添加分支条件（简化语法，推荐）

**一行命令搞定**，自动校验字段类型、自动生成 API payload、自动绑定到连线：

> **AND / OR 规则写在「同一次调用」里**：要组合多条规则，一次 `add` 传多个 `--rule` + `--relation AND|OR`，例如
> `--rule "form:金额:大于:1000" --rule "system:流程标题:包含:合同" --relation AND`。
>
> **对同一连线重复 `add` 是「替换」，不是叠加**：第二次 `add` 会先删掉该连线旧条件再重建。这是刻意的——若允许跨调用叠加，极易产生 `(金额≥100万) AND (金额<100万)` 这类永远不成立的矛盾条件。因此**想给已有条件补一条规则，必须在新的 `add` 里把旧规则连同新规则一起写全**，不能靠再跑一次叠上去。
>
> **同源节点多分支**：一条连线只绑一个条件。要分多个分支，先给每个分支各建一条连线（`add-link`），再分别对每条连线 `add`。

```bash
# 系统字段条件
e10-cli workflow condition add <wf> <sourceId> <nodeId> "条件名称" \
  --rule "system:流程标题:包含:关键词"

# 数值范围条件
e10-cli workflow condition add <wf> <sourceId> <nodeId> "金额过万" \
  --rule "system:流程超时(时):范围:1:72"

# 日期范围条件
e10-cli workflow condition add <wf> <sourceId> <nodeId> "今年发起" \
  --rule "system:发起时间:范围:2026-01-01:2026-12-31"

# 为空/不为空
e10-cli workflow condition add <wf> <sourceId> <nodeId> "无部门" \
  --rule "system:发起人部门:为空"

# 多规则 AND/OR 组合
e10-cli workflow condition add <wf> <sourceId> <nodeId> "复合条件" \
  --rule "system:流程标题:包含:报销" \
  --rule "system:流程超时(时):大于:24" \
  --relation AND

# 表单字段条件（字段ID / 名称 / dataKey 均可匹配）
e10-cli workflow condition add <wf> <sourceId> <nodeId> "表单字段" \
  --rule "form:<字段ID>:大于:1000"          # 按 fieldId
  --rule "form:申请金额:大于:1000"          # 按字段名
  --rule "form:je_2831:大于:1000"           # 按 dataKey（原生流程表单 fieldId 会变，用 dataKey 最稳）
```

> **字段匹配**：`form:` 后可填 fieldId、字段名、或 dataKey/columnName。EB 表单流程的 fieldId 与原始表单一致；**原生流程表单**创建时平台重新生成独立表单、fieldId 变化，此时只能按字段名或 dataKey 匹配。查不到时 CLI 会列出当前出口上下文所有可用字段（id+名+类型+dataKey）。

**可用的系统字段**：流程标题、发起人、发起时间、发起人部门、发起人分部、发起人岗位、发起人职级、当前操作人、流程超时(时)、节点通过时间(时)、紧急程度、发起人直接上级、当前操作人直接上级、密级

**字段类型 → 字段族映射**（按 `fieldType` / `componentKey` 自动判定）：

| fieldType | 字段族 | 说明 |
|-----------|--------|------|
| `Text`/`SerialNumber`/`Email` 等 | String | 等于、不等于、包含、不包含、为空、不为空 |
| `NumberComponent`/`Money`/`Float`/`Integer` | Number | 大于…小于等于、等于、不等于、为空、不为空、范围 |
| `DateComponent`/`DatePicker`/`DateTimePicker` | Date | 大于…小于等于、等于、不等于、为空、不为空、范围 |
| `Employee`/`Department`/`Select`/`CheckBox`/`RadioBox`/`Browser` | Browser | 等于、不等于、包含、不包含、为空、不为空、包含子部门、不包含子部门 |
| `Switch` | Bool | 是、否 |

> **注意**：`CheckBox`/`Select`/`RadioBox` 是**选项类**，归 Browser 族（属于/包含某选项），不是 Bool。Bool（是/否）只针对单值开关 `Switch`。

> CLI 会根据字段类型自动校验操作符合法性，不匹配会给出明确提示。

> **已知缺口**：String/Number/Date 字段可带值完整保存（文本/数值/日期）；Browser/Select/CheckBox 字段目前只支持**为空/不为空**（无需值），**带值条件**（等于/包含/属于 + 选项）需要选项 ID 的数组格式，尚未实现；Bool（Switch 是/否）payload 格式待真实 Switch 字段验证。

---

## 添加分支条件（原始 JSON，完整控制）

需要 4 步操作：
```bash
# 1. 生成新连线 ID
e10-cli workflow generate-link-id <workflowId>               # → newLinkId

# 2. 获取当前流程图 XML，在 XML 中添加新的 <mxCell edge="1"> 后保存
e10-cli workflow save-layout <workflowId> @修改后的xml文件

# 3. 保存条件规则（CLI 自动生成节点 ID，只需写条件逻辑）
e10-cli workflow save-condition @条件.json --app-id <appId>  # → conditionKey

# 4. 绑定条件到连线
e10-cli workflow set-link-condition-key <wf> <linkId> <key> <nodeId>
```

> `--app-id` 用于自动生成唯一 ID。省略时透传原始 JSON（需自己填好所有 ID）。

## 条件 JSON 格式

`childrens` 是**递归树结构**，叶子条件用 `selectType` 判断，分组条件用 `relation` + `childrens` 组合。**CLI 只自动生成 ID**（`expressionId`/`expressionBaseId`/`dataValueId`/`elementValue*Id`），其余字段必须按以下格式手写。

**完整结构**：
```json
{
  "source": 2,
  "sourceId": "连线ID",
  "workflowId": "流程ID",
  "conditionName": "条件名称",
  "linkName": "连线名称",
  "needFormfield": true,
  "readOnly": false,
  "mapBaseId": "表单ID",
  "isEdit": false,
  "isFromRuleListPage": true,
  "relation": 1,
  "childrens": [/* 叶子或分组 */]
}
```

---

### 两种节点类型

**叶子条件** — 有 `selectType`，无 `childrens`：

**分组条件** — 有 `relation` + `childrens`，无 `selectType`：

```json
{ "relation": 1, "childrens": [/* 嵌套的叶子或分组 */] }
```

> `selectType` 是数字 3 或 4。`relation`: 1=AND, 2=OR。

---

### 叶子条件：字段前缀由 fieldType 决定

> **关键**：每组字段有 `{前缀}CompareOptionLeft`、`{前缀}ValueOptionLeft`、`{前缀}TextValueLeft1` 三件套。

**Text / Textarea → `String*` 前缀**：

```json
{
  "selectType": 4,
  "formField": [{ "supportContainType": false, "total": false, "name": "字段名", "id": "fieldId", "fieldType": "Text", "groupKey": "Text" }],
  "StringValueOptionLeft": 1,
  "StringCompareOptionLeft": 5,
  "StringTextValueLeft1": "要匹配的值",
  "valueType": "0"
}
```

**Number / Money / Int → `Number*` 前缀**：

```json
{
  "selectType": 4,
  "formField": [{ "supportContainType": false, "total": false, "name": "金额", "id": "fieldId", "fieldType": "Money", "groupKey": "Money" }],
  "NumberValueOptionLeft": 1,
  "NumberCompareOptionLeft": 1,
  "NumberTextValueLeft1": "50000",
  "valueType": "1"
}
```

**Select / RadioBox / CheckBox → `Browser*` 前缀**：

```json
{
  "selectType": 4,
  "formField": [{ "supportContainType": false, "total": false, "name": "字段名", "id": "fieldId", "fieldType": "Select", "groupKey": "Select" }],
  "BrowserCompareOptionLeft": "9",
  "BrowserValueOptionLeft": "1",
  "BrowserTextValueLeft1": [{ "id": "选项valueKey", "content": "选项名" }],
  "valueType": "0"
}
```

**Date / DateTime → `Date*` 前缀**：

```json
{
  "selectType": 4,
  "formField": [{ "supportContainType": false, "total": false, "name": "日期", "id": "fieldId", "fieldType": "Date", "groupKey": "Date" }],
  "DateValueOptionLeft": 1,
  "DateCompareOptionLeft": 1,
  "DateTextValueLeft1": "2026-07-23",
  "valueType": "0"
}
```

**系统变量-字符串**（selectType=3, systemVariable="-1" 等）：

```json
{
  "selectType": 3,
  "systemVariable": "-1",
  "StringValueOptionLeft": 1,
  "StringCompareOptionLeft": 5,
  "StringTextValueLeft1": "值",
  "valueType": "0"
}
```

**系统变量-日期**（selectType=3, systemVariable="-3" 等）：

```json
{
  "selectType": 3,
  "systemVariable": "-3",
  "DateValueOptionLeft": 1,
  "DateCompareOptionLeft": 1,
  "DateTextValueLeft1": "2026-07-23",
  "valueType": "0"
}
```

---

### formField 字段映射

`formField` 需要**完整字段元数据**（不是精简格式）。直接从 `form read --app-id <appId> --out fields.json` 输出的字段对象中取，保留所有字段。

`formField` 至少包含：`id`（fieldId）、`name`（fieldName）、`fieldType`、`detail`、`detailName`、`total`、`formId`、`sourceModule`、`layoutDetail`、`selectDataSource`、`groupKey`、`supportContainType`、`newFormDesigner`、`variable`、`valueCount`、`dataTemplateId`、`detailTableId`。

> **不要精简**：碰到 `selectType: "4"` 就把 `form read` 返回的字段对象全量塞进 `formField` 数组。紧凑格式在 mulinquan 碰巧能过但不完整，eteams 直接拒绝。

---

## 查看已有条件

```bash
# 列出工作流下所有连线绑定的条件（连线名 + 条件名 + 表达式 + mapId）
e10-cli workflow condition list <workflowId> [--name <关键词>]
# 查看单个条件详情（含中文表达式），id 可用 conditionKey / mapId / conditionId
e10-cli workflow condition get <workflowId> <id>
# 删除条件（自动解绑连线），id 同 get
e10-cli workflow condition delete <workflowId> <id> [--link-id <linkId>]
```

> **getConditionList 是「按连线」查询**：请求体需回传 getConditionSet 的完整上下文
> （`sourceId`=连线 + `conditionName`=sourceName + `linkName` + `mapBaseId`/`conditionKey`
> + `exitConditionMapBrowserInfo`/`conditionMapBrowserBean`），只传简化参数会返回空列表。
> 删除时 `deleteConditions.mapIds` 需传 **mapId**（getConditionList 记录里的 mapId），不是 conditionKey。

---

### 前缀速查表

| 字段类型 | selectType | 前缀 | CompareOption 类型 | valueType |
|---------|-----------|------|--------------------|-----------|
| Text / Textarea | 4 | `String` | number | `"0"` |
| Number / Money / Int | 4 | `Number` | number | `"1"` |
| Select / RadioBox / CheckBox | 4 | `Browser` | **string** | `"0"` |
| Date / DateTime | 4 | `Date` | number | `"0"` |
| 系统变量-字符串 | 3 | `String` | number | `"0"` |
| 系统变量-日期 | 3 | `Date` | number | `"0"` |
| 系统变量-下拉 | 3 | `SysBrowser` | — | `"0"` |

---

### 比较符（CompareOption）

| 值 | 含义 |
|---|------|
| 1 | 大于 |
| 2 | 大于等于 |
| 3 | 小于 |
| 4 | 小于等于 |
| 5 | 等于 |
| 6 | 不等于 |
| 9 | 包含（文本/人员/部门）/ 属于（发起人/下拉） |
| 10 | 不包含 / 不属于 |
| 13 | 为空 |
| 14 | 不为空 |

> **易错**：`1` 是「大于」**不是**「大于等于」——`≥` 要用 `2`，`<` 用 `3`，`≤` 用 `4`。
> Number/Date 字段用 1/2/3/4/5/6（数值、日期比较）；Text 用 5/6/9/10（等于/不等于/包含/不包含）；Select/Browser 用 9/10（属于/不属于）。完整矩阵见 operator-matrix.md。

---

### 树结构示例

`合同子类型=采购类 AND 合同总金额≤50000`：

```json
{
  "source": 2,
  "sourceId": "1294902940272197632",
  "workflowId": "1294602764921430016",
  "conditionName": "采购类5w快速通道",
  "linkName": "采购类5w快速通道",
  "needFormfield": true,
  "readOnly": false,
  "mapBaseId": "1294601519433310236",
  "isEdit": false,
  "isFromRuleListPage": true,
  "relation": 1,
  "childrens": [
    {
      "selectType": 4,
      "formField": [{"supportContainType":false,"total":false,"name":"合同子类型","id":"1294601519433310217","fieldType":"Select","groupKey":"Select"}],
      "BrowserCompareOptionLeft": "9",
      "BrowserValueOptionLeft": "1",
      "BrowserTextValueLeft1": [{"id":"1294601523677945864","content":"采购类"}],
      "valueType": "0"
    },
    {
      "selectType": 4,
      "formField": [{"supportContainType":false,"total":false,"name":"合同总金额","id":"1294601519433310221","fieldType":"Money","groupKey":"Money"}],
      "NumberCompareOptionLeft": 4,
      "NumberValueOptionLeft": 1,
      "NumberTextValueLeft1": "50000",
      "valueType": "1"
    }
  ]
}
```

> `expressionId`/`expressionBaseId`/`dataValueId`/`elementValue*Id` 省略，CLI 自动生成。

---

## 参考

- [字段类型与关系符编码矩阵](operator-matrix.md) — 数字编码、字段类型矩阵、系统字段清单
