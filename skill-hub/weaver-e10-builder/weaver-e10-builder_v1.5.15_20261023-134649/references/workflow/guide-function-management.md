# 工作流高级设置：功能管理

适用位置：工作流设置 → 高级设置 → 功能管理。以下命令配置流程定义，不对流程实例执行撤回、加审或减审操作。加审与已有的加签 `workflow add-step` 是不同功能。

## 命令与工作方式

| 命令组 | get | create | update |
|---|---|---|---|
| `workflow withdraw` 撤回 | 查询当前配置 | 初始化/保存单份配置 | 局部修改单份配置 |
| `workflow add-operator` 加审 | 基本设置+权限规则；`--rule-id` 查单条 | 新增权限规则 | `--rule-id` 改规则；不带则改基本/会签属性 |
| `workflow minus-operator` 减审 | 权限规则；`--rule-id` 查单条 | 新增权限规则 | 必须 `--rule-id` |
| `workflow receiver-range` 接收人范围 | 基础设置+普通模式明细 | 新增一条范围明细 | `--rule-id` 改明细；不带则改总开关 |
| `workflow forward-circulate-back` 转发/传阅/抄送收回 | 查询当前配置 | 初始化/保存单份配置 | 局部修改单份配置 |

每个命令的位置参数都是 `<workflowId>`。写入使用 `--data '{...}'` 或 `--data @配置文件.json`，只传用户明确要求的设置项。`get --schema` 返回本环境的字段、枚举和默认值；`--out 文件.json` 保存结果。长 ID 一律字符串，浏览字段使用 ID 数组。枚举既可用编码，也可用当前环境返回的选项中文原文。

新增规则先读服务端新增表单，未指定项继承默认值；修改先查询现有值，合并补丁后保存并回读检查。撤回和收回属于流程级单份配置，create 不会新增第二份；已有配置也保留未指定字段。未知字段、无效枚举、错误节点/规则归属会拒绝，不自动重复发送新增请求。

## 撤回管理

```bash
e10-cli workflow withdraw get <wf> --schema
e10-cli workflow withdraw create <wf> --data '{}'
e10-cli workflow withdraw update <wf> --data '{"remarkRequired":true,"allowRemind":false}'
```

| 字段 | 意义 / 可选值 |
|---|---|
| allowType | 能撤回的节点：`0` 选择，`1` 排除 |
| allowNodes | 对应节点 ID 数组 |
| beAllowType | 允许被撤回的节点：`0` 全部，`1` 选择，`2` 排除 |
| beAllowNodes | 对应节点 ID 数组 |
| allowRemind | 允许前台用户选择是否提醒，布尔值 |
| remarkRequired | 撤回时意见必填，布尔值 |
| doPreOperate | 启用节点前附加操作，布尔值；部分环境页面隐藏此项 |

自然语言示例：“把流程【名称/ID】的撤回意见改为必填，其他设置保留。”

## 加审 / 减审

```bash
# 查询实时默认值与当前规则
e10-cli workflow add-operator get <wf> --schema
# 新增仅针对这个审批节点的加审权限
e10-cli workflow add-operator create <wf> --data '{"allowNode":["节点ID"],"operatorType":["1"]}'
# 修改一条权限规则；不改节点范围或接收人范围引用
e10-cli workflow add-operator update <wf> --rule-id <ruleId> --data '{"operatorType":["1","2"]}'
# 加审基本设置
e10-cli workflow add-operator update <wf> --data '{"todoAfterBackTodo":true,"allowModifyBackTodo":["1"]}'
# 减审
e10-cli workflow minus-operator create <wf> --data '{"allowNode":["节点ID"],"operatorType":["1"]}'
e10-cli workflow minus-operator update <wf> --rule-id <ruleId> --data '{"operatorType":["1","2"]}'
```

权限规则字段：

| 字段 | 意义 / 可选值 |
|---|---|
| allowNodeType | `0` 全部；`1` 选择；`2` 排除 |
| allowNode | 节点 ID 数组；选择/排除时必填，按实时节点浏览范围校验 |
| operatorType | 数组：`0` 上一节点操作者，`1` 当前节点未操作者，`2` 当前节点已操作者，`3` 指定节点操作者 |
| operatorNode | 指定节点的 ID 数组；operatorType 包含 `3` 时必填 |

