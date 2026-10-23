---
name: weaver-e10-builder
display_name: 泛微E10智能搭建Skill
display_name_en: E10 Builder
description: 泛微E10智能搭建skill v2（通用版），辅助编写泛微Ebuilder自定义应用，对应CLI版本1.5.15
description_zh: 泛微Ebuilder低代码应用智能搭建工具 v2（通用版），辅助编写自定义应用（表单/流程/列表/动作流/权限/分组/编号等），与 e10-cli 配套使用，当前对应 CLI 版本 1.5.15。
description_en: E10 Ebuilder low-code app builder skill v2 (general) — helps build Weaver E10 custom apps (forms/workflows/lists/actionflows/permissions/groups/numbering) via e10-cli, currently paired with CLI 1.5.15.
category: coding
version: 1.5.15
author: 泛微网络科技股份有限公司
auto: true
---

# Ebuilder 智能搭建 Skill

## 使用前提

- **版本必须匹配**：`e10-cli --version` 应与 frontmatter 的 `version` 一致；不一致时命令/选项/文档可能对不上。
- **鉴权**：仅在即将远程查询或写入前运行 `e10-cli auth status`；同一连续阶段不重复检查，切换系统地址、profile 或凭证后必须重新确认。
- **文档随 CLI 分发**：读 `references/...` 提示文件不存在时，跑 `e10-cli skill sync` 或重跑 `e10-cli auth status`。
- 安装/升级、skill 重装、WorkBuddy 注意事项 → `references/common/guide-install.md`。

## 核心理念

> **默认一份完整业务方案落在一个主应用。** 需求明确指定已有应用、跨应用资源或独立业务边界时，按实际范围处理，并在 `plan.md` 中标明每项资源的所属应用和跨应用关系。

```
一份完整业务方案 → 一个主应用（默认）
 └→ 应用下的资源: 表单 → 流程 → 菜单 → 页面
跨应用/已有应用增强 → 按实际边界规划并明确资源归属
```

接到需求不要一上来就写页面代码。先想清楚这一个应用下需要哪些表单、字段怎么设计、流程怎么走。

**能力范围**：应用与资源、表单与字段、视图与按钮、流程与动作流、设计器报表、权限、页面、数据操作，以及从接口文档批量创建 ESB 系统接口。具体能力、命令与限制以本页决策树路由到的 `_catalog.md` 和 `references/` 为准；规划时应一次覆盖需求中已明确的配置项，不因主文档未枚举某条命令而遗漏。

---

## 流程类型与默认路径

默认使用 **EB 表单**及应用内流程。只有需求明确要求原生流程表单、工作流程或流程中心建流程时，才切换到 `wf-form` / `workflow create-workflow`；不确定且选择会改变资源归属时，先向用户确认。EB 流程与原生工作流程的表单、资源 ID、接口不可混用；公文流程是原生工作流程的特殊类型。详见 `references/workflow/guide-workflow.md`。

---

## 执行流程

面向非编程用户：主动把模糊需求翻译成精确的资源设计。

0. **环境**：仅在即将远程查询/写入前跑 `e10-cli auth status`；切已有环境用 `auth profile use <name>`，新环境用 `auth set --eteamsid "<ETEAMSID>" --base-url <url>`（ETEAMSID 从浏览器 Cookies 复制，不走 `auth login`）。
1. **判断复杂度**：涉及 2+ 模块（应用/表单/流程/页面）→ 进入规划；单步改字段、查数据 → 直接执行。
2. **规划**（复杂需求必经）：
   - 每张表单建表前确认布局类型 **FLOW / EXCEL**（建后不可切换）；出现布局样表时按 `references/form/guide-form-layout-planning.md` 解析。
   - 按 `references/common/map.md` 识别资源与依赖，按 `references/common/guide-plan-template.md` 写 `plan.md`；每条要求有归属和来源，布局样表逐行保留，禁止预勾。
   - 写完打开 `plan.md` 与用户确认（此时所有 `[ ]` 保持未勾）。
