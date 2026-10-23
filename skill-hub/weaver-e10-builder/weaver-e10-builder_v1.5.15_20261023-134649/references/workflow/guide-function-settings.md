# 工作流功能设置

统一入口 `e10-cli workflow function`。七项为流程级单份配置，第一次保存读取程序默认值；已有配置先读再局部合并，保存后回读核对。无需另建配置 ID。没有 `--data` 时仅查询。

| 命令 | 功能 |
|---|---|
| batch-set | 批量提交/转办/征询/退回、各自节点范围、提交类型及退回发起节点规则 |
| auto-approve | 自动处理、相邻/后续规则及范围、前置/后置、必审节点、组织范围、预测节点、意见内容、主次账号；--cross 为跨流程规则 |
| other-set | 消息按钮、节点范围、自动保存及范围、身份切换、日志、默认最大显示、字段变更标记、门户等当前环境开放项 |
| water-mark-set | 开关、系统/自定义、文本/图片、尺寸、透明度、角度、内容模板 |
| import-approval-set | 导入开关、数据来源；旧模式另含无需导入字段、只读字段、钻取计算、默认值 |
| resource-share-set | 表单事项字段、意见事项范围、客户权限、无权限资源过滤、关联搭建表单基本信息共享范围 |
| doc-share-set | 文档/附件来源、流程参与人及表单字段共享、离开节点触发、禁止编辑、允许下载 |

## 查询与修改

```sh
e10-cli workflow function batch-set <wf> --schema
e10-cli workflow function batch-set <wf> --candidates selectNodes
e10-cli workflow function batch-set <wf> --data '{"enabledBatch":true,"selectOptions":"1","selectNodes":["审批节点ID"]}'
e10-cli workflow function auto-approve <wf> --data '{"autoHandle":true,"handWay":"0"}'
e10-cli workflow function auto-approve <wf> --cross --schema
e10-cli workflow function other-set <wf> --data '{"enableAutoSave":true}'
e10-cli workflow function doc-share-set <wf> --data @patch.json
e10-cli workflow function water-mark-set <wf> --candidates variables
```

参数统一：`--schema`（当前配置及实际字段定义）、`--data JSON/@file`（仅写指定项）、`--candidates 字段名`、`--out 文件`。开关用 true/false；单选用选项字符串 ID 或唯一名称；多选用数组。浏览字段用字符串 ID/唯一名称数组，清空用 []。组织范围用 `[{"_entityType":"user","id":"人员ID"}]`，所有人用 `[{"_entityType":"all","id":"0"}]`。列表修改替换指定字段的整个列表，其他字段保持不变。

## 完整字段

- batch-set：enabledBatch、allowTurnTodo、allowConsult、allowReject；selectOptions/selectNodes、turnTodoOption/turnTodoNodeBrowser、consultOption/consultNodeBrowser、rejectOption/rejectNodeBrowser；submitTypeOption/submitType；rejectToStart。
- auto-approve：autoHandle、handWay、adjacentCheck、adjacentOptions/adjacentNodes、followUpType、followUpCommit、followUpCheck、followUpOptions/followUpNodes、selectUsers、backHandle、mustHandNodeBrowser、allowHandleUserBrowser、backHandleForecastNodeBrowser、compensateTip、signMark、signContent、mainSecondEnable。
- auto-approve --cross：mainOperated、mainCommit、mainRangeType/mainRangeKey、associatedOperated、associatedCommit、associatedFieldKey。
- other-set：followNodeviewRight、allowViewFormLog、messageOperation、nodeRangeOptions/nodeRangeNodes、autoMaxDisplay、enableAutoSave、autoSaveRangeType/autoSaveRangeMultiBrowser、markChangedFieldScene、markFieldRange/markFieldKeyBrowserValue、allowUseInDoor、recordFlowLog、allowUseAndDiverted、formModifyLog。环境未开放字段拒绝修改。
- water-mark-set：enabled、waterType；waterMarkData 中可局部修改 wmClassify(text/picture)、wmWidth、wmHeight、wmNoTransparent、wmRotate、wmText、wmOriginText、wmImg。数字以字符串输入；wmImg 使用已上传图片的对象数组。本命令不上传本地图片文件。变量 ID 先查询 variables，不猜测。
- import-approval-set：canImportApproval、importSource；旧模式另有 importReadOnlyField、fieldBrowserValue、relate、defaultValue。
- resource-share-set：fieldSelect/fieldSelectBrowser、relateRangeSelect/relateRangeBrowser、customerShareType、filterNoPermission、ebShareBasicRangeBrowser。
- doc-share-set：docShareOption、flowShareOperator、formFieldBrowser、fieldShareDocChange、fieldShareLeaveTrigger、fieldShareLeaveNodesBrowser、forbidEditOption、allowDownload。

## 约束

具体枚举、节点和字段以服务端 schema/candidates 为准，不把普通字段权限与文档/附件共享权限混用。

节点可修改内容时关闭自动处理，必须同时启用存在必填项时关闭的规则；冲突输入拒绝，不静默改动用户未指定设置。预测节点必须保留发起节点。`followUpType` 的不启用不能与其他项并选。

新版导入设置的 fieldValueSet 是表单复制规则的只读入口（前端 isSetting=false），流程设置不保存这些规则；--schema 中 customParameters.formId 指明关联表单。新旧模式以实际返回字段判定，不能仅凭 enableFormCopy 的数值推断。

水印后端忽略空模板，CLI 因此拒绝空串清空请求；可关闭水印或替换有效内容。保存首次默认配置可能产生实体记录；恢复设置值不代表删除初始化记录。

服务端返回成功但回读不一致时，命令失败并列出差异，不能直接当成配置成功，也不会自动重复写入。

移动端布局独立设置（allowMobileLayout）和启用正文（enableOdocText）不提供写入支持；查询可见原值，修改其他配置时保留原值。

导入模式由后端 enableFormCopy(entity) 判定：无配置走新模式；已有配置但 canImportApproval=0 时按新模式；否则 enableFormCopy=1 为新模式、0 为旧模式。CLI 根据实际返回的 fieldValueSet/字段定义开放能力，不单凭版本号或返回数字推断。
