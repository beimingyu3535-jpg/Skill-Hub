---
name: generating-actionflows
description: "根据自然语言需求查询当前 Weaver 环境的真实对象与字段，生成并暂存 ESB 动作流，回读后返回设计器链接。默认只通过 CLI 运行，不读取或修改 Skill 内部实现；仅在用户明确要求维护、修复或新增 Skill 组件时才进入维护模式。"
---

# 动作流智能生成

将需求编译为“触发器 → 动作链 → 结束”的动作流。先发现真实平台数据，再生成；不要根据名称、历史场景或示例猜测任何平台对象。

## 工作模式

- **运行模式（默认）**：用户要创建、预览、检查或生成动作流时，只运行 `python scripts/actionflow_skill.py <command> '<json>'`。可按任务需要读取 `references/` 中的业务规则或组件示例，但不得读取或修改 `scripts/`、组件实现、测试或任何 Skill 文档；组件契约一律通过 `component-search` 和 `describe` CLI 获取。
- **维护模式（显式授权）**：仅当用户明确要求“修复 Skill”“修改 Skill”“审计/新增组件”“查看源码/转换器/测试”时，才读取或编辑 Skill 内部文件。完成后运行回归检查。

运行失败时，运行模式只能返回 CLI 的错误和所需真实对象；不得擅自查看源码或修改 Skill 来绕过错误。需要修复时先征得用户明确授权进入维护模式。

## 默认规则

1. 所有流程、表单、字段、人员、资源和选项均从当前环境查询；查不到即说明缺失，不伪造 ID 或原生对象。对平台明确必填、但用户未指定且不改变业务映射语义的操作人，允许从当前租户人员浏览器选择一个真实可用人员；必须在结果的 `autoResources` 中说明选择结果和原因。
2. 先用 `component-search` 选组件，再用 `describe` 读取所选组件的完整契约。不得读取组件源码替代 CLI；需要业务规则、条件示例或组件用法示例时，可按需读取对应 `references/` 文件。
3. 用户给出的映射优先，但每条动态映射都必须用本次 `component-context` 返回的原始 `paramKey`。Plan 中禁止传 `FormData.*`、`ApprovalData.*` 等设计器公式路径；它们只由编译器生成。不同触发器的数据 ID 键不同，必须读取本次结果，不能套用 `.5`、`.id` 等历史路径。编译器同时校验来源字段的真实名称、主/明细作用域和类型；名称明显无关或类型不兼容时暂停，不得因为 ID 存在而暂存。日期条件中的“当前/昨天/明天”等使用系统日期值，不在生成时固化；流程“归档/结束”统一为 `workflow_completed`。只有用户明确确认跨语义映射时才传 `confirmSemanticMismatch=true`。只有用户没有给映射时才自动映射，并报告每条自动映射的依据。
4. 组件契约、转换器和校验器是参数、默认值、DTO 与支持范围的唯一事实源；文档不替代程序校验。
5. 默认使用暂存并执行 `getStashSnapshot` 回读。暂存成功即可返回链接；回读异常须明确提示，不能伪称“暂存验证通过”。
6. 动作流名称默认加 `AI-` 前缀；凭据和环境配置只存放在 Skill 外部的 `%USERPROFILE%\.weaver-actionflows` 或环境变量中。

## 执行流程

1. 将每个场景作为独立事务处理。一次只处理一个：识别该场景的触发、动作、真实对象及可选映射/条件；用户给出的名称只作查询关键词。不得预查询、预组装或生成后续场景。能通过平台查询确定的信息直接查询；只有多个业务选择都合理、映射或固定值会改变结果、条件含义不明确或能力未支持时，才暂停确认。
2. 查询所需真实对象：流程用 `workflow-browser-list` 与 `workflow-nodes`；需要读取流程绑定表单（含明细）时用 `workflow-context-fields`，不得把只返回回写候选的 `workflow-fields` 当作完整字段结构；独立 e-builder 表单依次用 `form-applications`、`form-list`、`form-fields`；人员用 `recipient-search`。
3. 用 `component-search` 找候选，`describe` 读取选中组件。需要来源字段时，先为当前节点调用 `component-context`，不沿用别的触发器或旧环境的字段引用。
4. 跨节点动态赋值或引用上游数据时，先调用 `component-context` 与 `form-fields`，再按 `describe` 组装参数；条件、if/else 或筛选记录可按需读取 `references/condition_rules.md`，但最终参数必须以 CLI 返回的契约与校验结果为准。
5. 组装 `semantic_plan`，交由 `generate` 编译、校验、暂存和回读。不要自行补 `Output`、平台内部字段或未在 `describe` 中声明的参数。
6. 对当前场景完成生成、暂存、回读后，立即向用户返回名称、状态与可点击设计器链接，再开始下一场景。批量任务结束后另附汇总表；不得等全部场景完成才集中返回链接。一个失败不阻断其他场景，但不得因为失败预取后续场景的数据。

## 暂存结果

完整设计暂存成功时返回链接和 `saved=true`。若完整设计未通过但保底骨架暂存成功，也返回链接，并标记 `fallbackSaved=true`，提示需要人工补全。保底同样执行回读。快照接口失败时只重读同一版本一次；回读发现语义差异时，只有已登记的安全修复器才允许生成一次修正版。缺少真实对象、权限/接口错误、平台未支持能力、条件限制、资源缺失、类型不兼容或语义不明确时直接停止，不浪费重试。

修正回读发现的问题时，新建修正版；修正版暂存成功后，在下一次 `generate` 或 `generate-multi` 请求中传入旧版 `recycleAppId`，系统自动软回收旧版。修正版未暂存成功时保留旧版，不自动删除。

## 能力边界

只使用 `scripts/components/` 已登记组件及其 `describe` 中的属性。未登记组件、未声明属性或缺少真实 Browser/Upload 对象时，明确报告未支持。不可创建或修改流程定义、表单结构；不伪造循环、并发或外部资源配置。

## 命令速查

所有命令均通过：`python scripts/actionflow_skill.py <command> '<json>'`。

| 目的 | 命令 |
|---|---|
| 查流程 | `workflow-browser-list`、`workflow-nodes`、`workflow-context-fields`；`workflow-fields` 仅用于回写候选 |
| 查表单 | `form-applications`、`form-list`、`form-fields` |
| 查人员与会议字段 | `recipient-search`、`meeting-fields` |
| 发现与确认组件 | `component-search`、`describe` |
| 获取节点上下文 | `init-actionflow`、`prepare-context`、`component-context` |
| 暂存并回读 | `generate '{"plan":{...},"appName":"名称"}'` |
| 读取已有暂存 | `stash-readback '{"appId":"...","versionId":"..."}'`（`readback` 为别名） |
| 仅检查设计 | `generate '{"plan":{...},"previewOnly":true}'` |
| 批量独立生成 | `generate-multi` |
| 管理外部环境 | `env-list`、`env-current`、`env-switch`、`env-add`、`env-delete` |

含复杂 JSON 时优先使用 `generate` 的 `planFile` 参数，避免 shell 转义改变内容。
