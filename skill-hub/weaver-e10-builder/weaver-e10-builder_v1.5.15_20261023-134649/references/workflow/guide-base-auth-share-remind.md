# 工作流基础设置：权限、共享、提醒

命令名取自前端目录 `pathset-base-authset`、`pathset-base-shareset`、`pathset-base-remind`。配置的是工作流定义，参数使用 `workflowId`，不是流程实例 requestId。当前验证环境为 107，原生工作流；不据此宣称 EB、公文及个人工作流已验证。

## 共同规则

- `get --schema` 读取实时表单、枚举、浏览范围及默认值。所有命令输出 JSON，支持 `--out 文件`。
- `create/update --data '{...}'` 或 `--data @文件.json`。单份配置的 create 是读取默认/现有配置后保存，不重复建第二份。
- 修改先读后合并，只改明确的键；`false` 和 `[]` 是有效修改。拒绝未知字段、无效选项和跨流程节点，保存一次后回读；失败不自动重复写入。
- ID 用字符串。节点浏览值用名称或 ID 数组，重名时改用 ID。组织对象用 `[{"_entityType":"user","id":"人员ID"}]`；支持 user/dept/subcompany/group/role/all，以该位置允许类型为准。错误提醒人只支持 user/role/employeeManager。非 all 对象会从服务端按 ID 核实。
- 初始化可能创建配置记录；回读比较的是业务设置，记录 ID、创建/更新时间可变化。没有服务端并发版本控制，编辑期间应避免多人同时保存同一配置。

## 权限设置

```bash
e10-cli workflow base auth-set get <workflowId> --schema
e10-cli workflow base auth-set update <workflowId> --data '{"statistics":[{"_entityType":"user","id":"人员ID"}]}'
```

| 字段 | 设置 |
|---|---|
| maintenance | 维护权限；不包含删除工作流权限 |
| statistics | 统计权限 |
| statisticsExport | 统计数据导出权限，也影响统计导入 |
| containSubDept | 包含下级部门，boolean |

每组组织对象支持 `[]` 清空；没有指定的组保持原值。

## 共享设置

```bash
e10-cli workflow base share-set get <workflowId> --schema
e10-cli workflow base share-set update <workflowId> --data '{"defSharerCanViewComment":false}'
e10-cli workflow base share-set default get <workflowId> --schema
e10-cli workflow base share-set default update <workflowId> --data '{"commonTiming":"1","commonMultiNode":["审批节点ID"]}'
```

基础字段：`defSharerCanViewComment`（默认共享人查看意见/评论）、`allowAddNoDefShare`（允许添加非默认共享）、`sendRemindTiming`（数组，1 添加默认共享时、2 添加非默认共享时）。

默认共享字段：`defaultShareType` 为 0 通用 / 1 按条件共享；`commonTiming` 为 0 创建 / 1 到达节点 / 2 离开节点；`commonMultiNode` 为节点；`shareUsers` 为组织对象。到达/离开模式必须指定节点。切换共享模式是显式操作，不随规则新增隐式切换。不会执行“更新/删除历史流程默认共享”。

### 按条件共享

```bash
e10-cli workflow base share-set default update <workflowId> --data '{"defaultShareType":"1"}'
e10-cli workflow base share-set rule create <workflowId> --data '{"isEnable":false,"shareMultiNode":["节点ID"],"shareConditionUsers":[{"_entityType":"user","id":"人员ID"}],"condition":{"rules":["system:流程标题:包含:申请"],"relation":"AND"}}'
e10-cli workflow base share-set rule get <workflowId> --schema
e10-cli workflow base share-set rule update <workflowId> --rule-id <规则行ID> --data '{"shareTiming":"2"}'
e10-cli workflow base share-set condition get <workflowId> --rule-id <规则行ID>
```

字段：`shareConditionUsers`、`shareMultiNode`、`shareTiming`（1 到达 / 2 离开）、`isEnable`、`condition` 或 `shareCondition`。

新增时 `shareTiming` 取实时列默认值，`isEnable` 优先取列默认值，服务端未声明时继承前端程序 `newAddTableList` 的 true。示例特意设 false，便于先核对规则再启用。

`condition.rules` 使用已有条件编译器的 `system:字段:关系:值` / `form:字段名或ID:关系:值` 语法；`relation` 为 AND/OR，默认采用条件编辑器服务端 relation。表单字段、数字范围、明细量词等语法见[条件指南](guide-workflow-condition.md)。本命令始终使用共享条件 source=24，不能拿出口 source=2 替代。输入新 condition 时生成新条件引用，只替换该行；不会原地修改可能被其他行引用的条件。规则保存失败可能留下尚未绑定的条件，勿盲目重试。

`shareCondition:{}` 表示无条件；非空 `shareCondition` 只允许复用此流程已有共享行的 conditionKey。公共规则引用向导、任意嵌套表达式和条件多语言编辑未在此命令实现。

### 共享字段权限

```bash
e10-cli workflow base share-set field-permission get <workflowId>
e10-cli workflow base share-set field-permission update <workflowId> --data '{"fields":[{"name":"单行文本","display":false}]}'
e10-cli workflow base share-set system-field-permission get <workflowId>
e10-cli workflow base share-set system-field-permission update <workflowId> --data '{"fields":[{"fieldType":"REQUEST_NAMEL","isview":false}]}'
```

普通字段支持 id 或唯一 name，只改 display。系统字段使用 get 返回的 fieldType，只改 isview；编辑/必填等属性及其他字段保持原值，不同步到节点。

