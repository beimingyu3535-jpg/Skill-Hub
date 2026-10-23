---
name: skill-e10-cli
description: Ebuilder智能搭建skill v2（通用版），辅助编写泛微Ebuilder自定义应用，对应CLI版本1.0.0-beta
auto: true
---

# Ebuilder 智能搭建 Skill

## 核心理念

> **一份需求文档 = 一个 eb 应用。** 需求里的所有表单、流程、菜单、页面都建在**同一个应用**下，不要按功能点/表单拆成多个应用。只有需求明确要求分属不同业务系统时才建多个应用（此时先跟用户确认再动手）。

```
一份需求文档 → 一个 eb 应用
 └→ 应用下的资源: 表单 → 流程 → 菜单 → 页面
     前四个是业务主体
          页面是最后一步
```

接到需求不要一上来就写页面代码。先想清楚这一个应用下需要哪些表单、字段怎么设计、流程怎么走。

**CLI 能力速览（详细命令见 `references/common/ref-cli-commands.md`）——均为第一轮可配完，不要留到"后续再补"：**
- 表单：字段显隐联动 / 复杂编号(年份流水) / 字段公式 / 查重 / 关联浏览数据范围与显示列 / 布局·权限·视图管理
- 流程：分支条件 AND/OR / 动作流(常量·公式·累加·增删改) / 相关人员审批 / 消息提醒 / 提交校验
- 其他：台账显示列·搜索·排序·统计 / 列点击跳转 / 编号·流程编号规则

---

## 面向人群

- 本 skill 面向非编程人员。用户不懂技术，不会描述字段类型、数据关系。
- 你要主动引导，把模糊需求翻译成精确的平台资源设计。

### 工作流

