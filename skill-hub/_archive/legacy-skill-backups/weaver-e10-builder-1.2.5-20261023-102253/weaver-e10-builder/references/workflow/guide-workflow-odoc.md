# 公文流程指南

## 定位

公文流程是原生工作流程的特殊类型，由 `bridgeService=odoc` 标识。固定/自由通过 `--is-free 0|1` 设置。需求明确出现公文流程、公文审批、收文、发文、公文设置或正文设置时读取本指南；基础节点、出口、操作者、条件和布局规则同时读取 [流程表单指南](guide-workflow.md)。

## 创建

### 随流程自建原生流程表单

```bash
e10-cli workflow create-workflow "公文审批流程" --odoc --layout FLOW
```

自建模式沿用原生工作流程路径，提交 `relateForm=0`、`formId=0` 和 `bridgeService=odoc`。表格式布局使用 `--layout EXCEL`。

### 绑定已有原生流程表单

```bash
e10-cli workflow create-workflow "公文审批流程" --odoc --form-id <formId>
```

绑定模式提交 `relateForm=1`、`formId=<已有原生流程表单ID>` 和 `bridgeService=odoc`。后续字段与布局继续使用 `wf-form` 和原生流程表单 `formId`。

团队流程默认使用当前创建者机构；多机构场景再显式传 `--sub-company <机构ID>`。其他通用参数如 `--workflow-type`、`--desc`、`--is-free` 与普通原生工作流程一致。

## 创建结果与后续配置

命令返回 `workflowId` 和 `formId`，JSON 结果以 `flowKind:"odoc"`、`bridgeService:"odoc"` 标识公文流程。创建后的列表回读同样带 `bridgeService=odoc`，并核对返回记录的 `bridgeService`。

取得 `workflowId` 后，节点、出口、操作者、出口条件、会签、退回、超时、消息、编号和动作流继续使用通用 `workflow` 命令。

## 公文专属配置

### 查询

```bash
e10-cli workflow odoc list [--name <关键词>] [--sub-company <机构ID>]
e10-cli workflow odoc read <workflowId>
```

`list` 使用 `bridgeService=odoc` 查询公文流程；`read` 返回流程名称、绑定表单 `formId` 和公文设置摘要。

### 读取与保存公文设置

```bash
e10-cli workflow odoc setting get <workflowId>
e10-cli workflow odoc setting set <workflowId> --config @odoc-setting.json
```

`setting set` 读取当前配置、合并指定内容、保存并回读。配置 JSON 可直接使用平台字段，也可按 `basic`、`text`、`files`、`nodes`、`signature`、`archive`、`ai` 分组；`number` 映射为 `odocNumber`，`attachmentArea` 映射为 `odocAttachArea`。

常用配置也可直接使用参数：

```bash
e10-cli workflow odoc setting set <workflowId> \
  --official-type 1 \
  --request-title-field "公文标题" \
  --upload-word 1 --upload-pdf 1 --upload-ofd 1 \
  --text-in-form 1 --column-position 1 \
  --attach-area 1 --archive-node "归档" \
  --open-text-select 2 \
  --edit-text-node "发起节点" \
  --ai-odoc 1 --ai-abstract 1 --ai-format 1
```

字段参数支持字段名称或字段 ID，节点参数支持节点名称或节点 ID（名称在流程内重复时报错并给出候选 ID，不擅自挑一个）。平台开关值使用 `0` 和 `1`。

- `--open-text-select` 默认打开正文节点的范围编码；`--open-text-node` 配合它指定具体节点（可多个，逗号或空格分隔）。
- `--edit-text-node` 可编辑正文的节点，可多个。
- `--ai-odoc` 公文助手总开关；`--ai-abstract` 智能摘要、`--ai-format` 智能排版 是它下面的两项，单独打开它们不会自动把总开关带上，需要一并给。

### 配置结构

- 基础正文：`officialType`、`requestTitleField`、`flowDocField`、`documentTitleField`、`defaultCat`、`flowDocCatField`、`docPropSettings`。
- 正文展示：`openTextDefaultNode`、`editTextNode`、`previewDefault`、`isTextInForm`、`columnPosition`、`textColumnSize`。
- 文件与签章：`uploadWORD`、`uploadPDF`、`uploadOFD`、`signGroupMould`、`signNodeList`、`openSignatureSeal`。
- 公文编号：`odocNumber`。
- 附件区域：`odocAttachArea`，包含启用状态、打开节点、展示位置及正文/附件比例。
- 归档：`archivesForm`、`archivesNodeOpen`、`archivesNode`、`archivesAuth` 和字段映射设置。
- AI 与格式：`openAiAbstract`、`openAiFormat`、`defaultFormatTemplate`、`showAiAssistant`、`showOfficialDoc`。

保存请求携带完整公文设置，其中字段选择值为字段 ID、节点选择值为节点 ID，`signNodeList` 保存节点及其启用、必填状态。

**回读的值不能直接写回去。** 平台读回来的形状和保存要的形状不一样，混用会直接被服务端拒掉（`400 Bad Request`）：

| | 读取 | 保存 |
|---|---|---|
| 开关 | 布尔 `true` / `false` | 字符串 `"1"` / `"0"` |
| 基本类型清单 | 数组 `["id1"]` / `[]` | 逗号串 `"id1"` / 空串 `""` |
| 签章节点表 | 对象数组 | 对象数组，但**每个对象里的布尔同样要转成串** |
| 节点清单字段（`editTextNode` 等） | 对象数组 `[{name,id}]` | 逗号串 `"id1,id2"` |

分组的落法也分三种：`odocNumber` / `odocAttachArea` **整组保持嵌套**，`signNode` 组以 `signNodeList` 发出，其余分组的键**平铺**到顶层。这些转换由 CLI 自动完成，`--config` 里也按同样规则给值即可。

`setting set` 保存后会**回读比对**，对不上会点名是哪个键没落库 —— 平台对报文形状不合法一律报 400，但对语义问题可能静默收下，读回来才算数。
