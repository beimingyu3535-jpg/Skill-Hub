# 流程动作流指南

> 流程基础（建流程、节点、连线、审批人）见 `workflow/guide-workflow.md`，分支条件见 `workflow/guide-workflow-condition.md`。本指南专讲**节点提交事件**和**跨表单动作流**（本表数据 → 目标表 新增/更新/删除 记录）。
>
> **复杂动作流/多组件场景**（自然语言需求、Meeting/HttpCall/定时触发/条件分支等 20+ 组件）→ 走本 skill 内置的 `actionflows/` 子 skill（Python，**推荐**）：`python actionflows/scripts/actionflow_skill.py <命令> '{"json"}'`。本指南覆盖的简单动作流用 `e10-cli workflow action create` 即可。

## 节点提交事件（字段更新）

节点提交/到达时自动更新本表单字段值（actionType=0），如「审批状态置为审批中」。

> CLI 接受简化 JSON，内部自动构造 `saveAddActionList` 正确 payload（`targetValue`/`firstValue:"custom"`/`customValue`/`actionType:0`/`triggerType:"pre"` 等）。也支持直接传完整 `data:[]` 结构（高级用法）——**传入的 `data:[]` 行会自动归一化**，把 `action list-node` 的读回结果原样回传是安全的。
>
> **合并语义**：写入前先读回节点已有动作并归一化，再追加新动作写回——不覆盖已有动作。可与 `action create`/`message create`（actionType=2）安全混用同一节点。若节点已被写坏（读动作恒 500），CLI 会明确提示用 `delete-node` 删节点重建（API 无法修复）。
>
> **fieldId 会校验**：简化 JSON 的 `fieldId` 必须是流程表单里真实存在的字段，CLI 写入前反查表单字段校验，无效会报错并列出可用字段。**切勿用占位 fieldId**（如 `"1"`）——无效 fieldId 会被服务端存成空字段映射，之后任何合并写回都会把节点写坏（读恒 500，只能 delete-node 重建）。

**命令**：
```bash
e10-cli workflow save-action @action.json
```
> **只接 JSON 一个参数**：`workflowId` / `nodeId` 写在 JSON 内部，**不是位置参数**（区别于 `action create <wf> <node> ...`）。写成 `save-action <wf> <node> @file` 会报错。

### action.json 格式（常量赋值）

```json
{
  "workflowId": "1296243932023734272",
  "nodeId":     "1296243932023734278",
  "nodeName":   "上级审批",
  "fieldId":    "1296243579896791071",
  "fieldName":  "审批状态",
  "value":      "1296243644242280449"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| workflowId | 是 | 流程 ID |
| nodeId | 是 | 节点 ID（即 `objId`） |
| nodeName | 否 | 节点显示名（默认"节点"） |
| fieldId | 是 | 要更新的目标字段 fieldId |
| fieldName | 否 | 字段显示名（用于 `actionName` 展示） |
| value | 是 | 常量值。Text/Number 字段用实际值；Select 用 option 的 valueKey |
| trigger | 否 | 触发时机，默认 `"pre"`（到达节点时） |

**注意**：`workflow action create`（跨表单动作流）**不受此文档影响**，已通过 CLI 成功配置。

---

## 跨表单动作流（本表数据 → 目标表 新增/更新/删除 记录）

使用 `workflow action create` 一键完成动作流创建、设计保存和节点绑定：

```bash
# 1. 先查看目标表有哪些可用字段
e10-cli workflow action fields <targetTableId> <targetAppId>

# 2. 编写字段映射文件 mapping.json
# key = 源表字段ID，value = 目标表字段ID（支持 + / - 前缀做加减运算）
# {
#   "1293009997708083201": "1293010165253750785",     // 赋值
#   "1293009997708083202": "+1293010165253750786",    // 累加
#   "1293009997708083203": "-1293010165253750787"     // 扣减
# }

# 3. 创建动作流并绑定到节点
e10-cli workflow action create <workflowId> <nodeId> myAction \
  --target-table <targetTableId> \
  --target-app <targetAppId> \
  --mapping @mapping.json \
  --creator '{userid}' \
  --event arrive