```
0. 环境确认（每次对话必做）
   a. 检查当前鉴权：e10-cli auth status
   b. 用户提到不同系统地址（如"在 xxx 搭建"）→ 必须切换鉴权：
      - 已有 profile（凭证已存）：e10-cli auth profile use <name>（直接切，无需重新登录）
      - 新环境：e10-cli auth set --eteamsid "<ETEAMSID>" --base-url <url>
        （ETEAMSID 从浏览器 DevTools → Application → Cookies 复制；浏览器 OIDC 登录暂未实现，不要用 auth login）
   c. 需求含自定义页面时：`e10-cli project tree 0` 探测 Ecode 授权
      - 成功 → 页面可做
      - 401「e-code授权校验失败」→ 提前告知用户需开通 Ecode 权限（可并行处理，不阻塞段①②），plan.md「### 页面」标注「阻塞：待 Ecode 授权」

0.5 环境探测（段①应用创建后、建表前，每次新环境必做）
   a. `node scripts/probe-env.mjs <appId>` → 输出 physical: true/false
      - physical=true → 标准 `e10-cli form create`（物理表路径）
      - physical=false（仅 share）→ 逻辑表建表路径（见 troubleshooting.md 1.1），**禁止直接 form create**
   b. 结果写入 plan.md 头部「环境信息」行，如 `环境: eteams | 存储: share | 建表: 逻辑表`
   c. 注意：探测接口需要 appId，必须在应用创建之后执行；不要放在任务最开头

1. 判断需求复杂度
   ├─ 涉及 2+ 模块（应用/表单/流程/页面）→ 进入步骤 2
   └─ 简单单步操作（改字段、查数据）→ 直接执行

2. 全局资源设计（复杂需求必经）
   a. 理解需求，不够清楚的地方反问用户
   b. 在本地写 `plan.md` 搭建计划大纲，**逐项列出所有待建资源**：
      ```
      ## 搭建计划
      ### 应用
      - [ ] <应用名> | ID: 待创建    ← 一份需求只建这一个应用，所有表单/流程/菜单都在它下面
      ### 表单
      - [ ] <表单名> | ID: 待创建
        字段: 名称(Text) / 金额(Money) / 类型(Select: A,B) / 明细表: 序号(Number) ...
        （选项/编号规则/默认值/百分比显示建表时一并写全；单位无独立属性，写进字段名如 工时单价(元)）
      ### 流程 <流程名>
      > ⚠️ **流程级必做**：① 流程编号（`workflow numbering`，方案有编号规则的）；② 出口名称（`workflow link-rename`，连线默认名是英文/随机，**改成业务人话**，如"金额≥10万"、"金额<10万"，分支连线尤其要改）。
      - [ ] <节点1> | 操作者: 创建人
      - [ ] <节点2> | 操作者: 区域经理+部门领导(竞签)
      - [ ] <节点3> | 条件: <字段>=<值> 才走到，否则跳过/直达<节点>
      - [ ] <节点4> | 操作者: 角色X ｜ 动作流: → <目标表>(add/update/delete, 映射: 源→目标)
      - [ ] <节点N> | ...   （每个节点一行，操作者/条件/动作流挂在对应节点上）
      ### 菜单
      - [ ] <菜单名> | 指向: <流程/表单>
      ### 页面
      - [ ] 无定制页面，表单自带台账（有定制页面才另列）
      ### 必做项（销号核对，勿依赖平台默认值——平台默认值≠方案要求）
      > ⚠️ **[ ] 是待办，不是"已规划"。规划阶段全部留 `[ ]`；执行阶段做完一项、验证通过，才把 `[ ]` 改 `[x]` 并填入 ID。**plan 是配合搭建过程用的进度表——**完成一条打勾一条**，全部 `[x]` 才算完工。**禁止在规划阶段就把项勾成 `[x]`**（那等于谎报完成）。
      - [ ] 角色: role create（方案要求的每个角色都要建，不会自动有）
      - [ ] 节点操作者: workflow set-operator（每个审批节点，勿默认"所有人"）
      - [ ] 流程编号: workflow numbering（方案有编号规则的流程）
      - [ ] 出口名称: workflow link-rename（有分支条件的连线，改成人话）
      - [ ] 显示列: form ebuilder-columns / list-columns（先 `ebuilder-columns` 不带参数看**业务字段候选清单**（系统字段已自动过滤），从清单选字段名设置）
      - [ ] 数据过滤: form ebuilder-scope（关联浏览字段的数据范围设置，如"客户状态=启用"才可选；配到关联浏览字段上）
      - [ ] 提交校验: workflow node validate（字段 vs 字段/字面值/跨表，如 "请假时长 小于 4" 禁止提交、"行程明细.行程开始时间 等于 出差开始日期" 主子表校验）
      - [ ] 签字意见必填: workflow node sign（退回等操作类型必填意见，如 `node sign <wf> <审批节点> --select "退回"`）
      - [ ] 流程标题: workflow setting title（标题按规则生成真实数据，如 `--rule "发起人|提交日期|客户名称"`；标题=流程名+系统字段则跳过）
      - [ ] 数据来源落点: 写入型动作流的目标台账**必须建 Flow 字段**（如「数据来源」←来源流程，`form add-field <台账> <app> "数据来源" Flow --sform-id <流程表单objId>`）——add 时 `--sysvar` 写 requestId 的落点，update/delete 也靠它定位
      ```
      > **应用数量**：默认全需求只建 **1 个**应用。看到需求先归拢到这一个应用下，不要按功能点拆应用。确需多应用（分属不同业务系统）要先跟用户确认。
      > **流程按节点逐行**：每个节点一行 `- [ ]`，操作者（含签署方式：会签/非会签/竞签/依次/抄送）、条件（什么情况走到/跳过/直达）、动作流（该节点触发写目标表）都挂在对应节点上。**「A 或 B 审批」= 一节点多人 + 竞签/非会签**，写进操作者行，不拆节点。逐节点销号。
   c. 拿计划大纲和用户确认（**此阶段 plan 里所有 `[ ]` 保持未勾**——是待办清单，不是完成清单）
   d. 用户确认后按大纲**逐项执行、逐项打勾**：每做完一项、验证通过，才把 `[ ]` 改 `[x]` 并填入实际 ID。**完成一条打勾一条**，禁止预勾。

   > **台账页面不用写**：表单建好即自带台账（搜索/筛选/导出/批量操作）。plan 里的「### 页面」只列**定制化需求**（图表、跨表聚合、特殊交互）。没有定制页面就把整节标 `### 页面（无需，表单自带台账）`。

