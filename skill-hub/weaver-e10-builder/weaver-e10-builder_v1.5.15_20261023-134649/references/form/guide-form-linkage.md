# 显示属性联动指南

## 表单引擎模块选择

显示属性联动属于表单引擎能力，不限于 EB 表单。按表单实际所属模块选择命令与接口，不能把不同模块的 formId 混用：

| 模块 | 已确认的命令路径 | 已确认的接口前缀 |
|---|---|---|
| EB 表单 `ebuilderform` | `form linkage` | `/api/ebuilder/form` |
| 原生流程表单 `workflow` | `form-engine linkage --module workflow`；原有 `wf-form linkage` 仍可新增普通字段规则 | `/api/workflow/core` |
| 业务表单 `biaoge` | `form-engine linkage --module biaoge` | `/api/formdatareport` |

其他模块虽可能共用表单引擎前端组件，但尚未核对对应的保存报文与接口前缀，不按以上任一模块代填。

非 EB 表单的简单条件与字段目标可用统一命令：

```bash
e10-cli form-engine linkage fields <formId> --module workflow|biaoge
e10-cli form-engine linkage targets <formId> --module workflow|biaoge
e10-cli form-engine linkage add <formId> <名称> --module workflow|biaoge --config @rule.json [--workflow-id <流程ID>]
e10-cli form-engine linkage list <formId> --module workflow|biaoge
e10-cli form-engine linkage get <formId> <规则ID> --module workflow|biaoge
e10-cli form-engine linkage state <formId> <规则ID> --module workflow|biaoge --set on|off
e10-cli form-engine linkage update <formId> <规则ID> --module workflow|biaoge [--name <名称>] [--config @rule.json]
e10-cli form-engine linkage delete <formId> <规则ID> --module workflow|biaoge
```

先用 `fields` 查触发字段（`bizFields` 系统字段、`formFields` 表单字段），用 `targets` 查可变更字段，再写配置。系统字段以 `valueKey` 为条件目标，比较值按返回的 `valueType` 构造；选项型系统字段可在 `value` 中写选项名或 ID。非文本/日期/选项类型的系统字段，按平台结构明确提供 `sourceContent`。业务字段以字段 ID 为目标。动作目标使用平台可选列表返回的完整对象。

```json
{
  "conditions": [{"field":"紧急程度","operator":"EQUAL","value":"正常"}],
  "actions": [{"prop":"edit","fields":["浏览按钮B"]}]
}
```

`conditions[]` 支持 `detailType: "AND"`（全部）或 `"OR"`（任一）；空值算子使用 `NULL` / `NOT_NULL`。当前新命令支持字段目标 `field` 的 `hide/show/edit/readonly/required/hideLine/hideRow`，不将 EB 已支持的选项、明细组件或布局组件结构直接套用到其他模块。`biaoge` 当前使用“当前表单”生效维度；原生流程表单的流程／节点范围需给 `--workflow-id`，具体 `effect`、`nodeId` 仍按下文规则填写。`update --config` 提交一份完整新规则，名称单独更新可只用 `--name`。

## 概述

显示属性联动根据字段值或布尔公式的结果，改变字段、选项或明细表组件的显示与读写属性。它适合在同一布局中按业务条件动态切换；不同流程节点无条件地采用不同布局或固定权限时，仍使用节点布局或节点字段权限。

条件不满足时，目标恢复到布局中的默认读写属性。不同规则同时命中同一字段时，平台优先级为：隐藏 > 只读 > 必填 > 编辑；同一触发字段或目标字段尽量避免落入多条相互冲突的规则。

## 规则生命周期

```bash
e10-cli form linkage add <appId> <objId> <名称> --config @rule.json [--disabled]
e10-cli form linkage list <appId> <objId> [--keyword <名称>]
e10-cli form linkage get <appId> <objId> <规则ID> --json
e10-cli form linkage layout-targets <appId> <objId>
e10-cli form linkage state <appId> <objId> <规则ID> --set on|off
e10-cli form linkage update <appId> <objId> <规则ID> [--name <新名称>] [--config @patch.json]
e10-cli form linkage delete <appId> <objId> <规则ID>
```

规则名最长 200 字。新增默认启用，`--disabled` 可新建为停用；启停独立保存并读回。更新先读详情，只替换 `--name` 或配置中明确提供的 `conditions`、`detailType`、`effect`、`actions`、公式；未提供的部分保持原样。`actions` 是整组替换，修改前先用 `get --json` 核对现有目标。删除时按当前表单核对规则归属，再删除并回读确认。