```

参数说明：
| 参数 | 说明 |
|------|------|
| `--target-table` | 目标表单 tableId（数据写入哪个表） |
| `--target-app` | 目标表单所属应用 ID |
| `--mapping` | 字段映射 JSON：`{"源字段ID":"目标字段ID"}`，@ 开头表示文件路径 |
| `--constants` | 常量值 JSON：`{"目标字段ID":"固定值"}`，@ 开头表示文件路径 |
| `--formula` | 公式计算 JSON：`{"目标字段ID":{"op":"sub","fields":["源ID1","源ID2"]}}`，op: add/sub/mul/div |
| `--creator` | 数据创建者。传 `'{userid}'`（字面量）表示当前用户；指定特定用户传用户 ID 字符串，如 `--creator '2765550234448235905'` |
| `--event` | 触发时机：`arrive`(到达节点,默认) / `leave`(离开节点) / `delete`(删除) / `save`(保存) / `revert`(还原) / `pause`(暂停/启用) / `cancel`(撤销恢复) |

> **明细表字段映射（明细→明细）**：`--mapping` 里可直接放明细表字段，源明细表逐行写入目标明细表。语法不变，CLI 自动识别：目标字段属于哪张目标明细表、源字段属于哪张源明细表（源表单明细结构由 workflowId 自动反查，无需额外参数）。同一目标明细表的映射须来自同一张源明细表（作为该表「依据值」）。
> **限制**：明细映射仅支持 `--action-type add`（insert）；仅「源明细字段→目标明细字段」；明细目标字段不支持 `+`/`-` 前缀；`--constants` / `--formula` 只作用主表字段。**update/delete 含明细走 py 生成器**（结构含 basisValue/rowId 行匹配/updateAdd，CLI 不实现；py 的 action_eb_update 契约支持 detail + requestId 定位，生成后用 `action create --app-id` 绑节点，见下文「流程数据写入台账」④段）。

**更新示例**（按匹配字段定位目标记录后更新字段）：
```bash
# ① 按数据ID更新：--match-field 用 EBuilder 关联字段（其值=目标记录数据ID）
e10-cli workflow action create <workflowId> <nodeId> 更新合同台账 \
  --action-type update \
  --match-field <源EBuilder字段ID> \
  --mapping @mapping.json \
  --target-table <targetTableId> --target-app <targetAppId>

# ② 按字段匹配更新：--match-target 指定目标表匹配字段（走 updateData+filterInput，推荐）
e10-cli workflow action create <workflowId> <nodeId> 按合同编号更新 \
  --action-type update \
  --match-field <源合同编号字段ID> --match-target <目标合同编号字段ID> \
  --mapping @mapping.json \
  --target-table <targetTableId> --target-app <targetAppId>
```

> **update 定位方式（平台契约）**：`fieldUpdate`（按字段匹配更新）保存后右侧条件会被清空，**不可用**。推荐用 `updateData + filterInput`（`--match-target`，按「目标字段 = 源字段值」匹配）或 `opType=id + updateId`（`--match-field` 配 EBuilder 数据ID关联字段）。匹配字段不要选 `*_name`/`（名称）` 显示字段（那是标签文本不是真值）。

**常量值示例**（写入固定值而非映射字段）：
```bash
e10-cli workflow action create <workflowId> <nodeId> 更新流程状态 \
  --action-type update \
  --match-field <匹配字段ID> \
  --mapping '{"源字段ID":"目标字段ID"}' \
  --constants '{"目标状态字段ID":"已完成"}' \
  --target-table <targetTableId> --target-app <targetAppId>
```
`--constants` 格式：`{"目标字段ID": "固定值"}`，键是目标表字段ID，值是要写入的常量。

---

## 流程数据写入台账（数据来源落点）

**场景**：流程发起时写入目标台账、归档/退回时更新/删除台账记录（如"流程数据写入项目台账"，发起写入、归档更新、退回删除）。

**核心前提：目标台账必须建「数据来源」Flow 字段**（浏览-流程，`--sform-id` 指向流程绑定的表单 objId）。它存的是**流程实例 ID（requestId）**——add 时写入它，update/delete 靠它定位是哪次流程创建的记录，点击还能跳回流程。

```bash
# 台账建「数据来源」Flow 字段（只读，来源=项目立项流程）
e10-cli form add-field <台账objId> <appId> "数据来源" Flow --sform-id <流程表单objId>
```

**① add（发起写入）—— CLI 可配**：`--sysvar` 把流程实例 ID 写进台账「数据来源」字段：

```bash
e10-cli workflow action create <wf> <发起节点> 流程数据写入台账 \
  --target-table <台账objId> --target-app <appId> \
  --mapping @mapping.json \
  --sysvar '{"<台账数据来源字段ID>":"requestId"}'