3. 执行搭建（**最多分三段，每段完成停下来让用户确认，确认后才进下一段**）
   - **段① 应用 + 角色 + 全部表单**：
     - 建应用、建角色
     - **每张表一口气建全**：`form create --fields @fields.json` 写全字段/选项/默认值/精度/百分比/子表/明细（勿先建空表再 add-field）
     - **建表后逐表配齐表内项**（缺一项这张表就不算完成，逐项打勾）：
       - `serial-mark` 复杂编号（编号字段：前缀/年份/流水）
       - `relateFrom` 值带出（EBuilder 关联带出：`edit-field --relate-from`；表内人员/部门带出：`form relate`）
       - `ebuilder-scope` 关联浏览数据范围（如客户状态=启用才可选）
       - `formula` 字段公式（付款比例/工时金额等；fields.json inline 或 `form formula set`）
       - `validate` 查重校验（项目名称/工时日期重复不允许）
       - `list-columns` 台账显示列（去系统字段，只留业务字段）
     - 全部表 + 表内项都完成后，给用户列表单清单 + 关键字段，**确认字段设计**再进段②
   - **段② 流程**（节点/操作者/条件/动作流）→ 完成后给用户列流程（节点+签署方式+条件），**确认流程**再进段③
   - **段③ 菜单 + 页面**
   - 每段内按 plan.md 逐项推进、即时打勾，做到「大纲驱动、逐项销号」。
   - 简单单步需求（改字段、查数据）不分段，直接执行。
```

**关键约束**：
- Plan 阶段**不调用 e10-cli 写命令**（可以 list/read 查询现状）
- **必须写 plan.md 落地**，不要只在对话里列方案——用户需要一份可回顾的文档
- 执行时逐项销号，全部 `[x]` 才算完工
- **分段执行、分段确认**：应用+表单 → 确认 → 流程 → 确认 → 菜单/页面。**表单是流程的地基**（流程绑定表单、条件/动作流/操作者都引用字段），字段设计错了流程全返工，所以表单段必须确认后再进流程
- 本服务运行于 Windows 环境，注意命令行兼容性
- 不要多说废话，直接干活。用户等的是结果。
- **写代码不要犹豫**，按模板直接出完整代码，写完用 `e10-cli check` 验证。错了报错再改。
- **表单字段一次性建好**：`form create --fields @fields.json` 时把所有字段定义写全，包括选项和默认值。**不要先建表再加字段**——add-field/edit-field 只是罕见补救手段，正常流程就是一口气建完。
- **解析 Word 文档**：用 `e10-cli docx read <文件>` 一键转 markdown + 提取图片，**禁止自己写 python-docx 脚本**。读取后必须逐张 Read `_images/` 目录里的图片做多模态理解，**把分析结果写回 md**（替换图片占位符为实际描述，让文档完整可读）。

---

## 错误复盘协议（每次完整任务必做）

> 目标：每次完整搭建任务交付时，输出本次任务的问题复盘清单，供用户决定哪些沉淀进 `references/common/troubleshooting.md`，形成持续积累。

### 触发时机

- 一次完整搭建任务交付后（分段任务在最终交付时输出一次）
- 用户要求中途复盘时按需输出

### 执行步骤

1. 回顾本次任务全部执行过程，提取**真实遇到并实际处理过**的问题项
2. 按「问题分类」分级组织，每项严格按**四段式条目模板**输出
3. 输出后**不写入文件**，等待用户逐项确认
4. 用户确认的条目，才追加进 `references/common/troubleshooting.md`（追加到对应分类下，保持模板一致）

### 问题分类

```
一、环境与平台限制（物理表/授权/权限类）
二、PowerShell / Windows 兼容陷阱（转义/编码/管道类）
三、CLI 命令使用陷阱（参数语义/静默失败类）
四、动作流 py 生成器使用陷阱
五、动作流配置（CLI 侧）要点
```

出现新类别时新增分类，不要硬塞进旧分类。

### 四段式条目模板

> 严格按此格式，缺失的段写「无」。

```markdown
### X.X 标题（一句话概括问题）
- **现象**：报错原文/异常表现（原样引用，不改写）
- **根因**：一句话说明机制层面的原因（不确定就写「未完全确认，表现为...」）
- **解决**：实际生效的解决步骤（可含命令）
- **预防**：下次如何避免（规则化表述）
```

### 排除规则（不进入清单的问题）

- 已收录在 troubleshooting.md 且本次无新信息 → 不重复输出，只标注「复现第 X.X 条」
- 纯操作失误且无预防价值（如输错 ID）→ 不输出
- 与本次任务无关的历史问题 → 不输出
- 未实际解决、无法确认根因的悬置问题 → 标注「待解决」后输出，不假装已解决
- **同类合并**：不同现象但根因相同 → 输出时合并为一条主条目（根因/解决/预防写一次），各现象并列在「现象」下（如「--rules/--constants/--sysvar 及 py 传参均报 JSON 解析失败」）
- **入库去重**：新条目追加前必须检索 troubleshooting.md 同根因条目；命中 → 追加到已有条目的「补充场景」，不新建条目（同根因只允许一条主条目）

### 输出格式示例（标准模板）

```markdown
## 本次任务问题复盘