3. **执行**：最多三段，每段结束停下确认。
   - 段① 应用、角色、表单与视图；段② 流程与自动化；段③ 报表、菜单与页面。
   - 以 plan 为唯一清单，按功能批次执行，逐项销号并回填真实 ID；无法完成的保留 `[ ]` 并注明原因。
   - 布局样表：仍由 CLI 创建字段与初始布局；明确要求还原图片/XLSX 样式时读 `references/form/guide-form-layout-source.md`（先实际观察、经用户确认样式，再 compile/apply）。

**关键约束**
- 配置必须通过当前 `e10-cli` 支持的命令完成；没有对应命令就如实告知，不得写临时 `.mjs` 脚本或让用户操作浏览器代做。能力边界见 `references/common/capability-boundaries.md`。
- Windows 环境，注意命令行兼容性；少说废话，直接干活。
- 写代码按模板直接出完整代码，写完用 `e10-cli check` 验证。
- 解析 Word 用 `e10-cli docx read`，禁止自写 python-docx；必须逐张 Read `_images/` 图片并写回 md，布局表格保留空白、同排与合并关系。

---

## 决策树

> **根据用户需求自动加载对应子文档，不要一次性读取全部 reference。**
>
> **动作流两种用法**：动作流「生成」一律走 native `e10-cli actionflow generate`（语义 plan → 编译 → preflight → 保存并启用 → 正式回读，event 节点自带流程节点触发绑定，**推荐**）；`e10-cli workflow action` 仅作动作流管理（`list-node`/`clear-node` 查清节点绑定、`delete`/`disable`/`batch-delete` 禁用删除动作流 app）。本表字段赋值/节点附加操作（actionType=0）用 `e10-cli workflow save-action`。
> ```bash
> e10-cli actionflow component-list                          # 列已登记组件
> e10-cli actionflow component-describe <type>               # 读组件契约
> e10-cli actionflow generate '{"planFile":"@plan.json","appName":"AI-名称"}'  # 生成+保存并启用+正式回读；planFile 必须以 @ 引用文件（@plan.json 或 @绝对路径），CLI 强制要求 @ 前缀
> e10-cli workflow action list-node <wf> <node>             # 查节点绑定；clear-node 清；delete/disable 删动作流
> ```