加审基本设置：`todoAfterBackTodo`（全部加审人审批后回本人待办）、`allowModifyBackTodo`（允许修改为 `["1"]`，关闭为 `[]`）；会签属性 `todoSignAttr` 本节点待办、`todoNoSignAttr` 非本节点待办、`doneSignAttr` 已办，以及各自 `Def` 默认会签属性。选项以 `get --schema` 为准（一般 `1` 跟随操作者、`2` 用户选择、`3` 会签、`4` 非会签、`5` 依次处理，部分字段不允许 `1`）。减审不写与加审共用的基本设置。

自然语言示例：

- “流程【ID】增加一条加审权限：允许在【1级审批】加审，由当前节点未操作者操作，其他用系统默认。”
- “把加审规则【ID】改为当前节点已操作和未操作人员均可操作，其余保持。”
- “流程【ID】增加减审权限，只针对【节点】，可由指定节点【节点】操作者操作。”

## 接收人范围：普通模式

范围统一使用 `workflow receiver-range`，支持以下三个上下文；本次仅支持普通模式，高级模式已有配置会被拒绝，避免覆盖。

| 页面位置 | 定位参数 | 后端场景 |
|---|---|---|
| 加审管理 → 权限行的限制接收人可选范围 | `--add-operator-id <加审权限规则ID>` | 10 |
| 指定流转 → 目标节点通用设置 → 接收人范围 | `--scene assign-flow --node-id <源节点ID>` | 6 |
| 指定流转 → 目标节点单独设置 → 接收人范围 | `--scene assign-flow-target --node-id <源节点ID> --target-node-id <目标节点ID>` | 7 |

CLI 自动解析并回读核对真实范围引用，不需要传 mainId 或 receiverRangeKey。加审规则 ID 不是范围明细 ID；指定流转的源节点 ID 不是目标节点 ID。单独目标节点设置须已存在，可先用 `workflow node-assign-flow targets <wf> <源节点ID>` 查询，缺少时先 `add-target <wf> <源节点ID> <目标节点ID>`。

```bash
e10-cli workflow receiver-range get <wf> --add-operator-id <addOperatorId> --schema
# 新增：指定部门；关系、安全级别未指定则沿用服务端默认
e10-cli workflow receiver-range create <wf> --add-operator-id <addOperatorId> --data '{"objtype":"10","dept":["部门ID"]}'
# 新增：指定分部
e10-cli workflow receiver-range create <wf> --add-operator-id <addOperatorId> --data '{"objtype":"11","subDept":["分部ID"]}'
# 修改一条明细，仅改变关系
e10-cli workflow receiver-range update <wf> --add-operator-id <addOperatorId> --rule-id <rangeRuleId> --data '{"relationship":"1"}'
# 启用限制（新增明细不会隐式打开总开关）
e10-cli workflow receiver-range update <wf> --add-operator-id <addOperatorId> --data '{"isopen":true}'
```

指定流转使用相同的 `get/create/update` 和普通明细参数：

```bash
# 查询通用范围及当前环境默认值
e10-cli workflow receiver-range get <wf> --scene assign-flow --node-id <源节点ID> --schema
# 通用范围新增指定部门，仅适用于操作者；其他参数读取默认值
e10-cli workflow receiver-range create <wf> --scene assign-flow --node-id <源节点ID> --data '{"objtype":"10","dept":["部门ID"],"suitableType":"1"}'
# 启用限制，并限定在目标节点操作者范围内
e10-cli workflow receiver-range update <wf> --scene assign-flow --node-id <源节点ID> --data '{"isopen":true,"limitOperatorRange":true}'
# 单独目标节点范围：新增指定分部，仅适用于抄送人
e10-cli workflow receiver-range create <wf> --scene assign-flow-target --node-id <源节点ID> --target-node-id <目标节点ID> --data '{"objtype":"11","subDept":["分部ID"],"suitableType":"2"}'
# 局部修改单独范围某一条明细的适用类型，保留对象、安全级别和关系
e10-cli workflow receiver-range update <wf> --scene assign-flow-target --node-id <源节点ID> --target-node-id <目标节点ID> --rule-id <明细ID> --data '{"suitableType":"全部"}'
```

