# 表单数据 CLI 操作

通过 CLI 读写表单数据（不需要写页面代码）。JS 编码 API（getSimpleData/saveFormData 等）见 `coding/guide-form-crud.md`。

## 读数据

```bash
e10-cli form data list <objId>
```

返回该表单所有数据记录。

## 写数据（新增）

```bash
e10-cli form data add <objId> @data.json
```

data.json 格式（`@` 开头为文件路径）：

```json
{
  "1290462231772995585": "张三",
  "1290462231772995586": "1290462231772995612",
  "1290462231772995589": "2765550234448235905"
}
```

| 字段类型 | 值格式 |
|---------|--------|
| Text / TextArea / Number / Money | 直接值 |
| Date | `"2026-01-01"` |
| Select / RadioBox | 选项 valueKey（长 ID） |
| CheckBox | `"id1,id2"` 逗号分隔 |
| Employee / Department | 用户/部门 ID |
| FileComponent | `"fileid1,fileid2"` |

> **除非用户明确要求，否则不要往表单写入任何数据。** 表单创建完成后只需确认字段正确即可，不要自动插入测试数据。

## 删数据

```bash
e10-cli form data delete <objId> <dataId>
```
