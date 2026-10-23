# e10-cli 命令参考

> **所有系统交互统一使用 `e10-cli`**。auth 文件自动查找，也可 `--auth <path>` 指定。加 `--json` 输出 JSON 格式。

---

## 工具

| 命令 | 说明 |
|------|------|
| `e10-cli docx read <文件>` | 解析 Word 文档为 markdown + 提取图片到 `_images/`。**禁止自己写 python-docx 脚本** |

---

## Ecode 项目操作

| 命令 | 说明 |
|------|------|
| `e10-cli project create <name> [desc]` | 新建 Ecode 项目（名称自动追加时间戳） |
| `e10-cli project import <projectId> <zip> --main-url <url>` | 导入 zip 包，`--main-url` **必填** |
| `e10-cli project tree <parentId>` | 查看目录结构 |
| `e10-cli project read <fileId>` | 读取代码文件内容 |
| `e10-cli project update <fileId> <content>` | 更新代码文件（content 以 `@` 开头则为文件路径） |
| `e10-cli project create-file <name> <parentId> [type]` | 新建代码文件（默认 js） |
| `e10-cli project create-folder <name> <parentId>` | 新建文件夹 |
| `e10-cli project delete-file <fileId>` | 删除代码文件 |
| `e10-cli project delete-folder <folderId>` | 删除文件夹（= 删除应用） |

- 导入成功后会在 Ecode 项目下生成应用文件夹
- 二次导入之前先删掉旧应用文件夹（通过 `e10-cli project tree` 找到 folderId）

---

## Ebuilder 应用 & 表单

