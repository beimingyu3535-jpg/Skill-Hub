# 拟签意见、节点转发与节点签字意见

本地开发使用 `node dist/index.js` 替换下文的 `e10-cli`。先运行 `npm run build`，使用目标测试环境的已有登录态；不需要打包或重新全局安装。所有长 ID 都使用字符串。

三个命令都先读取服务端现有值或默认值，再合并 `--data` 中明确指定的项，保存一次后回读核对。未指定项保留；未知字段、无效枚举、未匹配名称提前报错。`--data` 支持 JSON 或 `@文件`，`--out` 保存不含认证信息的结果。`create` 对单份配置表示初始化/保存，不新增第二份同类配置。

## 拟签意见：workflow draft-opinion

```bash
# 流程展现设置及环境支持的选项
e10-cli workflow draft-opinion get <workflowId> --schema
# 查询布局中已保存的拟签控件，取得 widgetId（不是普通字段ID）
e10-cli workflow draft-opinion fields <workflowId>
e10-cli workflow draft-opinion get <workflowId> --widget-id <widgetId> --schema
# 修改控件的意见显示方式
e10-cli workflow draft-opinion update <workflowId> --widget-id <widgetId> \
  --data '{"typeAfSign":"显示全部意见"}'
# 开启流程自定义展现，弹窗填写，正序显示
e10-cli workflow draft-opinion update <workflowId> \
  --data '{"openCustomSet":true,"pcFillMethod":"弹窗填写","opinionOrder":"正序"}'
```

流程展现参数（枚举支持 ID 或服务端完整中文名称，以 `get --schema` 为准）：

| 参数 | 含义 |
|---|---|
| openCustomSet | 启用本流程自定义展现；关闭时读取应用级默认设置 |
| openTextarea | 是否使用纯文本意见输入框 |
| defautFont / defaultFontSize | 意见默认字体/字号；defautFont 是接口原拼写 |
| showBlank / openSearch | 显示空的意见/启用意见搜索 |
| opinionOrder | 0正序、1倒序 |
| showLog | 显示操作日志 |
| pcFillMethod | 1弹窗填写、2直接填写 |
| alertEndCountersign | 提交流程时弹出结束拟签提示 |

控件参数：

| 参数 | 含义 |
|---|---|
| opinionType | 0多人编辑同一条意见、1一个人一条意见 |
| enableCountersign | 启用组织意见拟签；开启前需已有结束拟签操作者或节点配置 |
| conterSignType | 拟签组织维度，按环境 schema 选择（接口原拼写） |
| typeBfSignDepart / typeBfSignSubcom | 结束拟签前的查看方式；按当前部门/分部维度使用对应参数，两项对应同一存储字段 |
| typeAfSign | 意见展示方式，例如显示最后一次意见/显示全部意见，以 schema 为准 |
| enableCopyClear / copyClearOperate / copyClearNode | 启用抄清、抄清操作者模式、节点名称或字符串 ID 数组 |
| enableGenerateRecord / agentRecordOperate / agentRecordNode | 启用代录、代录操作者模式、节点名称或字符串 ID 数组 |

既有的结束拟签操作者、抄清/代录人员范围引用会保留。选择节点操作者时，必须已有对应节点及人员范围。组织拟签结束人员、抄清/代录范围子弹窗的新增尚未接入此命令。切换“多人编辑同一条意见”不会悄悄关闭抄清/代录，须显式关闭后二次设置。

本命令配置**已存在并保存的拟签控件**，不向节点布局自动插入新控件。尚无控件时先在布局设计器添加并保存，再执行 `fields` 查询。

### 显示内容与按钮样式

```bash
e10-cli workflow draft-opinion content get <workflowId>
e10-cli workflow draft-opinion content update <workflowId> \
  --data '{"displayContent":"<p>$f_opinionContent$</p>"}'
e10-cli workflow draft-opinion style get <workflowId>
e10-cli workflow draft-opinion style update <workflowId> \
  --data '{"fontSize":"14","buttons":[{"menuKey":"fill","customName":"填写拟签","menuColor":"#336699"}]}'
```

`content` 的 `displayContent` 是 HTML 模板，不是对运行中流程填写意见；可用占位符由 `content get` 返回。CLI 负责 URL 编码。模板/样式首次保存前会读取主配置以完成服务端初始化。

`style` 可写 `menuFont`、`fontSize`、`buttons`。每个按钮以 `menuKey` 定位，可改 `customName`、`menuColor`、`menuFontColor`、`menuBorderColor`、`menuOrderNum`。未指定按钮和属性保留，调序不得重复。`fill` 为填写意见，其他 key 以查询结果为准。

