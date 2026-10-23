# 表单数据 CLI 操作

通过 CLI 读写表单数据（不需要写页面代码）。JS 编码 API（getSimpleData/saveFormData 等）见 `coding/guide-form-crud.md`。

## 读数据

```bash
e10-cli form data list <objId> [--page <n>] [--size <n>]
```

返回该表单数据记录。`--page` 页码（缺省 1）、`--size` 每页条数（缺省 1000；不传 pageInfo 平台默认卡 10 条）。

## 写数据（新增）

```bash
e10-cli form data add <objId> <appId> @data.json
# 或直接传 JSON：e10-cli form data add <objId> <appId> '{"单行文本":"x","金额":1000,"类型":"A"}'
```

data.json 格式（`@` 开头为文件路径）。key 可用 **fieldId（长 ID）或字段名（中文）**，CLI 自动按字段类型构造（走 `form/core/saveFormData`，dataDetails 按类型分）：

```json
{
  "单行文本": "张三",
  "金额": 1000,
  "签订日期": "2026-01-01",
  "类型": "A",
  "备注": "一段文字"
}
```

| 字段类型 | 值格式 |
|---------|--------|
| Text / Number / Money | 直接值 |
| TextArea | 直接值（文本） |
| Date / DateTime | `"2026-01-01"` / `"2026-01-01 10:30"` |
| Select / RadioBox | **选项名（自动解析为 valueKey）** 或 valueKey（长 ID） |
| CheckBox / SelectMultiple | 选项名数组 `["A","B"]` 或 valueKey 数组 |
| Employee / Department | 用户/部门 ID（暂未支持按名解析） |
| FileComponent | `"fileid1,fileid2"` |

> **除非用户明确要求，否则不要往表单写入任何数据。** 表单创建完成后只需确认字段正确即可，不要自动插入测试数据。

## 删数据

```bash
e10-cli form data delete <objId> <dataId>
```