| 命令 | 说明 |
|------|------|
| `e10-cli app create <name> [desc]` |
| `e10-cli form read <objId> [--app-id <appId>] [--out <file>]` | 读取表单字段。`--app-id` 含明细表字段+Select/RadioBox/CheckBox 选项；`--out fields.json` 写 UTF-8 JSON（推荐，机器可读）。旧版 `[dir]` 参数写 memo.md，已过时 |
| `e10-cli form read <objId> --app-id <appId> --out fields.json` | 读取字段含选项（Select/RadioBox/CheckBox 自动带 options）。**含明细表字段**，配动作流/联动拿明细 fieldId 用这个 |
| `e10-cli form list <appId>` | 列出应用下的所有表单 |
| `e10-cli form create <appId> <name> <dir> --fields @<json文件>` | 创建表单。`--fields` **必填**。支持 DetailTable(嵌套formFields)、EBuilder(sformId+dataTitle)、relateFrom(联动)。fields.json 字段可带 `"required":true`/`"readOnly":true` 直标（写进布局 comps）。**建表后自动加台账菜单**（VIEWPORT），`--no-menu` 关闭 |
| `e10-cli form add-field <objId> <appId> <name> <type> [title]` | 添加字段。`<type>`=componentKey（Text/Select/Employee/Money/DetailTable 等同 form create）；`[title]` 字段显示名，不传同 name。Select 类型需单独 `field-options` 配选项。**`--sub-form-id <明细表subFormId>` 在明细表里加字段**（自动重新布局）。Number 类型：**`--percent` 百分比显示**（numberType=percentage，缺省 1 位小数）、**`--default <值>` 默认值**（如 `--default 1000` 工时单价默认 1000）、`--precision <n>` 精度。**EBuilder/Flow 类型**：`--sform-id <目标表单objId>`（EBuilder 表关联 / Flow 浏览-流程字段，数据来源=浏览流程） |
| `e10-cli form edit-field <objId> <appId> <fieldId>` | 编辑字段属性。`--title`/`--required`/`--no-required`/`--sform-id`(改EBuilder关联)/`--relate-from`(值带出) |
| `e10-cli form serial-mark <objId> <appId> <fieldId> --prefix "XM-" [--year] [--serial 3] [--sep "-"] [--clear]` | 复杂编号（年份编号）：文本字段上配编码段（固定内容+年+分隔符+流水号），生成如 `XM-2026-001`。`--year` 年份；`--serial` 流水位数（seqAlone=1 补零）；`--sep` 年→流水分隔符（默认"-"）；`--clear` 解除。被编码字段平台自动只读 |
| `e10-cli form field-options <objId> <appId> <fieldId> --options @<json> [--default <key>]` | 设选项/默认值。options.json: `[{"name":"选项名","valueKey":"可选"}]`；`--default` 用平台生成的长 valueKey（`form read --app-id` 获取），不是 name |
| `e10-cli form linkage add <appId> <objId> <name> --config @<json>` | 添加字段显隐联动规则 |
| `e10-cli form relate <appId> <objId> <目标字段> --from <源字段>` | **HRM 值带出联动**：源字段为表内 Employee（人员）或 Department（部门）类型，换源自动填目标字段（换申请人→填邮箱/工号/部门；换所属部门→填部门编号/上级部门）。`--key` 从平台清单校验（默认 Employee=department、Department=name），`--title` 指定显示名（默认属性中文名）。详见 `form/guide-form-linkage.md` |
| `e10-cli form delete <objId> <appId>` | 删除表单 |
| `e10-cli form permission <list\|add\|remove\|rebuild> <objId> <appId>` | **表单数据权限**（谁能创建/查看/编辑/删除该表单数据）。`add --org-type <all/role/department/company/employee/group/post> --org-id <id> [--right-type 0创建/1查看/2编辑/3删除/5归档查看/6归档编辑/7归档删除] [--creator-related 0本人/1上级/5本岗位]`；all 类型 org-id 自动 0；添加后若提示 isShowRebuild=2 用 `rebuild` 重构。`list` 查看、`remove <id>` 删 |
| `e10-cli form list-view <objId> <appId>` | 查看台账/数据列表（获取 viewId 用于菜单配置） |
| `e10-cli form list-columns <objId> <appId> <listId> [--add <fieldId>] [--remove <fieldId>] [--pc-only]` | 查看/调整台账**显示列**。不加参数列出当前列；`--add` 追加字段列、`--remove` 移除。listId 用 `list-view` 的列表视图 ID。**保存时自动保留移动端配置**（`--pc-only` 目标明确只用 PC 时才允许移动端配置缺失） |
| `e10-cli form list-unit <objId> <appId> <listId> <fieldId> <后缀> [--prefix <前缀>] [--clear] [--pc-only]` | 设置台账列显示**单位**（后缀/前缀）。平台无字段级单位属性，靠列表列配置 `showTrans.ruleConfig.suffix/prefix` 实现。如 `form list-unit ... <fieldId> "（元）"` 让列显示单位；`--clear` 清除 |
| `e10-cli form list-click <objId> <appId> <listId> <fieldId> [--target <formObjId>] [--clear] [--pc-only]` | 设置台账列**点击跳转**（eventGroup/NewPage）：点该列数据跳目标表单视图。缺省跳本表单；`--target` 跳别的表单；`--clear` 移除。点项目名称跳台账视图 |
| `e10-cli form ebuilder-columns <objId> <appId> <fieldId> [字段名/ID...] [--clear]` | 设置 EBuilder 关联字段的**浏览显示列**（存在字段配置 `ffDisplayColumns:{id,name}[]`）。**缺省查看**：列出当前显示列 + 目标表单全部**业务字段候选**（系统字段已自动过滤，不设显示列时浏览走平台默认列会带系统字段）；**传目标表业务字段名/ID 设置**，系统字段会被拦截提示"系统字段不能设为显示列"；`--clear` 清空。关联浏览显示哪些字段（只留业务字段） |
| `e10-cli form ebuilder-scope <get\|set\|clear> <objId> <appId> <fieldId>` | **浏览数据定义 → 数据范围设置**（关联浏览字段，限定被关联数据须满足条件才可选，如关联客户只选"客户状态=启用"的）。走 `browserDataScope` 接口（独立于字段布局）。`set --rules '[{"field":"客户状态","operator":"eq","value":"启用"}]'`（选项类 value 用选项名，CLI 自动解析 valueKey）；`--logic and/or` 多规则关系；`--fill-null` 关联字段为空时填充；`get` 读已设条件；`clear` 清空。**这是关联浏览筛选的正解**，旧 `ebuilder-filter` 走 layout/save 不被设计器识别 |
| `e10-cli form validate list <objId> <appId>` | 查看表单**查重规则**（字段重复校验，多字段 AND）。`add <objId> <appId> <字段名...> [--help 提示] [--remind]` 新增（缺省禁止提交 NOSUBMISSION，`--remind` 仅提醒）；`delete <objId> <appId> <ruleId>` 删除。项目名称重名/工时日期重复不允许 |
| `e10-cli form list-search <objId> <appId> <listId> [--add <fieldId>] [--quick <fieldId>] [--remove <fieldId>] [--pc-only]` | 查看/配置台账**搜索条件**。`--add` 进搜索面板、`--quick` 加顶部快捷筛选、`--remove` 移除。**自动保留移动端配置** |
| `e10-cli form list-sort <objId> <appId> <listId> [--field <fieldId>] [--order ASC\|DESC] [--clear] [--pc-only]` | 查看/配置台账**排序**。`--field` 设置排序字段、`--clear` 清除。**自动保留移动端配置** |
| `e10-cli form list-stats <objId> <appId> <listId> [--add '<json>'] [--remove <statId>] [--pc-only]` | 查看/配置台账**顶部统计**。`--add '{"fieldId":"...","type":"sum","name":"合计"}'`（type: sum/count/avg/max/min）、`--remove` 移除。**自动保留移动端配置** |
| `e10-cli form view list <objId> <appId> [--with-comps]` | 列出表单全部视图。`--with-comps` 额外拉每个视图布局 comps 数、标出空视图（NList 数据视图会显示「读取失败」，正常） |
| `e10-cli form view populate <objId> <appId> <viewId>` | 把已有字段按布局类型填入新增的 formView（视图为空时用这个填充） |
| `e10-cli form layout read <objId> <appId> [--view-id <id>]` | 读表单布局结构（comps 坐标/只读）。不传 `--view-id` 读默认布局，传则读指定视图 |
| `e10-cli form data add <objId> <json>` | 写入表单数据（`@` 开头为 JSON 文件路径）。格式：`{"字段fieldId":"值"}`，Select 用 valueKey，Employee/Department 用用户/部门 ID，FileComponent 逗号分隔 fileId。详见 `form/guide-form-data.md` |
| `e10-cli form data list <objId>` | 查询表单数据 |
| `e10-cli form data delete <objId> <dataId>` | 删除一条表单数据 |