### 二、PowerShell / Windows 兼容陷阱

#### 2.1 CLI 的 JSON 选项参数被 PowerShell 转义破坏
- **现象**：`--rules '[{"field":"客户状态",...}]'` 报「不是有效 JSON」；`--constants '{"...":"..."}'` 报「JSON 解析失败」
- **根因**：PowerShell 引号/转义规则与 cmd 不同，内联 JSON 双引号丢失
- **解决**：所有 JSON 选项一律用 @文件路径：
  ```bash
  e10-cli form ebuilder-scope set ... --rules @scope.json
  e10-cli workflow action create ... --constants @constants.json --sysvar @sysvar.json
  ```
- **预防**：规则：CLI 选项带 JSON 值 → 写文件再 @ 引用
```

### 输出纪律

- 只写真实发生的，不编造现象/根因/解决
- 现象原样引用报错文本；解决写「实际生效」的方案（理论方案标注「未验证」）
- 每条控制在 5 行内（命令块除外），保持可快速扫读
- 全部输出后附一句：「以上条目请确认哪些写入 troubleshooting.md（回复条目编号即可）」

### 用户确认交互

- 用户回复形式：`保留 2.1、3.3` / `全部保留` / `都不需要` 均可
- 确需合并的条目由 AI 合并后写入，不要求用户逐条写理由

---

## 决策树

> **根据用户需求自动加载对应子文档，不要一次性读取全部 reference。**
>
> **动作流两种用法**：简单动作流（跨表单新增/更新/删除、常量/公式/累加、`--condition` 触发条件）用 `e10-cli workflow action create` / `save-action`；**复杂动作流/多组件**（自然语言、20+ 组件 Meeting/HttpCall/定时触发/条件分支/消息提醒）用内置 `actionflows/` 子 skill（Python，**推荐**）。调用前先**复用 e10-cli 鉴权**：
> ```bash
> eval "$(e10-cli auth export-weaver-env)"   # 把当前 profile 的 ETEAMSID/baseUrl 导出为 WEAVER_* 环境变量
> python actionflows/scripts/actionflow_skill.py <命令> @<json文件>   # ⚠️ 一律 @文件传参（UTF-8 无 BOM），禁止命令行内联 JSON
> ```
> **py 传参铁律**：
> - 所有 JSON 一律写文件后 `@` 引用（`env-add`、`generate`、`describe` 等全部命令共用此入口），绕开 Windows 转义与乱码
> - 文件必须是 **UTF-8 无 BOM**（Node/`write` 工具写入；PowerShell `Set-Content -Encoding UTF8` 会带 BOM 导致 py 报错）
> - 环境注册参数名是 **`eteamSid`**（不是 eteamsId）等 py 传参细节，见 troubleshooting.md 2.1（补充场景）

| 用户关键词 | 加载文档 |
|-----------|---------|
| 报错排查、遇到问题、报错、失败、troubleshoot | `references/common/troubleshooting.md`（先查错误文档，再动手；含环境/转义/命令/动作流五类已知问题） |
| 建应用、创建应用、app create | `references/common/ref-cli-commands.md` |
| 鉴权、登录、ETEAMSID、多环境、profile、切换环境 | `references/auth/guide-auth.md` |
| 表单数据读写、getSimpleData、withDisplayNames、getFieldOptions、saveFormData、updateFormData | `references/coding/guide-form-crud.md`（前端代码） |
| form data add、form data list、form data delete、写入数据、查询数据、删除数据 | `references/form/guide-form-data.md` |
| 编辑回显、handleEdit、getAllData、数据回填 | `references/coding/guide-edit-backfill.md`（前端代码） |
| 字段联动、显隐联动、条件显示、form linkage | `references/form/guide-form-linkage.md` |
| 新建表单、form create、字段定义、字段类型、fields.json | `references/form/guide-create-form.md` |
| 流程、审批、workflow、提交流程、预填 | `references/workflow/guide-workflow.md` |
| 流程节点、操作者、审批人、连线、添加节点、删除连线、删除节点、delete-node、节点操作者、set-operator、出口名称、link-rename、节点字段权限、field-permission | `references/workflow/guide-workflow.md` |
| 节点校验、提交校验、node validate、智能审批规则、字面值校验、禁止提交 | `references/common/ref-cli-commands.md` |
| 分支条件、出口条件、条件JSON、save-condition、连线条件 | `references/workflow/guide-workflow-condition.md` |
| 动作流、跨表单、写入台账、ActionEbAdd/ActionEbUpdate/ActionEbDelete、提交事件、数据来源、requestId、按流程定位、回写数据ID、回写 | `references/workflow/guide-workflow-action.md`（**简单动作流**：CLI `action create`；**requestId 定位/回写/多组件**→ 走 py 生成器） |
| 菜单、导航、左侧菜单、系统页面、待办、已办、流程监控 | `references/menu/system-menus.md` |
| 角色、角色管理、权限、成员 | `references/common/ref-cli-commands.md` |
| 新页面、导出、路由、entry.js、asyncImport | `references/coding/guide-page-export.md`（前端代码） |
| 写页面、页面代码、React编码、组件、entry.js模板 | `references/coding/guide-page-code.md`（前端代码） |
| CLI命令、打包、build、import、创建应用/表单/菜单 | `references/common/ref-cli-commands.md` |
| 编译报错、语法不支持、babel | `references/coding/ref-compile-rules.md`（前端代码） |
| Word文档、docx、需求文档、解析文档 | `e10-cli docx read` 一键转换，禁止自己写脚本 |
| 新建视图、表格视图、看板、日历、思维导图、form view、台账显示列、显示列、list-columns、搜索条件、排序、list-sort、顶部统计、list-stats | `references/form/guide-form-view.md` |
| 视图权限、查看布局、修改共享权限、view permission | `references/form/guide-form-view-permission.md` |
| EBuilder关联、关联表单、数据过滤设置、ebuilder-filter、EBuilder显示列、ebuilder-columns、去掉系统字段、只留业务字段 | `references/form/guide-ebuilder-filter.md` |
| 关联浏览筛选、数据范围设置、浏览数据定义、只选启用状态、关联客户过滤、ebuilder-scope | `references/form/guide-ebuilder-scope.md` |
| 函数公式、字段公式、formula、DAYS、日期差、expressId、公式绑定 | `references/form/guide-form-formula-functions.md`（219 个函数速查矩阵，写 `fields.json` 的 `formula` 或 `form formula set --expression` 时查函数格式/示例；**日期差用 `DAYS(开始,结束)`**） |
| 表单按钮、button、自定义按钮 | `references/common/ref-cli-commands.md` |
| 表单权限、permission、数据权限 | `references/common/ref-cli-commands.md` |
| 消息提醒、消息动作流、workflow message、IM提醒 | `references/common/ref-cli-commands.md` |
| 编号规则、serial-mark、自动编号、流水号、年份编号、流程编号、numbering | `references/common/ref-cli-commands.md` |
| 超时处理、退回设置、节点菜单、node timeout、node reject | `references/common/ref-cli-commands.md` |
| 流程设置、提交确认、签字意见、批量操作、setting | `references/common/ref-cli-commands.md` |
| 流程存档、定时触发、高级设置、advanced | `references/common/ref-cli-commands.md` |
| HRM、矩阵、条件矩阵、matrix、映射表 | `references/hrm/guide-matrix.md` |

> 组件文档（Button/Table/Input/Upload 等）在 `references/` 中按文件名查找。完整索引见 `_catalog.md`。

> **表单自带默认台账** — 用户明确要求额外表格视图时，用 `form table-view create` 原子完成 `nListView` 创建、显示列配置和回读；禁止用 `form view create --type tableView` 创建空壳。`formView` 使用 `form view create` 后必须执行 `form view populate`。

---

## 平台架构

- **Ecode** — 存放和运行代码的平台，自定义页面在这里编码、构建、运行
- **Ebuilder 应用** — 独立的概念，包含表单、流程等元素（与 Ecode 项目不同）
- **表单自带台账，无需开发** — 每个表单创建后，平台自动生成默认的台账/列表页面，自带搜索、筛选、导出、批量操作。**台账会自动挂入应用菜单，无需手动建菜单。** 这不是一个「功能」，是一个硬规则——建了表单就有台账页面，不需要写一行代码。只有以下场景才需要自定义页面：图表仪表盘、跨表单聚合视图、特殊交互流程、对外公开页面。
- 所有系统交互命令均通过 `e10-cli` 执行（已全局 link）。auth 文件自动查找，也可 `--auth <path>` 指定。
- 用户的 userId 是固定的变量 `TEAMS.currentUser.id`，系统里已支持，js 代码里可以直接写。

---

## 平台能力边界（禁止编造）

> **以下能力 CLI 不支持、平台也不支持，AI 禁止声称可以做、禁止输出操作步骤。**

| 不支持的能力 | 说明 |
|-------------|------|
| **H5/移动端菜单** | 移动端是独立体系（不同 URL + 不同 pageId），尚未整理，禁止编造 |

> 遇到用户要求以上不支持的能力时，必须明确告知"当前平台/CLI 不支持"，不要给出虚假操作步骤。

---

## 关键数据操作速查

### 表单数据 API

| API | 用途 | 返回内容 |
|-----|------|---------|
| `getSimpleData(objId, userId)` | 读 ID、写回 formToSave | 所有特殊字段统一返回 `fieldOptionId`（纯数字串） |
| `getAllData(objId, userId)` | 提取名称、编辑回显 | 含 `fieldOptionName`，mainTable key 是随机哈希 |
| `withDisplayNames(rows, map)` | 表格展示：ID → 名称 | 把 Select 的 `valueKey` 映射为中文名 |
| `getFieldOptions(fieldId, objId)` | 拿下拉选项 | `[{valueKey, name}]` |

### 不同字段类型，名称来源不同

| 字段类型 | getSimpleData 返回 | 展示时名称来源 |
|---------|-------------------|--------------|
| Text / Number / Date | `"值"` / `123` / `"2026-01-01"` | 直接展示 |
| Select / RadioBox / CheckBox | `"1283421826353889337"`（选项 ID） | `getFieldOptions` → `withDisplayNames` 映射 |
| **Employee** | `"2765550234448235905"`（用户 ID） | `getAllData` 的 `fieldOptionName`，**不是** getFieldOptions |
| **Department** | `"2765550234448235905"`（部门 ID） | 同上 |
| FileComponent | `"fileid1,fileid2"`（文件 ID 串） | 上传组件的 `name` |

> 完整数据读写指南见 `references/coding/guide-form-crud.md`（前端代码），编辑回显见 `references/coding/guide-edit-backfill.md`（前端代码）。

---

## 页面编码

> **页面是搭建流程的最后一步。** 写页面代码前，确保应用、表单、流程都已建好。

页面编码规范、entry.js 模板、@weapp/ui 组件清单、编译规则、代码质量检查清单 → 详见 `references/coding/guide-page-code.md`（前端代码）。

---

## 快速参考

- 入口注册 + 新页面导出 → `references/coding/guide-page-export.md`（前端代码）
- 流程 URL 透传、预填 → `references/workflow/guide-workflow.md`
- 编译约束（var 声明、不支持的语法）→ `references/coding/ref-compile-rules.md`（前端代码）
- CLI 命令速查 → `references/common/ref-cli-commands.md`
- 报错排查、已知问题 → `references/common/troubleshooting.md`
- 组件完整索引 → `_catalog.md`

---

## 附：自定义页面代码场景——拷贝模板项目

> 仅用于「自定义页面代码」场景（写 entry.js / 自定义页面、调 formApi）。建表单/流程/菜单等不需要拷模板，直接用 `e10-cli` 命令。

从本skill `assets/sample/` 拷贝模板文件到你的工作目录。

模板包含：
| 文件 | 用途 |
|------|------|
| `entry.js` | 路由注册入口，已配置好 `asyncImport` |
| `api/formApi.js` | 表单数据读写的标准 API |
| `config/config.js` | 基础配置（userId 等） |
| `eslint.config.cjs` | 代码检查规则 |
| `.claude/settings.local.json` | Claude Code 本地设置 |