```

**② update/delete（归档更新/退回删除）—— 走 py 生成器**：定位条件"**台账.数据来源 = 当前流程 requestId**"，CLI `--match-field` 只认流程表单字段、引用不了 requestId，**必须用 py 生成器**（`filterCondition` 动态右值引用 requestId，编译器自动判定为 `ApprovalData` 流程数据）：

```json
{
  "targetForm": {"groupId":"<appId>","id":"<台账objId>"},
  "person": {"id":"<人员id>","name":"<姓名>"},
  "opType": "updateData",
  "filterCondition": [
    {"field":"<台账数据来源字段ID>","operator":"=","value":{"type":"context","paramKey":"<component-context 返回的流程ID paramKey>","label":"流程ID"}}
  ],
  "mapping": {"<源paramKey>":"<目标字段ID>"}
}
```

> 调 py 前先 `eval "$(e10-cli auth export-weaver-env)"` 复用鉴权；`paramKey` 必须用本次 `component-context` 返回的原始键，不要写死 `ApprovalData.*` 路径。也可直接给 py 下自然语言（"流程归档时按数据来源更新台账，项目状态置为立项"）。

**④ py 生成后绑到节点**：py `generate` 只暂存设计、返回 `appId` + 设计器链接，**不自动绑节点**。用 CLI `action create --app-id` 复用模式把已生成的动作流绑到流程节点：

```bash
# py 返回的 appId 拿来绑节点（跳过创建，只做 saveAddActionList 绑定，合并节点已有动作）
e10-cli workflow action create <wf> <归档节点> 归档更新台账 \
  --app-id <py返回的动作流appId> --event leave
#   可加 --condition "form:<字段id>:等于:立项" 条件触发、--condition-relation AND/OR
```

> 这是 py（复杂设计）与 CLI（节点绑定）的衔接：py 生成 requestId 定位/回写/明细 update/多组件等 CLI 配不了的设计 → CLI `--app-id` 绑到节点生效。**py 暂存的 appId 能否直接绑节点需实测一次**（若暂存态不可绑，先在设计器发布再拿 appId 绑）。

**③ add 回写 dataId（源表存台账记录 ID）**：若后续 update/delete 想用"源表字段 = 台账 dataId"定位，py 的 `workflow-fields` 命令提供"回写数据ID对应字段"候选查询。复杂动作流（requestId 定位/回写/多组件）统一走 py 生成器。

---

## 关联 EBuilder 更新目标表数据（跨表更新）

**场景**：表A（带流程）通过 EBuilder 关联字段指向表B，流程到节点时动作流更新表B的目标记录字段。

**机制**：表A 的 EBuilder 关联字段的值 = 表B 记录的数据ID。动作流 `--match-field=<表A的EBuilder字段>`，opType `id`（按数据ID更新）→ 直接用关联值定位表B记录，无需字段值匹配。

### 建两张表

表B「客户台账表」（被更新）：客户名称(Text)、最后拜访日期(Date)、累计拜访金额(Money)
```json
[
  {"componentKey":"Text","fieldName":"客户名称"},
  {"componentKey":"Date","fieldName":"最后拜访日期"},
  {"componentKey":"Money","fieldName":"累计拜访金额"}
]
```

表A「拜访登记表」（带流程）：拜访日期(Date)、拜访金额(Money)、客户关联(EBuilder→表B)
```json
[
  {"componentKey":"Date","fieldName":"拜访日期"},
  {"componentKey":"Money","fieldName":"拜访金额"},
  {"componentKey":"EBuilder","fieldName":"客户关联","sformId":"<表B objId>","dataTitle":"客户名称"}
]
```
> EBuilder 字段：`sformId`=目标表 objId，`dataTitle`=目标表显示字段（填字段名或 fieldId，CLI 自动解析）。

### 动作流命令

先 `form read` 拿两张表的 fieldId，写 mapping.json：
```json
{
  "<表A拜访日期fieldId>": "<表B最后拜访日期fieldId>",
  "<表A拜访金额fieldId>": "+<表B累计拜访金额fieldId>"
}
```
> mapping 目标ID 不加前缀=**直接赋值**（源值原样写入）；加 `+`=累加，`-`=扣减。直接赋值时 CLI 按目标字段类型（日期/金额/文本等）自动匹配，不用管 fieldType。

```bash
e10-cli workflow action create <workflowId> <nodeId> 更新客户台账 \
  --action-type update \
  --target-table <表B objId> --target-app <appId> \
  --match-field <表A客户关联 fieldId> \
  --mapping @mapping.json \
  --creator '{userid}' --event leave
```
> `--match-field` = 表A 的 EBuilder 关联字段（其值=表B记录数据ID）。`--event leave` 离开节点时触发。

---

**公式计算示例**（加减乘除多字段运算）：
```bash
e10-cli workflow action create <workflowId> <nodeId> 计算退款差额 \
  --action-type update \
  --match-field <匹配字段ID> \
  --formula '{"目标金额字段ID":{"op":"sub","fields":["金额1字段ID","金额2字段ID"]}}' \
  --target-table <targetTableId> --target-app <targetAppId>
