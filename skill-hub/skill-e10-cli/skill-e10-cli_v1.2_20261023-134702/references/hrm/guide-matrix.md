# HRM 条件矩阵指南

> 矩阵 = 「条件维度（行）→ 值维度（列）」的映射查询表。例如：部门 + 费用类型 → 审批人。用于流程中的矩阵对应操作者类型。

## 命令参考

### 矩阵管理

| 命令 | 说明 |
|------|------|
| `e10-cli matrix create <name>` | 新建矩阵。`--type 0=分部/1=部门/2=自定义` `--desc` `--org-id` |
| `e10-cli matrix update <id>` | 更新矩阵。`--name` `--desc` `--type` |
| `e10-cli matrix list` | 查询矩阵列表。`--name` `--enable-status` `--org-id` |
| `e10-cli matrix config <id>` | 查看矩阵配置（条件字段 + 值字段） |
| `e10-cli matrix config-edit <id>` | 编辑配置。`--condition` `--value` 或 `--config` 一次性提交 |
| `e10-cli matrix enable <id>` | 启用矩阵 |
| `e10-cli matrix disable <id>` | 停用矩阵 |
| `e10-cli matrix delete <ids...>` | 删除矩阵 |

### 矩阵数据维护

| 命令 | 说明 |
|------|------|
| `e10-cli matrix data list <matrixId>` | 分页查询矩阵数据行。`--condition` `--value` 过滤 |
| `e10-cli matrix data save <matrixId> --rows @file` | 保存数据行（新增/修改）。简写: `[{"字段configId":["实体ID"]}]` |
| `e10-cli matrix data delete <matrixId> <ids...>` | 删除数据行 |
| `e10-cli matrix data template <matrixId>` | 下载导入模板（Excel） |
| `e10-cli matrix data import <matrixId> <file>` | 从 Excel 导入。`--mode add/cover` |

---

## 典型工作流

```bash
# 1. 创建矩阵
e10-cli matrix create "审批人映射表" --type 2 --desc "部门→审批人"

# 2. 查 ID
e10-cli matrix list --name "审批人"

# 3. 配字段（条件=部门，值=审批人）—— 注意：首次配置可能需在 UI 操作
e10-cli matrix config-edit <matrixId> \
  --condition '[{"type":"department","name":"所属部门"}]' \
  --value '[{"type":"resource","name":"审批人","singleType":1}]'

# 4. 启用
e10-cli matrix enable <matrixId>

# 5. 填数据
echo '[{"<条件configId>":["<部门ID>"],"<值configId>":["<人员ID>"]}]' > rows.json
e10-cli matrix data save <matrixId> --rows @rows.json

# 6. 查数据
e10-cli matrix data list <matrixId>

# 7. 在流程中使用矩阵
e10-cli workflow set-operator <wf> <nodeId> --type matrix \
  --matrix-id <matrixId> --value-config-id <值configId> \
  --matrix-rule "<条件configId>:1:1:1"
```

---

## 字段类型枚举

| 中文 | API 值 |
|------|--------|
| 人员 | `resource` |
| 部门 | `department` |
| 分部 | `subcompany` |
| 岗位 | `position` |
| 客户 | `customer` |
| 项目 | `project` |
| 数据源 | `datasource` |

## config-edit 参数

```json
{
  "id": "<矩阵ID>",
  "conditionConfigList": [
    { "type": "department", "name": "显示名", "sort": 1 }
  ],
  "valueConfigList": [
    { "type": "resource", "name": "显示名", "singleType": 1, "sort": 1 }
  ],
  "conditionDelList": [],
  "valueDelList": []
}
```

> `singleType`: 0=多选, 1=单选。条件字段不传，值字段必传。

## data save 简写格式

```json
[
  {"<条件configId>": ["<实体ID>"], "<值configId>": ["<实体ID>"]}
]
```

CLI 自动查 config 判断 `conditionAble` 标记并展开为完整格式。