共享字段权限固定使用 legacy，不提供 `--renderer` 参数，也不保留新版权限写入分支。工作流程和 EB 均先读取 `frame/getPathFrameInfo`，根据 `relateType=wea_form/wea_ebuilder` 判断类型；缺失、未知类型、业务失败或 formId 不一致时停止，禁止通过接口成功/失败推断类型。旧版接口读取完整明细，只修改明确指定字段的显示权限并回读，保留其他属性。

共享字段权限 legacy 接口契约：

| 类型 | 读取 | 保存 |
|---|---|---|
| `wea_form` | `/api/workflow/core/bridgeform/getFieldPermissionViewDataById` | `/api/workflow/core/form/formFieldPermission/saveNodeExtSet` |
| `wea_ebuilder` | `/api/ebuilder/flow/core/bridgeform/getFieldPermissionViewDataById` | `/api/workflow/core/form/formFieldPermission/saveNodeExtSet` |

读取参数为 `workflowId/formId/permissionId/nodeFormRelateId=-1`；保存携带 `share:true`、`nodeFormRelate.workflowId`、完整 `fieldPermission.permissionDetails`。EB 的旧接口可能没有 `initPermissionDetails`，按旧前端组件从 `fieldList/readFieldIds/writeFieldIds` 还原明细：复合控件 ComboSelect、DateInterval、MatrixComponent 的子字段继承父字段权限，Paragraph/SubTableControl 不可写；缺少必要列表则停止。已有明细保留原属性，不自行补默认权限。保存由 workflow/core 后端根据关联类型分发，不能将它替换为节点新版 `saveFieldPermission`。

## 提醒设置

```bash
e10-cli workflow base remind-set get <workflowId> --schema
e10-cli workflow base remind-set update <workflowId> --data '{"forceEndReceiver":[]}'
e10-cli workflow base remind-set detail get <workflowId> --src emailAndSmsRemind --schema
e10-cli workflow base remind-set detail update <workflowId> --src sysRemind --data '{"sysCcNoRemind":true}'
```

主设置：`remindType` 为数组（0 短信、1 邮件、2 系统）；`isCustomContent` 自定义内容；`forceEndReceiver` 为数组（0 结束节点操作者、1 未操作已查看、2 未操作未查看、3 发起人）；`errRemindCustom`、`errReminder` 为错误提醒自定义开关及组织对象。省略字段不清空。

详情渠道必须显式指定 `--src`：

| 渠道 | 字段 |
|---|---|
| sysRemind | sysRemindScope（0 全部 / 1 指定）、sysArchiveNoRemind、sysCcNoRemind、messageSenderCustom、messageSenderType（0 发起人 / 1 当前操作者） |
| emailAndSmsRemind | remindScope（0 全部 / 1 指定）、defaultRemindType（0/1 数组）、archiveNoRemind、ccNoRemind、chooseReminder、alterNodesType（0 全部 / 1 选择）、alterNodesBrowser |

默认渠道不能超出主设置已启用的渠道。指定节点模式需要先新增节点规则，不会隐式添加节点。详情两组完整读取并保留另一组。

### 指定节点提醒

```bash
e10-cli workflow base remind-set nodes get <workflowId> --src emailAndSmsRemind --schema
e10-cli workflow base remind-set nodes create <workflowId> --src emailAndSmsRemind --data '{"alterNodesBrowser":["节点ID"],"remindType":["0","1"]}'
e10-cli workflow base remind-set nodes update <workflowId> --src emailAndSmsRemind --rule-id <规则ID> --data '{"ccNoRemind":true}'
e10-cli workflow base remind-set detail update <workflowId> --src emailAndSmsRemind --data '{"remindScope":"1"}'
```

新增字段为 alterNodesBrowser/remindType/ccNoRemind，未指定项从服务端新增表单继承。修改字段为 reminders（渠道数组）、ccNoRemind、remindContentType（0 默认 / 1 自定义）。规则ID与节点ID不同；CLI 核实流程与渠道归属。

### 邮件、短信、系统消息模板

```bash
e10-cli workflow base remind-set templates get <workflowId> --content-type 1
# 流程级保存会被后端联动开启自定义；必须先明确设置该开关
e10-cli workflow base remind-set update <workflowId> --data '{"isCustomContent":true}'
e10-cli workflow base remind-set templates update <workflowId> --content-type 1 --event 10 --data '{"title":"待审批：[-313]"}'
# 节点模板需要先有该渠道节点提醒规则；省略 --node-id 是流程级
e10-cli workflow base remind-set templates get <workflowId> --content-type 0 --node-id <节点ID>
```

content-type：0 短信 / 1 邮件 / 2 系统。`--event` 取 get 返回的 remindType，不猜事件编号。模板字段为 content，邮件另有 title/isFormData/isSignData/isAttachmentData，后面三项以环境能力为准。字段占位符用 `[code]`，从 fields 获取，校验事件 hideSysFields。修改会保留其他事件、未指定属性及现有多语言元数据；本命令不提供多语言翻译编辑。

107 租户启用需审核的短信服务，产品本身不支持工作流或节点自定义短信内容，仅支持应用全局默认设置（前端 smsTemplateCheckFlag 对 WORKFLOW/NODE 返回 2）。CLI 查询返回 editable:false 和入口说明，写入明确拒绝；不会显示未生效的普通短信正文冒充有效模板。未开启审核的环境支持普通短信正文，但该分支尚无远端写入验证。邮件、系统消息已在关闭渠道且未启用的临时节点上原值保存并回读；流程级开关未改变，临时节点规则已移除。全局模板修改测试曾被自动审批拒绝，已改用这一安全验证；没有执行被拒绝脚本。