## 配置结构

```json
{
  "conditions": [
    {
      "fieldId": "触发字段ID",
      "operator": "EQUAL",
      "options": [{"optionId": "选项ID", "content": "选项名"}]
    }
  ],
  "actions": [
    {
      "linkageObj": "field",
      "prop": "hide",
      "fields": [
        {
          "fieldId": "目标字段ID",
          "name": "字段名称",
          "dataKey": "字段编码",
          "fieldType": "Employee",
          "isDetail": false
        }
      ]
    }
  ]
}
```

### actions[].fields[]（联动目标字段）

| 键 | 说明 |
|------|------|
| fieldId | 目标字段的 fieldId（从 `form read --app-id` 获取） |
| name | 字段名（显示用） |
| dataKey | 字段编码；`form read` 不返回它，**留空即可**（用 fieldId 代替可行） |
| fieldType | 字段类型，如 `Text` / `Employee` / `Date` |
| **`isDetail`** | **目标落在明细表里时必须为 `true`**。不传 = 主表字段 |

**目标字段在明细表里，就加 `"isDetail": true`** —— 这是「主表字段控制明细列显隐」的写法，两个方向都支持（`hide` / `required` 均可）：

```json
{
  "conditions": [{ "fieldId": "<主表字段ID>", "operator": "EQUAL", "value": "Y" }],
  "actions": [{
    "prop": "hide",
    "fields": [{ "fieldId": "<明细列ID>", "name": "明细列A", "dataKey": "", "fieldType": "Text", "isDetail": true }]
  }]
}
```

**怎么认出明细字段**：`form read` 的输出里，明细字段会标注所属明细表 —— 带 `明细表: xxx` 那些就是，照它填 `isDetail: true`。

### 简易条件 `conditions`

多个条件用顶层 `detailType: "AND" | "OR"` 指定全部满足或任一满足；未指定时由平台采用默认值。

| 字段 | 说明 |
|------|------|
| fieldId | 触发字段的 fieldId（从 `form read --app-id` 获取） |
| operator | 比较符，见下表 |
| value | 普通字段的比较值（文本/数字）。**「为空 / 不为空」不要给** |
| options | Select/RadioBox 字段的选项，格式：`[{"optionId": "选项ID", "content": "选项名"}]` |
| sourceFieldId | 以另一个表单字段的值作右值，走 `VARIABLE`，与常量值二选一 |
| sourceContent | 人员、日期等结构化常量对象，直接编码为平台 `sourceContent`；与 `value/options` 二选一 |

比较符：

| 写法 | 含义 | 备注 |
|------|------|------|
| `EQUAL` / `NOT_EQUAL` | 等于 / 不等于 | |
| `CONTAIN` / `NOT_CONTAIN` | 包含 / 不包含 | |
| `GREATER` / `LESS` / `GREATER_EQUAL` / `LESS_EQUAL` | 大于 / 小于 / 大于等于 / 小于等于 | |
| **`NULL`** | **为空** | 也可以写 `EMPTY` / `IS_NULL`，命令会归一成平台码 |
| **`NOT_NULL`** | **不为空** | 也可以写 `NOT_EMPTY` / `IS_NOT_NULL` |

**「为空」的算子写错，报错会指向完全无关的地方。** 平台不认 `EMPTY` 这类写法时不会说「算子不合法」，而是在写库时抛一句 `mybatis PersistenceException / Error updating database` —— 容易让人误判成字段配置问题（真实发生过：被当成「目标字段 `dataKey` 为空导致 NOT NULL」去查，而 `dataKey` 留空本身是没问题的）。用 `NULL` / `NOT_NULL`，或者写 `EMPTY` 交给命令归一。

触发字段可以是主表或明细表字段，也可包含平台返回的系统字段 ID。主表触发控制明细字段时，目标整列变化；明细字段触发本表同一行的目标字段时，按行变化。明细字段触发主表或其他明细表目标时，任意一行满足即可触发。复杂值类型先从现有字段和选项读回真实 ID，不猜测。

### 多个条件之间：任一 / 全部

界面上的「满足以下**任一**条件」= `OR`，「满足以下**全部**条件」= `AND`。在 config 顶层写 `detailType`：

```json
{ "detailType": "OR", "conditions": [ ... ], "actions": [ ... ] }
```

**不写这个键时由平台取自己的默认值** —— 设计器每次都显式发，所以缺省行为没有依据，命令不替平台决定。多条件时建议明确写。

