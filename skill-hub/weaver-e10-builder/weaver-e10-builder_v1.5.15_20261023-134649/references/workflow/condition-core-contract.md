# 公共条件能力与业务适配契约

## 边界与顺序

出口条件是第一迁移点。先用正式 `workflow condition add` 验证编译、保存、绑定及 `get --tree` 回读，再迁移其他场景。矩阵规则与节点字段校验不接入此核心。

`compileWorkflowCondition` 负责语法、类型、字段/浏览对象解析，返回 `{relation, childrens}`；不写入。`persistWorkflowCondition` 在 sourceId=-1 上新建条件集合并保存，返回 conditionKey；业务适配层绑定引用。替换时不先删除旧条件；绑定失败保留原引用，并报告新条件 key。未绑定的旧条件不自动删除，避免误删其他引用。

## 各场景

| 场景 | source | 字段/条件上下文 | 业务绑定 |
| --- | --- | --- | --- |
| 出口 | 2 | workflowId，解析时 sourceId=linkId；保存新集合 sourceId=-1 | nodeLink/saveLinkConditionKey |
| 操作者批次 | 3 | workflowId，解析时 sourceId=operatorSetId | saveOperatorGroup 的指定行 conditionId；保留全部原操作者属性及其他行 |
| 默认共享 | 24 | workflowId，sourceId=-1 | ShareConfig/saveConfigCondition 的共享行 shareCondition |
| 子流程触发 | 7 | workflowId；明细触发带 detailTable=true、detailTableId=triSource | subWf/saveSet 的 ruleId/ruleName，重读原配置再更新 |
| 权责表分支 | 2 | belongScene=3、belongSceneId/segmentId=authRespId；独立表 workflowId=-99999999、variable 元数据 | 保留原 saveConditionSet/saveCondition + saveLinkConditionKey + 权责表行保存流程 |

权责表使用编译结果而保留业务入库方式，不能丢失变量类型、场景和片段同步上下文。原始 childrens 是有效高级输入，保留；不把它当成第二套自然语言解析器。

## 代码核对依据

- 前端 `weapp-workflow/src/components/public/rule/api/ruleDesign.ts`：条件编译结果保存与 getExpressionBean 回显。
- 前端 `.../nodeset/operatorset/store.ts` 的 editGroupItemDatasConditionByIndex：只更新 conditionId、condition、groupCondition、conditionSourceId，与操作者类型独立。
- 后端 `.../pathnode/cmd/operator/DoSaveOrUpdateNodeOperatorCmd.java`：conditionId 作为条件 key，既有 operatorSetId 保持更新语义。
- 子流程前端 `.../pathset/subwf/baseSetEdit.tsx`：条件保存回调绑定 ruleId/ruleName。
- 子流程后端 `.../pathnode/cmd/subwf/GetBaseSetCmd.java#getRuleParams`：明细触发必须携带 detailTable/detailTableId。
- 后端 `.../condition/cmd/WfpGetFormfieldListCmd.java`：按 belongScene/belongSceneId 解析权责表变量。
- 后端 `.../pathnode/cmd/link/SaveLinkConditionKeyCmd.java`：虚拟流程出口仍由 linkId + workflowId 查找；segmentId 控制片段条件同步。

## 兼容与纠错

- 字段 ID/名称/dataKey/columnName；有歧义要求 ID。明细合计与明细原字段可能共享 ID，必须分别保留；直接 ID 指普通字段，合计用合计名称。
- 范围为开区间；闭区间使用大于等于、小于等于两条。拒绝旧语法中会被忽略的多余参数。
- 浏览名称必须唯一精确匹配，支持准确 ID 或结构化 `{id,content}`；保留选项 valueKey=0。
- Switch 是/否编码为 SwitchCompareOptionLeft=5、SwitchTextValueLeft1=1/0；Bool 使用 23/24。107 实际接口已证明二者不相同。
- 系统人员/组织使用 Browser 前缀；紧急程度/密级使用 SysBrowser。
- 明细任一/所有分别为 detailOption=1/2；合计不带 detailOption。
- 结构化输入支持任意嵌套 AND/OR，避免字符串里的冒号/竖线歧义。

## 验证对象

107 独立测试流程 `1328015591882129414`，表单 `1328015587520053248`。
出口第一阶段：CLI 入口测试 13 个测试组通过；实环境保存并回读数值/日期八种比较、文本六种比较、范围、字段比较、明细任一/所有及合计、人员、分部、选项、开关、系统条件、AND/OR 子组及替换绑定。
原始 JSON 回读存放于 `output/condition-core-regression/`；这些结果验证配置持久化，不代表已执行真实流程实例。


第二阶段实环境结果：
- 指定人批次 `1328020561216045057`，公共条件 key `1328020694334865409`；CLI 自动比对原操作者字段未变。
- 共享规则 `1328021059283222553`，source=24 条件 key `1328021059298033665`，停用。
- 子流程配置 `1328021080909053952`，source=7 条件 key `1328021179523563520`，停用。
- 独立权责表 `1328021896900542464`（baseId `1328021896900542465`），变量条件 key `1328022412372115475`，普通变量与嵌套 OR 回读通过。
- 较早的回归权责表 `1328021205488271361` 保留用于对照变量量词修复；不用于业务。

清理复核：src/test 中不再有 buildConditionChildrens/saveWorkflowCondition 的调用，已删除旧实现。SYSTEM_FIELDS 等常量保留给公共编译器及节点校验。--batch-condition 只写描述、不生成条件引用，已删除并用 operator-batch set-condition 替代。workflow save-condition 与权责表 raw childrens 仍是有效高级入口，保留，不误删。

限制：配置验证不等同于流程实例执行。独立测试表单的 Switch 由现有 add-field 创建时没有选项文案，107 条件中文显示为空；完整树已回读确认 1/0 正确。旧 Bool 编码在真实 Switch 上会丢值，已修复。

最终验证：构建通过；针对性测试 120 项通过、0 失败。另在107验证上级操作者、表单人员本人批次及明细子流程条件。见 output/condition-core-regression/verification.json 和 test-result.txt。

准确ID验证：人员 1259330131187138561 与分部 1259330045288693760 通过正式 CLI --preview 解析成功。纯数字ID走 common/browser/destData/{type}，名称走 complete/{type} 精确匹配；不能用联想接口搜索ID。

准确ID路径修复后的末次 CLI 回归：15 项通过、0 失败（在前述 120 项测试基础上复测 CLI 套件）。
