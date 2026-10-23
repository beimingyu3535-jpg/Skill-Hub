# 规则集（`LogicFlowSet`）

## 何时使用

创建动作流中的规则集节点，引用当前租户已有规则集完成复杂规则判断或计算。

## 先查询

获得当前租户规则 Browser 原对象。

## 不可猜测

不在动作流中创建或编辑规则定义；没有真实规则对象即停止。

## 最小计划

`logicFlow`；可选 `inputParams` 必须为前端规则参数设计器回读的单表 `ParamMappingBean`。

`logicFlow` 是固定 Browser 动态赋值对象，不支持上下文、变量、常量或公式。规则名称会通过当前租户的 `/api/logicflow/common/browser/complete/rule` 查询，并必须唯一匹配真实规则对象；计划中可使用 `{"kind":"fixed","value":["规则名称"]}`，生成后会回填为规则 Browser 对象数组。

`logicFlow` 不是规则定义本身，而是当前租户规则 Browser 原对象数组，至少包含真实 `id` 和 `name`。`inputParams.tableData` 使用规则集外部设计器的 `ParamBean` 字段类型：`paramType` 表示字段类型，`dataType` 表示 `attribute/node`，结构化字段通过 `parentId` 关联，动态赋值放在行的 `formulaData` 中；参数设计器返回的展示字段也要原样保留，不能套用其他组件的参数归一化规则。

规则 Browser 解析出真实规则 ID 后，CLI 会请求 `/api/component/logicflow/esb/info/{ruleId}`，使用响应 `data.input` 的 `tableData` 生成 `inputParams`。因此不需要手工猜测规则的输入参数结构；如果计划中已经为同一个 `paramKey` 提供 `formulaData`，CLI 会把该赋值合并回详情接口返回的对应参数行。