### 布尔函数条件

与 `conditions` 二选一。**必须用** `e10-cli form formula functions --scene form-view-linkage` 查询当前环境可选函数；通用公式函数表包含该场景未开放的函数，不能据此选用，例如 `NOTEMPTY` 可改写为 `NOT(ISEMPTY(...))`，`DAYS` 在当前场景目录中不可选。新增、修改时 CLI 会用同一份场景目录预检查表达式中的函数；未列出的函数会在保存前报错，目录获取失败也会停止写入。引用已有 `formulaId` 时会读取其表达式与返回类型并做同样检查。自定义函数只有在该场景目录中出现时才能使用。可在配置中写 `"formula":"{主表.任务编号}==1111"` 并可选写 `formulaName`，CLI 解析字段引用，按 `Boolean` 返回类型保存公式，再把返回的公式 ID 绑定到显示属性联动。也可传已有公式的 `formulaId` 和 `formulaName`。公式保存若要求平台二次验证，命令会明确报错并停止，不会把未保存的公式当成成功；公式已保存而联动保存失败时应先核对公式 ID，避免重复创建。

## 生效维度（生效范围）

联动可以只对**某一种展示形态**生效。在 config 里用 `effect` 指定：

| 写法 | 含义 |
|------|------|
| 不写 | **当前表单**（最常见） |
| `"effect": "formLayout"` | 只对**某个表单布局**生效（布局 id 现查） |
| `"effect": { ... }` | 直接给 `{effectType, effectName, effectValue}`，自行指定 |

⚠ **布局维度的值要的是 `multipleLayoutId`，不是 `formLayout.id`** —— 同一张表上这两个值**相邻但不同**（例如 `…375` 与 `…376`）。给错了命令**不报错**，只是指向另一个布局，而且平台按这个 id 解析不出名字，回读时生效范围是个空白（`表单布局: `）。命令取的是前者，不用手填。

### 工作流表单那条路由的维度不一样

上面的表是 **eb 表**（`form linkage add`）的。**原生工作流程表单**（`wf-form linkage`）提供的是另外四种，写法也不同：

| 界面上的维度 | `effect` 写什么 | 取值 | 额外参数 |
|---|---|---|---|
| 当前表单 | 不写（缺省） | 表单 formId | — |
| **表单布局** | `"formLayout"` | **布局 id**（默认布局；可用 `"layoutId"` 指定别的） | — |
| **当前工作流** | `"workFlow"` | **流程 ID** | `--workflow-id` |
| **选择节点** | `"includeNode"` | **节点 ID** | `--workflow-id` + `"nodeId"`（可写节点名） |

```bash
e10-cli wf-form linkage <formId> "规则名" --workflow-id <流程ID> --config @cfg.json
```

```json
{ "effect": "workFlow",  "conditions": [ ... ], "actions": [ ... ] }
{ "effect": "includeNode", "nodeId": "1级审批", "conditions": [ ... ], "actions": [ ... ] }
```

**这条路由的 `refId` 始终是流程 ID**，是「这条联动挂在哪个流程上」，**不是**选项的取值 —— 给「选择节点」时选项取值是节点 ID，两者不同，别照着取值抄。流程表单 formId 与流程 ID 不是一回事，用 `workflow info <流程ID>` 可以反查。

选项的显示名里那个 `【V1】` 是**平台按活动版本自己加的**，写节点名进去它会补成「节点名【V1】」。

### actions（联动效果）

| 属性 | prop 值 | 效果 |
|------|---------|------|
| 隐藏 | `hide` | 字段隐藏不可见 |
| 隐藏行 | `hideLine` | 字段所在行整行隐藏（表格式布局；流式布局效果与隐藏相同；`hideRow` 兼容旧写法） |
| 显示（只读） | `show` | 字段显示但不可编辑 |
| 编辑 | `edit` | 字段显示且可编辑 |
| 只读 | `readonly` | 字段显示且不可编辑（同 show） |
| 必填 | `required` | 字段显示且必填（条件满足时必填） |

对象类型写在每个 action 的 `linkageObj`：

