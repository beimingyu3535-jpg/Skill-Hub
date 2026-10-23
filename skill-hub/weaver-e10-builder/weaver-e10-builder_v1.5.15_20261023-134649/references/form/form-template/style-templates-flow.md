# 流式布局模板

流式布局 `FLOW` 按 PC 与移动终端分别选择模板。它使用独立的模板列表和布局模型；表格式模板的 ID、网格坐标及样式数据不能直接用于流式模板。

## 当前可用能力

`form layout init --style-template <名称|ID>` 会读取目标表单的布局类型，按流式模板列表解析和校验名称或 ID，再初始化表单布局。不同布局类型可能有同名模板，以目标表单的 `FLOW` 类型查询结果为准。

```bash
e10-cli form layout init <objId> <appId> --style-template <流式模板名称或ID>
```

### 从实际布局另存为模板

已有 **PC 流式布局**可将当前布局样式另存为新模板。指定实际布局 ID，CLI 读取该布局的 `formStyle`，提取表单标题、通用样式及明细样式，保存后按名称回读新模板。它不会把实际表单的业务字段或 `pageLayouts` 复制进模板。

```bash
# 流程表单：传 formId 和布局 ID
e10-cli form layout save-as-template <formId> --module workflow --view-id <布局ID> --name <新模板名>

# eBuilder 表单：传 objId 和布局 ID
e10-cli form layout save-as-template <objId> --view-id <布局ID> --name <新模板名>
```

默认新模板为禁用状态；需要创建后即可用于初始化时加 `--enabled`。已有封面文件可通过 `--cover-file-id <文件ID>` 复用，显示顺序可用 `--show-order <整数>` 调整。命令会拒绝表格式和移动端布局、重复模板名及不匹配的布局 ID。布局入口和读取方式见[表单布局规划](../guide-form-layout-planning.md)。

流式模板的独立新建、编辑、导入及移动端组件样式规则仍未实现为 CLI 命令。不能套用表格式高级模板的 `workbook`、`marks` 或图片网格迁移规则。