### 表单按钮

| 命令 | 说明 |
|------|------|
| `e10-cli form button list <objId> <appId>` | 列出所有按钮 |
| `e10-cli form button add <objId> <appId> <name> --url <url> --open-type <1\|2\|3>` | 添加自定义按钮（open-type: 1=弹窗,2=新页面,3=当前页） |
| `e10-cli form button toggle <objId> <appId> <buttonId>` | 启用/禁用按钮 |
| `e10-cli form button info <objId> <appId> <buttonId>` | 查看按钮详情 |
| `e10-cli form button sort <objId> <appId> <sourceId> <targetId>` | 调整按钮排序 |
| `e10-cli form button delete <objId> <appId> <buttonId>` | 删除按钮 |

> **除非用户明确要求，否则不要往表单写入任何数据。** 表单创建完成后只需确认字段正确即可，不要自动插入测试数据。

> **创建表单流程**：
> 1. 读取 `references/form/guide-create-form.md` 了解字段类型和参数格式
> 2. 与用户确认所有字段名和字段类型
> 3. 将字段定义写入临时 JSON 文件（格式：`[{"componentKey":"Text","fieldName":"姓名"},...]`）
> 4. 执行 `e10-cli form create ... --fields @<临时文件路径>`
> 5. 涉及人员的字段统一使用 Employee 类型，不要用 Text

---

## 角色

| 命令 | 说明 |
|------|------|
| `e10-cli role list` | 列出所有角色（树形结构，含层级关系） |
| `e10-cli role create <name>` | 创建角色，`--parent <id>` 指定父角色，`--code` 编码，`--remark` 备注 |
| `e10-cli role delete <ids...>` | 删除角色（可多个） |
| `e10-cli role add-member <roleId> <keyword>` | 搜索人员并添加到角色 |

## 流程