| 对象 | 写法与允许效果 |
|---|---|
| 字段 `field`（缺省） | `fields[]` 指目标字段；hide/show/edit/readonly/required/hideLine。明细目标加 `isDetail:true` |
| 选项 `option` | `fields[]` 指选项所属字段，`options[]` 逐项给 `fieldId/optionId/optionName`；hide/disabled |
| 明细表组件 `detail` | `fields[]` 指明细表组件 ID、名称与类型；hide/show/edit/readonly/hideLine |
| 布局组件 `layout` | `fields[]` 指布局组件 ID，CLI 从 `layout-targets` 查询并补全完整组件对象；hide/show/hideLine |

一条规则可含多个不同对象的 action。选项型对象包含单选框、复选框、下拉单选／多选、图片单选／多选；按平台的真实选项 ID 配置。布局组件以 `layout-targets` 实际返回的可选列表为准；当前抓包已确认折叠分组 `Fold` 的保存结构，其他类型是否可选取决于当前表单布局和平台返回值。

布局组件示例：先执行 `form linkage layout-targets <appId> <objId>` 取得分组的 `id`，再在配置中写：

```json
{
  "conditions": [{"fieldId":"updater","operator":"EQUAL","sourceContent":{"valueType":"LIST","optionValues":[{"valueType":"TEXT","textValue":"员工ID","name":"员工名"}]}}],
  "actions": [{"linkageObj":"layout","prop":"hideLine","fields":[{"id":"布局组件ID"}]}]
}
```

CLI 会根据 `id` 读取可选目标并使用平台返回的完整对象保存；不在可选列表中的组件会被拒绝。`hideLine` 在表格式布局隐藏所在行，流式布局与隐藏效果一致。

**优先级**：`hide` > `readonly` > `required` > `edit`

多个联动规则同时满足时，优先级高的生效。

## 示例

### 示例 1：优先级=高 时隐藏负责人字段

```json
{
  "conditions": [
    {
      "fieldId": "1290473132445114373",
      "operator": "EQUAL",
      "options": [{"optionId": "1290473132445114394", "content": "高"}]
    }
  ],
  "actions": [
    {
      "prop": "hide",
      "fields": [
        {
          "fieldId": "1290473132445114370",
          "name": "负责人",
          "dataKey": "fzr48cef",
          "fieldType": "Employee"
        }
      ]
    }
  ]
}
```

### 示例 2：金额 > 10000 时审批人变为只读

```json
{
  "conditions": [
    {
      "fieldId": "金额字段ID",
      "operator": "GREATER",
      "value": "10000"
    }
  ],
  "actions": [
    {
      "prop": "readonly",
      "fields": [
        {
          "fieldId": "审批人字段ID",
          "name": "审批人",
          "dataKey": "spr89abc",
          "fieldType": "Employee"
        }
      ]
    }
  ]
}
```

## 注意事项

1. **主表 vs 明细表**：主表触发字段可修改主表或明细字段（明细目标按整列变化）；明细表触发本表同一行字段时按行变化，触发主表或其他明细表目标时任意一行满足即可触发。
   目标落在明细表里时，`actions[].fields[]` 那个条目**必须带 `isDetail: true`**；不带的话这个目标会被当作主表字段提交
2. **表格布局限制**：通过隐藏行/列/单元格自定义属性隐藏的字段，无法通过联动显示出来；表格式布局中的“隐藏”只隐藏标题与字段组件，不隐藏单元格区域和样式
3. **明细表字段列隐藏**：需在明细表第一行配置操作按钮元素。明细表本体与表内字段的读写属性独立；即使所有列只读，明细表仍可能允许增删行。默认隐藏的明细字段不能由本行联动重新显示；默认显示的明细字段按行联动隐藏时，列标题仍可显示
4. **多规则冲突**：避免同一个触发字段或同一个目标字段出现在多个规则里。若规则 A 只看字段 A、规则 B 同时看 A 和 B，B 满足时可能覆盖 A；B 不满足时平台可能回落默认读写属性，而非继续执行规则 A
5. **默认属性**：字段的默认显示属性为设计器中设置的"读写属性"或"字段权限"
6. **目标字段 dataKey**：`form read` 不返回它，**留空即可** —— 平台按 `fieldId` 定位，`dataKey` 空着能正常建规则（已对照验证）。填上真值也行，但别为了凑它去猜；它**不是**某些报错的原因。
7. **Select 选项 ID**：必须用 `form read --app-id` 返回的真实 `valueKey`（自动生成的长 ID，如 `1294601918674214939`），不能用建表单时给的短 `valueKey`（如 `"GQ"` / `"5"`）

---

字段值带出与赋值（`relateFrom`、`form relate`、`form field-linkage`）见 [字段联动指南](guide-field-linkage.md)。
