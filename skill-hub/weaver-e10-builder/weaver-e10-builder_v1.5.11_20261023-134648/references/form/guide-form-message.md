# 消息提醒（表单数据提醒）

表单数据发生**新建 / 修改 / 删除**时，按配置把消息推给指定的人。位置在 **表单模型 → 消息提醒 → 表单数据提醒**（同一页面还有个「动作流提醒」页签，是另一条链路）。

一条提醒由这几样组成：**触发时机 + 推送渠道 + 标题内容 + 落地页 + 提醒对象**，整体可**启用 / 停用**。

## 命令

| 命令 | 用途 |
|---|---|
| `form message list <appId> [--obj-id <objId>] [--keyword <kw>]` | 列出提醒。不传 `--obj-id` 就是把整个应用的列出来 |
| `form message get <appId> <triggerId>` | 看单条，含**推送渠道**与提醒对象 |
| `form message add <appId> <objId> --name <名称>` | 新建 |
| `form message edit <appId> <triggerId> [...]` | 修改，没传的项保持原值 |
| `form message delete <appId> <triggerId>` | 删除（不可逆） |
| `form message enable \| disable <appId> <triggerId>` | 启用 / 停用 |

`get` / `edit` / `delete` / `enable` / `disable` 的 `--obj-id` 可以省 —— 不传会自动反查这条提醒挂在哪张表单上。

### `add` / `edit` 的选项

| 选项 | 说明 |
|---|---|
| `--type <类型>` | 触发时机：`新建` / `修改` / `删除`，逗号分隔，也可以写 `all`。缺省 `all` |
| `--channels <渠道>` | 推送渠道：`im`（站内）/ `cloud-bridge`（云桥）/ `email`（邮件）/ `sms`（短信），逗号分隔，也可以写 `all`。**缺省只发 `im`** —— 不会替你打开短信 |
| `--title` / `--content` | 提醒标题与内容。纯文本会自动包成富文本；不传时标题取提醒名称、内容按触发时机生成一句话（如「数据新建、修改了」） |
| `--pc-link` / `--mobile-link` | 点开提醒后的落地页，缺省是这条记录的表单卡片页 |
| `--rule <spec>` | 提醒对象，可重复（写法见下） |
| `--rule-json '<json>'` | 提醒对象原始报文，逃生口 |
| `--disabled` | 建成即停用（`edit` 用 `--enable` / `--disable`） |

## 提醒对象怎么写

五类：`user` 人员、`dept` 部门、`role` 角色、`company` 分部、`matrix` 矩阵。

写法是 `<类型>:<值>[,name=<显示名>][,extra=0|1]`：

- **`<类型>:<名字>`** —— 工具按名字去查。**同名多条会报错并列出候选（带 ID）**，不会替你挑一条，免得配错人还看不出来。
- **`<类型>:<ID>,name=<名字>`** —— 名字有歧义、或手上只有 ID 时用这个：`<值>` 直接当 ID 用，不查。

`extra` 是组织范围上的附加项 —— 页面上部门 / 分部的提醒对象显示成「营销部:本部门含兼职人员」就是它。部门 / 分部缺省开、人员 / 角色 / 矩阵缺省关，需要时显式覆盖。

### 矩阵提醒对象（`matrix`）

```bash
form message add <appId> <objId> --name 有新数据了 --type 新建 --channels im \
  --rule matrix:门店经理矩阵
```

矩阵那条报文的**键集合与其余四类完全不同**（真机报文坐实）：只有 `selectedType` / `containExtra` / `name` /
`jobLevelText` / `jobLevelTextSpan` / `matrixValueRelation` / `matrixConditionData` / `ruledetail` / `id`，
**没有** `levelScope` / `fieldtype` / `roleLevel` / `relation` 那一套，而且**不带 `ruletype`** —— 平台靠
`selectedType='matrix'` 认它。工具会按矩阵的**值字段**自动构造 `matrixValueRelation`
（决定用哪一列匹配当前用户），矩阵没配值字段时直接报错。

> ⚠ **矩阵的「条件」这一层暂时配不了**。设计器能给矩阵提醒对象再加条件（`matrixConditionData`），
> 但那个对话框里的右值是一种新形态（`type:"custom"` + 一组选中的对象数组 + `customSelect`），
> CLI 还没有对应的构造；报文里这个键会发空串。要带条件的，先去设计器里配。

```
form message add <appId> <objId> --name 有新数据了 \
  --type 新建 --channels im,email \
  --rule user:任来仪 \
  --rule dept:营销部 \
  --rule role:会议管理员
```

## 几个容易踩的点

- **列表是应用级的**：这条接口按应用列，`--obj-id` 是命令在**本地按表单收口**（平台不认那个过滤参数，传了也照回全应用）。
- **渠道勾选要单条看**：列表和详情返回里都不带渠道，`form message get` 会额外读一次补上。
- **停用不等于删除**：`disable` 只是不再推，配置留着；`delete` 才是真的没了。
- **修改是整份保存**：`edit` 先读回现有配置再合并你改的项，**没传的项不会被清空**。提醒对象默认保持原样，要整份替换就传 `--rule`，要清空传 `--clear-rules`。
- **提醒名称**就是列表里显示的那个名字，建的时候起的 `--name` 别随手写。