| 命令 | 说明 |
|------|------|
| `e10-cli workflow create <appId> <formObjId> <name> [desc]` | 创建流程，自动设置所有人可发起。**建流程后自动加发起菜单**（LAYOUT，指向表单新建页 `/sp/ebdfpage/card/1/<formObjId>/0`，点开即触发流程），`--no-menu` 关闭 |
| `e10-cli workflow list <appId>` | 列出应用下的所有流程 |
| `e10-cli workflow search` | 通用搜索流程（不依赖 appId）。`--name`/`--id`/`--type`/`--belong` |
| `e10-cli workflow nodes <workflowId>` | 查看流程节点详情（名称、类型、操作者、连线含 linkId） |
| `e10-cli workflow nodes <wf> --mode list` | 列表视图：展示全节点含 nodeAttr、合流方式（比 chart XML 更全） |
| `e10-cli workflow set-operator <wf> <node> [keyword]` | 设置节点操作者。`--type user`(指定人) / `role`(指定角色) / `dept`(指定部门) / `position`(指定岗位) / `all`(所有人) / `free`(自由选择) / `superior`(发起人上级) / `prev-node`(上一节点) / `form`(表单相关人员) / `matrix`(矩阵对应,需 `--matrix-id` `--value-config-id` `--matrix-rule`)。`--sign-order` 会签/非会签/竞签/依次处理/抄送/抄送需批注（概念见 guide-workflow）。**一个节点多人用逗号分隔 keyword**（如 `"区域经理,部门领导"`）；默认每次全量重建操作者组（先清空再新建），重复设置不堆积。**多操作者组叠加（如「部门领导矩阵 + 门店经理矩阵」双组会签）：先用 set-operator 配第一组，再用 `--append` 配第二组**，`--append` 不清空已有组，两组合起来就是双矩阵会签 |
| `e10-cli workflow generate-link-id <wf>` | 生成新连线 ID |
| `e10-cli workflow add-node <wf> <type> <name>` | 添加节点（列表 API）。`<type>`: 0=发起 1=审批 2=确认 3=归档 5=投递 7=自动处理 8=等待 / forkstart/forkend/forkmiddle。**结束节点=归档节点（type=3）**。`--node-attr` 节点属性；合流点支持 `--merge-type`（0=全部/1=指定/2=数量/3=比例）、`--merge-num`、`--branch-nodes` |
| `e10-cli workflow rename-node <wf> <nodeId> <name>` | 重命名节点（saveNodeSetForm API） |
| `e10-cli workflow add-link <wf> <from> <to> <label>` | 一键添加连线（列表 API）。`--reject` 退回 / `--default` 默认出口 |
| `e10-cli workflow add-links <wf> @links.json` | 批量添加连线（列表 API，一次保存）。格式：`[{"from":"节点ID","to":"节点ID","label":"标签","reject":true,"default":true}]` |
| `e10-cli workflow link-list <wf>` | 查看出口列表（含默认/退回/条件标志）。`--node-id` 过滤单节点 |
| `e10-cli workflow link-save <wf> @datas.json` | 修改/删除出口（列表方式）。`--delete-rows`/`--changed-link-ids`/`--update-row-ids` |
| `e10-cli workflow link-rename <wf> <linkId> <名称>` | 重命名出口（连线名称）。linkId 用 link-list 查看。实现：读出口列表 → 改 linkName → saveNodeLinkEditTable(updateRowIds) |
| `e10-cli workflow numbering read <wf>` | 查看流程编号规则 |
| `e10-cli workflow numbering enable <wf>` | 启用流程编号（`--off` 关闭）。方案要求"流程有编号"时必做，平台默认不自动启用 |
| `e10-cli workflow numbering add-component <wf> --type fixed\|date\|field --value <text> --format <yyyyMMdd> --field-id <id>` | 添加编号组成项：fixed=固定内容 / date=日期 / field=表单字段 |
| `e10-cli workflow numbering reserve <wf> <count> [--prefix]` | 预留编号 |
| `e10-cli workflow node validate <wf> <nodeId> --rule "主题字段 操作 值字段或字面值"` | 节点提交校验（智能审批规则，提交时拦截）。值可以是**字段**（字段 vs 字段）或**字面值**（字段 vs 常量）；主题字段支持**跨表**——用「明细表名.字段名」定位明细字段做主子表校验：`"请假时长 小于 4"`、`"行程明细.行程开始时间 等于 出差开始日期"`（明细字段=主表字段）。`--name` 规则名；`--disable` 关闭；`--view` 查看 |
| `e10-cli workflow node menu <wf> <nodeId>` | 查看/切换节点操作菜单。`--toggle <menuId>` 切换启用状态 |
| `e10-cli workflow node reject <wf> <nodeId>` | 配置节点退回设置。`--remind`/`--type`/`--checked-node`/`--submit-type` |
| `e10-cli workflow node timeout <wf> <nodeId>` | 配置节点超时处理。`--time-type`/`--time-value`/`--flow-type`/`--remind-type` |
| `e10-cli workflow node field-permission get <wf> <nodeId>` | 查看节点字段权限（各字段 显示/隐藏）。表单字段在节点上可见与否 |
| `e10-cli workflow node field-permission set <wf> <nodeId> --hide <字段...>` | 设置节点字段显示/隐藏。`--hide 字段名/ID` 隐藏、`--show` 显示；可多个，已设权限则更新、未设则新建 |
| `e10-cli workflow node sign <wf> <nodeId>` | 节点签字意见必填（退回时必填意见等）。缺省查看；`--all-required` 全部必填、`--none-required` 全部不必填、`--select "退回,加签"` 指定操作类型必填（按 mustInputDto=2 + 选中操作类型 id）。`getSignConfigForm` 枚举操作类型 |
| `e10-cli workflow setting title <wf>` | 流程标题规则（发起后标题按规则生成，如"发起人-提交日期-客户名称"→真实数据）。缺省列出可用变量（发起人/部门/日期/表单字段）；`--rule "发起人\|提交日期\|客户名称"` 竖线分隔字段名设置；`--sep <分隔符>` 默认 `-`；`--disable` 关闭自动生成（标题回退流程名+系统默认）。占位符 `$code$`，平台发起时替换为真实值 |
| `e10-cli workflow setting submit <wf>` | 提交确认设置。`--confirm`/`--node-range`/`--show-way` |
| `e10-cli workflow setting sign <wf>` | 签字意见设置。`--show-order`/`--inform-range` |
| `e10-cli workflow setting comment <wf>` | 评论功能开关。`--enable` |
| `e10-cli workflow setting batch <wf>` | 批量操作设置。`--enable-batch`/`--enable-turn-todo`/`--enable-consult`/`--enable-reject` |
| `e10-cli workflow setting auto <wf>` | 自动处理设置。`--enable`/`--way`/`--follow-type` |
| `e10-cli workflow setting other <wf>` | 其他设置。`--message-op`/`--auto-save`/`--switch-identity` |
| `e10-cli workflow advanced doc <wf>` | 流程存档设置。`--enable`/`--dir-select`/`--doc-types` |
| `e10-cli workflow advanced schedule <wf>` | 定时触发审批。`--enable`/`--frequency`/`--begin-date`/`--time`/`--weekday-only`/`--sms`/`--email`/`--message`/`--limit-creator` |
| `e10-cli workflow advanced schedule-range <wf>` | 定时触发人员范围。`--list`/`--add`/`--delete` |
| `e10-cli workflow delete <workflowId>` | 删除流程。`--with-form` 同时删除关联表单 |
| `e10-cli workflow delete-link <wf> <linkIds...>` | 删除连线（列表 API，可多个）。自动清理关联节点 |
| `e10-cli workflow delete-node <wf> <nodeId>` | 删除节点（自动清理关联出口）。`--bridge` 桥接上下游 |
| `e10-cli workflow save-layout <wf> @xmlfile` | 保存完整流程图 XML（浏览器 mxGraph 格式：数字 cell id + nodeId/linkId）。服务器只认浏览器格式，勿转 node_X。新增节点/连线会自动注入 flag="add" |
| `e10-cli workflow auto-layout <wf>` | **节点自动排版**（分层布局，全量重排坐标）。`--direction ltr/ttb`(默认ltr)、`--gap-x/--gap-y` 间距、`--dry-run` 只算不打回、`--out` 配合 dry-run 输出新 XML。忽略退回线分层，分支自然融入 |
| `e10-cli workflow condition add <wf> <sourceId> <nodeId> <name> --rule "..."` | **简化语法**添加条件。`--rule "system:流程标题:包含:关键词"` 或 `--rule "form:字段ID|字段名|dataKey:大于:1000"`（fieldId/名/dataKey 均可匹配，原生流程表单用 dataKey 最稳）。按 fieldType 自动判族校验算子。支持 `--relation AND/OR`。详见 `workflow/guide-workflow-condition.md` |
| `e10-cli workflow save-condition @jsonfile --app-id <appId>` | 保存条件规则（原始 JSON）。CLI 自动生成 ID 并绑定到连线 |
| `e10-cli workflow condition list <wf>` | 列出工作流下所有连线绑定的条件（连线名 + 条件名 + 表达式 + mapId），支持 `--name` 过滤 |
| `e10-cli workflow condition get <wf> <id>` | 查看单个条件详情。`<id>` 可用 conditionKey / mapId / conditionId |
| `e10-cli workflow condition delete <wf> <id> [--link-id <linkId>] [--node-id <nodeId>]` | 删除条件（删定义 + 解绑连线）。`<id>` 同 get |
| `e10-cli workflow set-link-condition-key <wf> <link> <key> <node>` | 绑定条件 Key 到连线 |
| `e10-cli workflow save-action @jsonfile` | 加节点提交动作（常量赋值）。**只接 JSON 一个参数**，`workflowId`/`nodeId` 写在 JSON 内部（不是位置参数）。JSON 格式见 `workflow/guide-workflow-action.md` |
| `e10-cli workflow action create <wf> <node> <name> --target-table --target-app [--action-type] [--match-field] [--mapping] [--constants] [--formula] [--sysvar] [--app-id]` | **一键创建动作流**。支持 `--mapping`(字段映射，含明细表字段：源明细→目标明细逐行，**仅 add**)、`--constants`(常量)、`--formula`(公式 add/sub/mul/div)、`--sysvar '{"目标Flow字段":"requestId"}'`(流程id写入关联流程字段，点字段跳回本流程)。`--app-id <已有动作流appId>` **复用模式**：跳过创建，把已存在的动作流（如 py 生成器暂存的）绑到节点，配合 `--event`/`--condition`。**update/delete 含明细走 py 生成器**（CLI 仅主表；明细+requestId定位用 py 的 action_eb_update + filterCondition，再 `--app-id` 绑节点） |
| `e10-cli workflow action get <sceneId>` | 查看动作流设计 |
| `e10-cli workflow action list-node <wf> <nodeId> [--trigger-type all\|link]` | 列出节点绑定的动作（getAddActionDataList）。显示每条的动作类型/appId/触发时机，type0 还带字段=值 |
| `e10-cli workflow action clear-node <wf> <nodeId> [--trigger-type all\|link]` | **清空节点所有动作绑定**（deleteAddAction + delList）。清理重复 add/已删实体残留的悬空绑定；动作流实体另用 `action delete` 清 |
| `e10-cli workflow action fields <tableId> <appId>` | 查看目标表可用字段（用于编写 mapping） |
| `e10-cli workflow action disable <appId> <name>` | 禁用动作流（禁用后才能删除） |
| `e10-cli workflow action delete <appId> <name>` | 删除动作流（自动先禁用再 batchAddRecycle 删实体）。**平台无"按动作流反查绑定节点"接口**：删实体后，绑定了此动作流的节点会残留**悬空引用**（前端显示「被删除」）。CLI 删完会提示，需逐个用 `action clear-node <wf> <node>` 清理节点绑定 |