| 用户关键词 | 加载文档 |
|-----------|---------|
| 表单布局源码、表单级 ecode、表单 JS 代码块、JSSDK、代码校验、明细代码汇总、字段事件脚本、表单组件复写 | 先读 `references/code-block/guide-code-block.md` 选代码层级和 CLI 写入命令，再按效果读取该目录对应 JSSDK 专题；**布局源码 ecode 由 CLI 编码，不要手改 `sourceCode.ecode`；手工调接口必须用 `encodeURI`，不能用 `encodeURIComponent`（设计器用 `decodeURI` 读取）** |
| 写plan、搭建计划、plan.md、资源梳理、搭建模板、必做项清单、完整实施方案、需求映射、能力地图、跨资源依赖、规划预检、平台架构、Ecode、Ebuilder应用、默认台账与菜单 | 先读 `references/common/map.md` 识别资源、配置与依赖；必要时读对应细节文档；再按 `references/common/guide-plan-template.md` 写资源清单与功能批次 plan |
| 安装、升级、装不上、skill remove、skill sync、references 文档缺失、WorkBuddy | `references/common/guide-install.md` |
| 支不支持、能不能做、能力边界、不支持的能力 | `references/common/capability-boundaries.md` |
| 建应用、创建应用、app、应用列表、应用详情、应用目录、app read/list/folder/edit/delete | `references/common/ref-cli-commands.md` |
| 启用应用、停用应用、发布到前台、发布应用、取消发布、应用发布信息、前台入口、应用名多语言、应用英文名、app enable/disable/publish/unpublish/publish-info、app lang | `references/app/guide-app-publish.md`（启用→发布→改发布信息→取消发布的先后关系 + 停用会收回发布态 + 多语言整份写回） |
| 字段联动、字段值带出、HRM 属性带出、relateFrom、form relate、跨表带出赋值、FormDataLinkage、多跳带出、关联客户带出客户类型、field-linkage、Text字段赋值名称 | `references/form/guide-field-linkage.md`（按来源选择直接带出、HRM 带出或跨表查询赋值；含单跳/多跳与 --hops 格式） |
| 函数联动、本表字段间公式赋值、赋值式公式、EXCEL 公式联动、字段自动计算、form formula-linkage、wf-form formula-linkage、流程表单函数联动、触发事件、模块字段不能作目标 | `references/form/guide-formula-linkage.md`（四套联动对比 + 赋值式语法 + 触发事件表 + 模块字段 + 流程表单那条路由 + 常见报错） |
| 鉴权、登录、ETEAMSID、多环境、profile、切换环境 | `references/auth/guide-auth.md` |
| 表单数据读写、getSimpleData、withDisplayNames、getFieldOptions、saveFormData、updateFormData | `references/coding/guide-form-crud.md`（前端代码） |
| form data add、form data list、form data delete、写入数据、查询数据、删除数据 | `references/form/guide-form-data.md` |
| 编辑回显、handleEdit、getAllData、数据回填 | `references/coding/guide-edit-backfill.md`（前端代码） |
| 显示属性联动、显隐联动、条件显示、form linkage、为空/不为空条件、NULL 算子 | `references/form/guide-form-linkage.md` |
| 新建表单、form create、EB表单创建流程、fields.json | `references/form/guide-create-form.md`；确定具体字段参数时再读 `references/form/ref-form-fields.md` |
| 虚拟表、虚拟表单、绑定数据源、业务表展示、数据加工结果 | `references/form/guide-virtual-form.md`；字段类型按来源映射，不按普通字段重新猜测 |
| Excel样式、表格式布局、布局样表、布局蓝图、标签字段交替、合并单元格 | `references/form/guide-form-layout-planning.md` |
| 还原图片样式、还原Excel样式、XLSX布局、源网格、pageLayouts、layout extract/compile/apply/verify/style-audit、已有字段位置匹配 | `references/form/guide-form-layout-source.md`（图片 imageStyles 三层投影与样式诊断；已有字段复用，纯布局编译、单次保存和独立回读） |
| 流程、审批、workflow、提交流程、预填 | `references/workflow/guide-workflow.md` |
| 流程绑了哪张表、流程对应表单、workflow info、从流程找表单 | 命令速查 `references/common/ref-cli-commands.md` 的 `workflow info` 一行（**流程列表接口不含这个信息**；拿到的是 formId，不是 objId） |
| 权责表、权责矩阵、权责表方式流程、分支场景、变量映射 | `references/workflow/guide-workflow-auth-resp.md`（操作者和条件同时遵循流程基础指南） |
| 公文流程、公文审批、收文、发文 | `references/workflow/guide-workflow-odoc.md`（基础节点/出口/操作者同时遵循 `guide-workflow.md`） |
| 公文设置、正文设置、痕迹、套红、排版、文号、附件区、归档、智能助手 | `references/workflow/guide-workflow-odoc-setting.md` |
| 流程节点、操作者、审批人、连线、添加节点、删除连线、删除节点、delete-node、节点操作者、set-operator、出口名称、link-rename、节点字段权限、field-permission | `references/workflow/guide-workflow.md` |
| 节点独立布局、节点换布局、node layout、节点用哪套布局、流程布局、流式/表格式布局、引用节点、updateQuoteNode | `references/workflow/guide-workflow-node-layout.md` |
| 分支条件、出口条件、条件JSON、save-condition、连线条件 | `references/workflow/guide-workflow-condition.md` |
| 动作流、跨表单、写入台账、ActionEbAdd/ActionEbUpdate/ActionEbDelete、提交事件、数据来源、requestId、按流程定位、回写数据ID、HTTP/HTTPS、DML/数仓、自定义事件、内置 MQ | `references/workflow/guide-workflow-action.md`（动作流生成走 `e10-cli actionflow generate`；`workflow action` 仅查/清/删/禁用；本表字段赋值走 `save-action`；复杂组件契约按需读取 `actionflows/SKILL.md` 及其 `references/components/`） |
| 菜单、导航、左侧菜单、系统页面、待办、已办、流程监控、菜单改名、重命名菜单、菜单排序、菜单顺序、放第一个、menu order、showOrder、--first | `references/menu/system-menus.md` |
| 新页面、导出、路由、entry.js、asyncImport | `references/coding/guide-page-export.md`（前端代码） |
| 写页面、页面代码、React编码、组件、entry.js模板 | `references/coding/guide-page-code.md`（前端代码） |
| CLI命令、打包、build、import、创建应用/表单/菜单 | `references/common/ref-cli-commands.md` |
| 编译报错、语法不支持、babel | `references/coding/ref-compile-rules.md`（前端代码） |
| Word文档、docx、需求文档、解析文档 | `e10-cli docx read` 一键转换，禁止自己写脚本 |
| 接口文档、Postman、系统接口、批量导入接口、创建连接器接口 | `references/esb-interface/guide-import.md`；使用 `e10-cli interface import` |
| 新建视图、表格视图、看板、日历、思维导图、form view、台账显示列、显示列、list-columns、搜索条件、排序、list-sort、上下级、父级、树形展示、上级类型、list-hierarchy、视图数据条件、list-filter、日期占位符、{date}、{curryear}、动态日期 | `references/form/guide-form-view.md` |
| 视图权限、查看布局、修改共享权限、view permission | `references/form/guide-form-view-permission.md` |
| EBuilder关联、关联表单、数据过滤设置、ebuilder-filter、EBuilder显示列、ebuilder-columns、去掉系统字段、只留业务字段 | `references/form/guide-ebuilder-filter.md` |
| 浏览数据定义、浏览弹窗高级搜索、浏览数据范围、浏览 Tab、可配置浏览字段 | `references/form/guide-browser-definition.md`；关联 EBuilder 字段的简便筛选命令另见 `references/form/guide-ebuilder-scope.md` |
| 字段分组、分组容器、字段分段、基本信息/合同信息分段、Collapse、Fold、字段归组 | `references/form/guide-form-layout-planning.md`（**按需**：用户明确要求字段分组才在 fields.json 写 `group`，默认不加分组） |
| 独占一行、整行显示、字段换行、singleRow、--single-row | `references/form/guide-form-layout-planning.md`（fields.json 字段写 `"singleRow":true`；add-field 用 `--single-row`） |
| 布局样式模板分类、公共规则、layout init、style-template | `references/form/form-template/style-templates.md`（简易、高级、流式分别链接） |
| 给已有表单加字段、改必填/只读、表单不是自己建的、--reinit、布局被重建、字段在布局里对不上、字段标题显示不出来 | `references/form/guide-form-layout-incremental.md`（**⚠ 不是自己建的表不要用 `--reinit`**；设必填是改布局组件，字段定义里没有 `required`） |
| 字段类型、字段码表、日期区间、关联浏览、关联订单、关联合同、Order、Contract、字段多选、multiple、--multiple | `references/form/ref-form-fields.md` |
| 表单复杂编号、serial-mark、流水号、年份编号、代字 | `references/form/guide-form-serial-mark.md` |
| 函数公式、字段公式、formula、DAYS、日期差、expressId、公式绑定 | `references/form/guide-form-formula-functions.md`（219 个函数速查矩阵，写 `fields.json` 的 `formula` 或 `form formula set --expression` 时查函数格式/示例；**日期差用 `DAYS(开始,结束)`**） |
| 显示列批量设置、批量加列、列宽、列顺序、list-columns --set | `references/form/guide-list-columns.md` |
| 顶部统计、明细统计、付款记录数、list-stats、子表计数 | `references/form/guide-list-stats.md` |
| 关联页签、关联视图、association、页签显示布局、关联数据筛选、set-filter | `references/form/guide-form-association.md` |
| 表单按钮、button、自定义按钮、视图按钮、行上、行末下拉、右上、打开视图、打开布局、发起流程、按钮预填、按钮字段映射、action-set | `references/form/guide-form-button.md`；`references/common/ref-cli-commands.md` |
| 表单消息提醒、消息提醒、表单数据提醒、数据变动提醒、新增数据提醒、form message、提醒对象、推送渠道、IM提醒、云桥、短信提醒 | `references/form/guide-form-message.md`（表单数据新建/修改/删除时提醒人；列表是应用级、`--obj-id` 本地收口；提醒对象四类写法与同名歧义处理） |
| 流程消息、编号规则、超时处理、退回设置、指定流转、投票、机器人节点、公用流转片段、子流程、人员范围、节点菜单、流程设置、流程存档、节点校验、提交校验、角色/权限/成员 | `references/common/ref-cli-commands.md` |
| 签署顺序、会签、非会签、竞签、或签、依次处理、抄送、operator-sign | `references/workflow/guide-workflow.md`；命令速查 `references/common/ref-cli-commands.md` |
| 分类搜索、表单权限、编译/build/compile/check、skill 文档/skill sync/copy/root、CLI 命令速查 | `references/common/ref-cli-commands.md`（分类搜索四类字段：选项 / 浏览框 / 日期 / 系统字段） |
| 页面设计器、配置式页面、仪表盘、看板页、designer、page create、comp-add、工厂模板、factory、组件模板、页面布局、designer layout/save、页面版本、version revert、发布页面菜单、publish-menu、**自定义CSS、组件样式、改样式、选择器、DOM结构、样式不生效、designer css、designer dom** | `references/ebuilder-designer/guide-designer.md`（布局层）；组件配置见 `guide-designer-components.md`，**自定义 CSS 与 DOM 结构索引见 `guide-designer-css.md`**，工厂模板见 `guide-designer-factory.md`，版本见 `guide-designer-version.md`，命令速查见 `references/common/ref-cli-commands.md`「页面 & 设计器」节 |
| HRM、矩阵、条件矩阵、部门矩阵、分部矩阵、matrix、映射表、行 id、rowId | `references/hrm/guide-matrix.md` |
| 报表、设计器报表、EDC 报表、report build、新建报表、数据集、报表列、报表查询条件、报表权限、报表快照、report | `references/report/guide-report-build.md`（建表主干）；改已有报表见 `guide-report-modify.md`，查询条件见 `guide-report-query.md`，命令速查见 `ref-report-commands.md`；踩坑先扫 `ref-report-pitfalls.md` |
| 报表多数据源、跨数据集、跨表关联、主从报表、两个表单合成一张报表、父格筛选、subordination、leftFilterField、render 渲染回读 | `references/report/guide-report-multisource.md`（spec 写法 + 区域/入口格 + 双保存与关预聚合 + 验证） |
| 报表单元格、父格、扩展方向、合并、冻结、隐藏行、条件格式、数据条、图标集、tableName、字段三件套 | `references/report/ref-report-pitfalls.md` + `report-data-model.md`（枚举）· `layout-showlocation-freeze-guide.md`（冻结/居左）· `hidden-row-and-header-merge-guide.md`（空白行与表头合并） |

