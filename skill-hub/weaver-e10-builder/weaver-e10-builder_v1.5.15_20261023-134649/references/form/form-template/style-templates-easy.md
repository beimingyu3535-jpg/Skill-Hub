# 表格式布局：简易模板

简易模板用一组参数生成表格式布局。

## 模板类型与新建

- **预设模板：**平台提供 6 种系统模板，可预览，不可编辑。
- **自定义模板：**管理员可新建并设置主表、明细表的尺寸、边框色和背景色。新建时输入模板名称，再分别配置主表和明细表。

后台设计器提供**实时预览**，修改配置后可查看生成的实际效果。当前 CLI 支持列表、详情、新增、编辑和删除；CLI 的 `preview` 调用不落库接口并返回布局摘要，尚未提供与后台设计器相同的可视化实时预览。导入尚未实现。

## 可设置内容

| 区域 | 参数 | 含义 |
| --- | --- | --- |
| 基本 | `templateName`、`showOrder` | 名称、显示顺序 |
| 主表 | `rowHeight` | 主表区域行高，至少 30px |
| 主表标题 | `titleWidthType` + `titleWidthPx` 或 `titleWidth` | 固定像素宽度或百分比宽度 |
| 主表字段 | `fieldWidthType` + `fieldWidthPx` 或 `fieldWidth` | 固定像素宽度或百分比宽度 |
| 主表标题与字段 | `titleBorderColor`、`fieldBorderColor`、`titleBgColor`、`fieldBgColor` | 各自的边框色和背景色 |
| 明细 | `dRowHeight`、`dColWidthType` + `dColWidthPx` 或 `dColWidth` | 明细表区域行高（至少 30px）和列宽 |
| 明细标题与字段 | `dTitleBorderColor`、`dFieldBorderColor`、`dTitleBgColor`、`dFieldBgColor` | 各自的边框色和背景色 |

宽度模式 `0` 使用 `*Px` 固定像素值；模式 `1` 使用无 `Px` 后缀的百分比值（0–100 的整数）。颜色为 `#RRGGBB`，名称最长 150 字符。简易模板不支持逐单元格字体、边框线型、合并单元格或字段占位符设计。

## 命令

```bash
e10-cli form-engine layout-template easy list
e10-cli form-engine layout-template easy get <模板ID>
e10-cli form-engine layout-template easy preview --id <模板ID>
e10-cli form-engine layout-template easy preview --config @easy-template.json
e10-cli form-engine layout-template easy create --config @easy-template.json
e10-cli form-engine layout-template easy update <模板ID> --config @changes.json
e10-cli form-engine layout-template easy delete <模板ID> [更多模板ID...]
```

`create` 至少提供名称、主表与明细行高、三组宽度模式及对应宽度。`update` 只传修改项，CLI 读取现有配置后合并、保存并回读。`--config` 也接受内联 JSON。`preview` 不保存模板。

`delete` 可批量删除自定义简易模板。CLI 会先核对全部 ID，拒绝删除系统预设模板；检查可删除性后执行删除，并回读列表确认目标已消失。

```json
{
  "templateName": "浅蓝简易模板",
  "rowHeight": 40,
  "titleWidthType": 0, "titleWidthPx": 150,
  "fieldWidthType": 0, "fieldWidthPx": 300,
  "dRowHeight": 40,
  "dColWidthType": 0, "dColWidthPx": 180,
  "titleBorderColor": "#5D9CEC", "fieldBorderColor": "#5D9CEC",
  "titleBgColor": "#E3F0FF", "fieldBgColor": "#FFFFFF",
  "dTitleBorderColor": "#5D9CEC", "dFieldBorderColor": "#E5E5E5",
  "dTitleBgColor": "#E3F0FF", "dFieldBgColor": "#FFFFFF"
}
```