指定流转额外支持：基础字段 `limitOperatorRange`（只能在目标节点操作者设置范围内选择）；明细字段 `suitableType`（`0` 全部、`1` 操作者、`2` 抄送人，也可传中文标签）。前者启用后与明细范围取交集，目标节点操作者无法计算时可选人员为空。新增明细不会自动启用限制或指定流转，须按需求分别设置。`workflow node-assign-flow` 仍负责指定流转基础/通用属性；原 `range` 子命令保留兼容，完整普通模式范围使用此统一命令。

自然语言示例：“把流程【ID】源节点【ID】的指定流转通用接收人范围设为普通模式，新增指定部门【名称】，只适用于操作者，启用限制，其他设置不变。”单独设置请明确：“源节点【ID】到目标节点【ID】的单独范围”。先查询现有明细，已有匹配项用 update，避免重复新增。

| objtype | 接收人类型 | 其他字段 |
|---|---|---|
| 0 / 1 / 2 / 3 / 4 | 本部门 / 直接上级部门 / 所有上级部门 / 下级部门 / 所有下级部门 | 无浏览值 |
| 5 / 6 / 7 / 8 / 9 | 本分部 / 直接上级分部 / 所有上级分部 / 下级分部 / 所有下级分部 | 无浏览值 |
| 10 | 指定部门 | `dept` ID 数组；安全级别 |
| 11 | 指定分部 | `subDept` ID 数组；安全级别 |
| 12 | 指定人员 | `person` ID 数组 |
| 13 | 指定角色 | `role` ID 数组；`rolelevel` 成员级别；安全级别 |
| 14 | 指定岗位 | `job` ID 数组；`joblevel` 岗位级别；`joblevelBrowser` 对应组织 ID 数组 |
| 15 | 所有人 | 安全级别 |

通用 `relationship`：`0` 包含、`1` 排除。安全级别 `seclevel` 为 `"最小值,最大值"`，如 `"0,100"`，合法边界 -999 至 999；只在组织已启用安全级别且该类型支持时可设置，默认从服务端读取。角色级别通常 `0` 总部、`1` 所有级别、`2` 分部及总部；岗位级别 `0` 总部、`1` 指定部门、`2` 指定分部，非总部时需要 joblevelBrowser。以实时选项为准。

注意接口特性：

- 第一次查询可能由服务端创建范围主记录并关联加审权限规则或目标节点单独配置，行为与打开页面弹窗一致。
- `enableSecurityLevel`、`isUpgrade` 是服务端能力信息，不能通过此命令修改。
- 后端没有按 ID 修改明细的接口。CLI 先新增并回读核对，验证通过才删除旧明细，再检查其他明细未变。结果返回 `previousRuleId` 与新的 `ruleId`，后续必须使用新 ID。
- 新项校验失败会尝试清理新项并保留旧项；清理/删除失败会报告相关 ID，应先查询现状，不要重复新增。替换不是服务端事务，请避免同时编辑同一范围。

自然语言示例：“给流程【ID】的加审规则【ID】限制接收人范围，普通模式，包含本部门和指定分部【名称】，启用限制，其他不变。”执行时先查询规则、解析真实分部 ID，再分别新增范围明细、启用总开关。

## 转发 / 传阅 / 抄送收回

```bash
e10-cli workflow forward-circulate-back get <wf> --schema
e10-cli workflow forward-circulate-back update <wf> --data '{"forwardBackCondition":["1"],"forwardAllowBack":false}'
```

| 字段前缀 | 功能 | 后缀 BackCondition | 后缀 AllowBack |
|---|---|---|---|
| forward | 转发 | 收回条件数组：`1` 查看前、`2` 查看后；`[]` 清空 | 接收人批注后允许收回 |
| circulate | 传阅 | 同上 | 接收人批示后允许收回 |
| cc | 抄送 | 同上 | 接收人批注后允许收回 |

自然语言示例：“流程【ID】的转发只允许查看前收回，批注后不允许收回，传阅和抄送保持原样。”

## 源码验证入口

修改后在 CLI 项目内运行 `npm run build`，随后可直接用 `node dist/index.js workflow ...` 测试，不需要先打包或全局安装。开发时也可用 `node --import tsx src/index.ts workflow ...`。自然语言测试依赖执行方加载此文档；CLI 本身接收结构化命令，不直接解析整句自然语言。