> 组件文档（Button/Table/Input/Upload 等）在 `references/` 中按文件名查找。完整索引见 `_catalog.md`。

> **表单自带默认台账** — 普通列表需求先查询并复用已有默认台账，记录实际名称/listId；“客户信息表／客户信息”这类简称差异不构成新建理由，默认保留原名，不统一去掉“表”字。仅名称需对齐时应改名而非另建。用户明确要求额外表格视图时，用 `form table-view create` 原子完成 `nListView` 创建、显示列配置和回读；禁止用 `form view create --type tableView` 创建空壳。`formView` 使用 `form view create` 后必须执行 `form view populate`。

---

## 能力边界

> 不支持的能力、以及「CLI 没有命令时怎么办」的判定方式 → `references/common/capability-boundaries.md`。禁止声称平台/CLI 支持实际不支持的能力，禁止用临时脚本或浏览器操作绕行。

---

## 页面编码

页面是搭建的最后一步，动手前确保应用、表单、流程已建好。优先用设计器配置式页面（`page create` → `designer comp-add --template` → 绑数据 → `designer save` → `page publish-menu`），详见 `references/ebuilder-designer/guide-designer.md`；只有设计器无法满足的深度定制才用 Ecode React，编码规范与模板见 `references/coding/guide-page-code.md`。