模板和按钮样式的保存不隐式开启 `openCustomSet`，需要采用流程自定义展现时明确开启。`fieldSet/displayContent/menuStyle/logviewer` 在流程配置中只是齿轮状态，不能当开关写入。日志查看人员权限、应用全局设置不在本命令范围内。

## 节点转发：workflow node forward-setting

```bash
e10-cli workflow node forward-setting get <workflowId> <nodeId>
e10-cli workflow node forward-setting update <workflowId> <nodeId> \
  --data '{"todo":{"isForward":true,"allowSubOpt":false},"done":{"isForward":true,"allowSubOpt":true}}'
```

顶层三组：`todo` 待办、`done` 已办、`end` 结束。每组支持：

| 参数 | 含义 |
|---|---|
| isForward | 是否允许转发 |
| allowSubOpt | 转发接收人是否可提交意见 |
| allowForward | 转发接收人是否可继续转发 |
| allowSubOptCusName | “可提交意见”自定义名称，空串恢复默认名称 |
| allowForwardCusName | “可转发”自定义名称，空串恢复默认名称 |

开关用 true/false 或 0/1。开启转发时不会顺便重置未指定的接收人权限。这个命令与 `forward-circulate-back`（收回设置）不同。节点转发菜单的启用仍用 `workflow node menu`；本命令不修改接收人范围，不执行“保存并同步”。

## 节点签字意见：workflow node sign

原命令及 `--all-required`、`--none-required`、`--select` 保留。

```bash
e10-cli workflow node sign <workflowId> <nodeId> --schema
e10-cli workflow node sign <workflowId> <nodeId> --options viewTypeDto
e10-cli workflow node sign <workflowId> <nodeId> --options signOperateTypeList
e10-cli workflow node sign <workflowId> <nodeId> --select '退回,加签'
e10-cli workflow node sign <workflowId> <nodeId> \
  --data '{"hideInput":true,"viewTypeSelectDto":"1","viewTypeDto":["批准/确认","拟签意见"],"viewEmptyNotShow":true,"signOperateTypeSelect":"1","signOperateTypeList":["批准/确认"]}'
```

| 参数 | 含义 |
|---|---|
| mustInputDto | 0全部不必填、1全部必填、2按操作类型 |
| inputOperateTypeSelectDto + inputOperateTypeDto | 意见必填操作类型的模式与列表 |
| hideInput | 意见输入框不显示（只对不必填的操作生效） |
| signOperateTypeSelect + signOperateTypeList | 必须使用签批或签名的操作类型 |
| hideArea | 意见及评论区域不显示 |
| viewTypeSelectDto + viewTypeDto | 意见列表显示类型 |
| viewEmptyNotShow | 空意见不显示 |
| viewRangeSelectDto + viewRangeDto | 意见显示节点范围 |
| notSeeEachOther | 当前节点操作者不可互相查看意见 |
| feedback / nullNotFeedback | 意见反馈/意见为空时不反馈 |

四个 Select 模式字段均为 `0全部/1选择/2排除`（以当前 schema 为准）；列表传完整名称或字符串 ID 数组。完整候选通过 `--options <对应列表字段>` 获取，会保留节点类型等过滤条件。部分名称命中失败会整体拒绝，不静默丢失。

`signOperateTypeSelect=1` 且 `signOperateTypeList=[]` 表示不指定必须签批的操作。全部节点模式须同时显式清空已有节点列表。全部操作意见必填与隐藏输入框冲突时，须显式设置 `hideInput:false`。不修改其他节点，不执行同步。

## 自然语言测试话术

- “使用 107 测试环境，查询流程【ID】已有拟签字段，把【控件ID】改为显示全部意见，其他保持原样，保存后回读。”
- “流程【ID】开启拟签自定义展现，填写方式改为弹窗、意见正序排列；不要改字体、模板和按钮。”
- “流程【ID】节点【ID】，待办允许转发但接收人不能提交意见；已办允许转发且可提交意见，结束流程设置保持不变。”
- “流程【ID】节点【ID】，签字意见只展示批准和拟签意见、隐藏空意见，批准时必须使用签批或签名，其余配置不变。”

执行前先查询真实 workflowId/nodeId/widgetId、环境枚举和操作候选；自然语言由 AI 映射为上面的 CLI 参数。验证完成应区分配置回读通过和前台运行行为通过。
