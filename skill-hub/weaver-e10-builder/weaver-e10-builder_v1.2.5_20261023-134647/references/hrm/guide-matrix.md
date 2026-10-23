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
| `e10-cli matrix delete <ids...>` | 删除矩阵。**矩阵里有数据行时平台会拒绝删除**（报"存在不能删除的矩阵"且不指出是哪个）——先 `matrix data delete <id> <rowIds...>` 清空数据行再删；批量删除时只要有**一条**不可删，整批都失败 |

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
# 1. 创建矩阵（新建即启用；分权租户的所属机构自动取当前机构）
e10-cli matrix create "审批人映射表" --type 2 --desc "部门→审批人"

# 2. 查 ID
e10-cli matrix list --name "审批人"

# 3. 配字段（条件=部门，值=审批人）—— 直接可用，不需要先开设计器
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

## 系统矩阵 vs 自定义矩阵

`matrix list --json` 每条记录带三个标记位，决定这个矩阵能改什么：

| 字段 | 取值 | 含义 |
|---|---|---|
| `type` | `0` / `1` / `2` | `0`=分部矩阵、`1`=部门矩阵、`2`=自定义矩阵 |
| `sysType` | `1` / `0` | `1`=系统矩阵（平台内置的组织维度矩阵），`0`=非系统 |
| `syncType` | `1` / `0` | `1`=数据行随系统组织同步，`0`=手工维护 |

- **系统矩阵**（`sysType=1`，即 type 0/1 的分部/部门矩阵）：条件列由平台内置的组织维度决定（分部 / 部门），建好后不自行增删条件列；`syncType=1` 时数据行随系统组织同步，不需要 `matrix data save` 手工填（典型：`部门矩阵` —— 条件列=部门、值列为空、描述"同步系统部门信息"）。
- **自定义矩阵**（`sysType=0`，`type=2`）：条件列与值列都自由配置，数据行手工维护，可带 `belongOrgId` 归属机构。

> 两者**在流程里的用法完全一样**（都是 `workflow set-operator --type matrix`），差别只在"条件列从哪来 / 数据谁来填"。

**所属机构与分权**：矩阵强制校验"所属机构"，而落到哪个字段由**分权状态**决定——分权开启时平台读 `belong_org_id`（归属机构），关闭时读 `targetId`。CLI 建矩阵前会自动查 `check-detach` 判断并选对字段，分权租户还会直接用返回的当前机构兜底，所以 `matrix create` 通常不用手写机构；只有"非分权租户"或"归属机构与目标机构必须不同"时才需要 `--org-id` / `--target-id`。

**列表的状态过滤**：`matrix list` 走管理端点 `matrix2/list`，能看到**停用的矩阵**并显示真实状态；`--name`（模糊）、`--enable-status`、`--org-id` 都是服务端过滤。

## 完整配置：条件列 → 人员列 → 数据映射 → 运行时读回

```bash
# ① 建矩阵（自定义矩阵。系统矩阵是平台内置的，用 matrix list 找现成的）
#    新建即为「启用」状态，不需要再 enable；要停用才跑 matrix disable
#    所属机构：分权租户自动取当前机构，非分权租户用 --org-id 显式指定（不加会有"所属机构不能为空"）
e10-cli matrix create "部门审批人" --type 2 --desc "部门→审批人"

# ② 配列：条件列 + 值列。值列 type=resource 就是"人员列"；singleType 0=多选 1=单选
e10-cli matrix config-edit <matrixId> \
  --condition '[{"type":"department","name":"所属部门"}]' \
  --value '[{"type":"resource","name":"审批人","singleType":1}]'

# ③ 取各列 configId（数据映射的键就是它），再填数据行
e10-cli matrix config <matrixId>            # → conditionConfigList[].id / valueConfigList[].id
e10-cli matrix data save <matrixId> --rows @rows.json
e10-cli matrix data list <matrixId>         # 回读数据行

# ④ 启用并挂到流程节点
e10-cli matrix enable <matrixId>
e10-cli workflow set-operator <wf> <nodeId> --type matrix \
  --matrix-id <matrixId> --value-config-id <值列configId> \
  --matrix-rule "<条件列configId>:1:1:1"

# ⑤ 运行时读回：确认条件列/值列是否就是流程实际在读的那一组
e10-cli matrix config <matrixId>
```

> **矩阵类型不用手填**：`--type matrix` 的 `sourceType` / 条件列中文名由 CLI 自动读 `GET /api/bs/hrm/matrix2/config?id=<matrixId>` 解析——`conditionConfigList[].type` 是 `department` 即部门矩阵、`subcompany` 即分部矩阵。条件列不在目标矩阵里时会直接报错并列出可选列，不会静默挂错。
>
> 排查"取不到人"时按这个顺序看：`matrix config`（列对不对）→ `matrix data list`（行有没有）→ 流程节点的矩阵规则是否引用了正确的 `条件configId`。

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