> **加节点**: add-node 直接操作节点列表 API (getNodeEditTable → saveNodeEditTable)
> **加连线**: add-link/add-links 直接操作出口列表 API (getWfpNodeLinkTable → saveNodeLinkEditTable)
> **删连线**: delete-link 直接操作出口列表 API (getWfpNodeLinkTable → saveNodeLinkEditTable, deleteRows)
> **删节点**: delete-node 直接操作节点列表 API (saveNodeEditTable, deleteRows)，`--bridge` 自动桥接
> **查看节点/出口**: nodes --mode list / link-list 走列表 API（比 chart XML 更完整）
> **加分支条件两种方式**: 
>   - 简化: `condition add` — 一行命令搞定
>   - 完整: generate-link-id → save-layout → save-condition → set-link-condition-key
> **加节点提交动作（字段常量赋值）**: save-action @action.json（格式见 `workflow/guide-workflow-action.md`）
> **加跨表单动作流**: workflow action create —— 自动完成动作流创建+设计保存+节点绑定

---

## 菜单

| 命令 | 说明 |
|------|------|
| `e10-cli menu list <appId>` | 列出当前Ebuilder应用下的菜单 |
| `e10-cli menu add <name> <path> <appId>` | 将页面加入左侧导航（LINK 类型，URL path）。ecode 页面 path 如 `/sp/custom/ecode/project-list`。**表单台账/流程发起菜单用下面两条专用命令**（VIEWPORT/LAYOUT 类型，非 URL） |
| `e10-cli menu add-table <appId> <objId> [name]` | 给表单加**台账菜单**（VIEWPORT，指向数据列表页）。`form create` 已自动加，此命令用于事后补加 |
| `e10-cli menu add-start <appId> <formObjId> [name]` | 给流程绑定的表单加**发起菜单**（LAYOUT，指向表单新建页，点开触发流程）。`workflow create` 已自动加，此命令用于事后补加 |
| `e10-cli menu delete <menuId> <appId>` | 删除菜单项 |