```
`--formula` 格式：`{"目标字段ID":{"op":"add|sub|mul|div","fields":["源字段ID1","源字段ID2"]}}`。mapping / constants / formula 可混合使用。

**删除示例**（按匹配字段删除目标记录）：
```bash
e10-cli workflow action create <workflowId> <nodeId> 删除关联记录 \
  --action-type delete \
  --match-field <源表单字段ID> \
  --mapping '{"源字段ID":"目标字段ID"}' \
  --target-table <targetTableId> --target-app <targetAppId>
```

CLI 内部自动完成：
1. `POST application/save` → 创建动作流容器
2. `POST getEbField` → 校验目标字段
3. `POST saveDesign` → 保存设计（触发事件+动作+字段映射）
4. `POST saveAddActionList` → 绑定到流程节点

> **绑定是合并而非覆盖**：第 4 步会先 `getAddActionDataList` 读回节点已有动作，把回读行**归一化回写入格式**（回读格式 `async:false`/`fieldMappingData` 嵌套/`actionData` 缺 `paramsSet`，原样回写会让节点永久 500），再追加新动作写回。所以：
> - 同一节点可**安全混用** `save-action`（actionType=0 常量赋值）+ `action create` / `message create`（actionType=2 动作流）
> - 多次绑定不会覆盖已有动作，只追加
> - 若某节点已被旧版 CLI 写坏（读 500，API 不可恢复），只能 `delete-node` 删节点重建

动作流管理：
```bash
e10-cli workflow action get <sceneId>           # 查看动作流设计
e10-cli workflow action disable <appId> <name>  # 禁用动作流
e10-cli workflow action delete <appId> <name>   # 删除动作流（需先禁用）
```

> **支持的动作类型**：
> - `add`（默认）：`ActionEbAdd`，新增表单数据，opType=insert
> - `update`：`ActionEbUpdate`，更新已存在的记录
> - `delete`：`ActionEbDelete`，删除记录
>
> `update`/`delete` 需要额外参数：
> | 参数 | 说明 |
> |------|------|
> | `--action-type update` | 指定为更新动作 |
> | `--action-type delete` | 指定为删除动作 |
> | `--match-field <源字段ID>` | 用于匹配目标表已有记录的字段（update/delete 必填） |
>
> **注意**：动作流创建后需启用相关节点事件。

---

## 条件性动作流（同一节点按条件走不同动作）

一个节点可挂**多个动作流，各自带触发条件**——提交时只有条件命中的动作才执行。典型场景「合同变更」：变更类型=续期 → 插入台账；变更/终止 → 更新+插入。

```bash
# 动作A：仅当 变更类型=续期 时执行（新增台账记录）
e10-cli workflow action create <wf> <node> 合同续期写台账 \
  --target-table <台账表id> --target-app <appId> \
  --mapping @mapping.json --event leave \
  --condition "form:<变更类型字段id>:等于:续期"

# 动作B：仅当 变更类型=变更 时执行（更新台账）
e10-cli workflow action create <wf> <node> 合同变更更新台账 \
  --action-type update --match-field <匹配字段id> \
  --target-table <台账表id> --target-app <appId> \
  --mapping @mapping.json --event leave \
  --condition "form:<变更类型字段id>:等于:变更"
```

参数说明：
| 参数 | 说明 |
|------|------|
| `--condition` | 触发条件规则，可多个（同一条件内多规则）。格式同 `condition add` 的 `--rule`：`"来源:字段:操作:值[:值2]"`，来源=form 用字段ID / system 用系统字段中文名（如 `--condition "form:123456:等于:续期" --condition "system:流程标题:包含:合同"`） |
| `--condition-relation` | 条件内多条规则关系：`AND`(默认) / `OR` |
| `--condition-name` | 条件名称（默认 `节点名-条件`） |

**机制**：CLI 内部两步完成——① `saveCondition`（source=19, sourceId=-1）保存条件规则拿到 `conditionKey`；② `saveAddActionList` 绑定时动作项带 `conditionKey` + `hasRule:true`。多次 `action create` 是**追加合并**，同一节点可安全挂多个条件动作流。

> **验证**：`workflow action list-node <wf> <node>` 会标注 `⚠️条件` 的动作为带规则动作。条件内容在流程设计器节点 → 提交事件 → 动作的规则图标里查看。

---

## 角色管理

```bash
e10-cli role list                              # 查看角色树
e10-cli role create <name> --parent <id> --code <code> --remark <text>
e10-cli role delete <ids...>                   # 删除角色（可多个）
e10-cli role add-member <roleId> <keyword>     # 搜索人员添加到角色
```