---

## 人员 & 图标

| 命令 | 说明 |
|------|------|
| `e10-cli user search <keyword> [count]` | 模糊搜索员工（返回 ID/姓名/部门/手机） |
| `e10-cli icon search <keyword...>` | 搜索 Ebuilder 图标（4999 个，支持多关键词） |

---

## 代码检查

| 命令 | 说明 |
|------|------|
| `e10-cli check <项目目录>` | 代码质量检查，逐条自检，全部确认通过后再 build |

---

## 典型工作流

```bash
# 1. 创建项目ecode
e10-cli project create 会议室预订

# 2. 打包 & 上传
ecodecmd build /path/to/project --target=e10
e10-cli project import <projectId> .target/xxx.zip --main-url /sp/custom/ecode/table-demo

# 3. 后续改代码再上传（先删旧应用文件夹）
ecodecmd build /path/to/project --target=e10
e10-cli project tree <projectId>              # 找旧应用 folderId
e10-cli project delete-folder <folderId>
e10-cli project import <projectId> .target/xxx.zip --main-url /sp/custom/ecode/table-demo

# 4. 需要表单时
e10-cli app create 会议室管理                  # → appId
# 先写字段定义文件 fields.json，然后：
e10-cli form create <appId> 会议室表单 /path/to/project --fields @fields.json  # → objId
e10-cli form read <objId> --app-id <appId> --out fields.json  # 写入 fields.json（推荐）

# 5. 角色管理
e10-cli role create 财务主管 --code CW01 --remark "审批角色"
e10-cli role add-member <roleId> 张三

# 6. 创建流程
e10-cli workflow create <appId> <formObjId> 会议室审批
e10-cli workflow nodes <workflowId>                     # 查看节点

# 7. 配置审批节点
e10-cli workflow set-operator <wf> <nodeId> 张三         # 指定人
e10-cli workflow set-operator <wf> <nodeId> 财务主管 --type role  # 指定角色

# 8. 加分支条件（如金额≥1000走CEO审批）
e10-cli workflow generate-link-id <wf>                   # → newLinkId
e10-cli workflow save-layout <wf> @修改后的xml文件
e10-cli workflow save-condition @条件.json                # → conditionKey
e10-cli workflow set-link-condition-key <wf> <linkId> <key> <nodeId>

# 9. 添加菜单
e10-cli menu add 会议室预订 /sp/custom/ecode/meeting/list <appId>

# 10. 配置动作流（新增/更新/删除）
e10-cli workflow action fields <targetTableId> <targetAppId>     # 先查目标表字段
# 新增: mapping.json = {"源表字段ID":"目标表字段ID",...}
e10-cli workflow action create <wf> <nodeId> 动作流名称 \
  --target-table <targetTableId> --target-app <targetAppId> \
  --mapping @mapping.json --creator '{userid}' --event arrive
# 更新: 按匹配字段定位记录后更新
e10-cli workflow action create <wf> <nodeId> 更新动作 \
  --action-type update --match-field <源字段ID> --mapping @map.json \
  --target-table <id> --target-app <id>
# 累加更新（如 项目工时 += 工时金额）：mapping 值带 + 前缀（OPERATE_PLUS）；
# match-field 用关联字段（不传 --match-target → opType:id，关联值=目标记录dataId）
e10-cli workflow action create <wf> <归档节点> 工时累加 --action-type update \
  --match-field <关联项目fieldId> \
  --mapping '{"<源:工时金额fieldId>":"+<目标:项目工时fieldId>"}' \
  --target-table <项目台账objId> --target-app <appId>
# mapping 方向: key=源字段 value=目标字段；+前缀=累加(PLUS) -前缀=累减(MINUS)
# 删除: 按匹配条件删除
e10-cli workflow action create <wf> <nodeId> 删除动作 \
  --action-type delete --match-field <源字段ID> \
  --mapping '{"源字段ID":"目标字段ID"}' --target-table <id> --target-app <id>
```