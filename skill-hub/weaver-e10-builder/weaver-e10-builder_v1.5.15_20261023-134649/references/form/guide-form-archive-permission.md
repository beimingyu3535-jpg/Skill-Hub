# 流程归档权限

「流程归档权限」管的是**某个流程归档之后**，它的数据对谁可见、可改、可删。它和表单的共享权限是两套：
共享权限按表单配一次，归档权限**按流程各配一套**（同一张表单的不同流程可以不一样），并且多一档「归档附件」权限。

## 命令

```bash
# 查看某个流程的归档权限
e10-cli form permission archive list <objId> <appId> --workflow <workflowId>

# 通用对象：给某个部门开「归档查看」
e10-cli form permission archive add <objId> <appId> --workflow <workflowId> \
  --target general --org-type department --org-id <deptId> --rights view --file-rights view download

# 创建人相关：创建人本人及本部门可查看/编辑
e10-cli form permission archive add <objId> <appId> --workflow <workflowId> \
  --target creator --creator-related 0 --rights view edit

# 字段相关：以表单里的「负责人」字段取值决定权限
e10-cli form permission archive add <objId> <appId> --workflow <workflowId> \
  --target field --field 负责人 --rights view edit delete

# 矩阵相关（真矩阵）
e10-cli form permission archive add <objId> <appId> --workflow <workflowId> \
  --target matrix --matrix 门店经理矩阵 --rights view

# 矩阵相关（e-Builder 表单当矩阵用）
e10-cli form permission archive add <objId> <appId> --workflow <workflowId> \
  --target matrix --eb-form <表单名或id> --matrix-value 创建者 --rights view

# 矩阵相关 + 条件（真矩阵才有条件列）：所属门店 等于 本表单的「创建人部门」
e10-cli form permission archive add <objId> <appId> --workflow <workflowId> \
  --target matrix --matrix 门店经理矩阵 \
  --matrix-condition '{"column":"所属门店","func":"等于","field":"创建人部门"}' \
  --rights view

# 删除（按 list 里的权限 ID）
e10-cli form permission archive remove <objId> <appId> --right-id <id[,id...]>

# 归档卡片开关
e10-cli form permission archive card <workflowId> <appId>
e10-cli form permission archive card <workflowId> <appId> --set 1
```

## 四类授权对象

同一个端点上靠 `codeType` + `orgType` 区分四类，命令层用 `--target` 选择：

| `--target` | 类别 | `codeType` | `orgType` | 主体怎么给 |
|---|---|---|---|---|
| `general` | 通用对象 | `obj_data_admin` | `employee` / `department` / `company` / `role` / `group` / `all` … | `--org-type` + `--org-id`（`all` 自动 0） |
| `creator` | 创建人相关 | `obj_data_creator` | `creatorRelated` | `--creator-related` 0~7 |
| `field` | 字段相关 | `obj_data` | `field_<字段类型>` | `--field <字段 id 或名称>` |
| `matrix` | 矩阵相关 | `matrix` / `ebuilder_form` | 同 `codeType` | `--matrix`（真矩阵）或 `--eb-form` |

`--target` 也接受中文名（`通用对象` / `创建人相关` / `字段相关` / `矩阵相关`）。

### 创建人相关的 0~7

`0` 本人、本部门、本分部；`1` 直接上级、本部门及所有下级部门、本分部及所有下级分部；`2` 本分部、本部门及所有上级部门、本分部及所有上级分部；
`3` 本部门、所有下级部门、所有下级分部；`4` 所有上级、所有上级部门、所有上级分部；`5` 本岗位；`6` 直接下属；`7` 上级部门。

### 字段相关的字段类型

`--field` 既可给字段 id，也可给字段名（重名会报错，改用 id）。字段属于明细表时补 `--sub-form-id`。

`orgType` 由字段的组件类型推出，目前覆盖：

| 组件类型 | `orgType` | 回显名 |
|---|---|---|
| `Employee` | `field_employee` | 人员字段 |
| `Department` | `field_department` | 部门字段 |
| `SubCompany` | `field_company` | 分部字段 |
| `Post` | `field_post` | 岗位字段 |
| `EBuilder` | `field_ebuilder` | 关联ebuilder字段 |

其余字段类型（人员范围选择、人力资源条件、人员组织多选等）不在自动推断表里 —— 组件类型名与 `field_*` 后缀不是一一对应，
猜错会**静默授错对象**，所以命令会报错而不是替你选。这类请用 `--org-type field_xxx` 显式指定：

`field_employee_condition`（人员范围选择字段）、`field_employee_share_condition`（人力资源条件字段）、`field_employee_organization`（人员组织多选）。

### 矩阵相关的「取值字段」

取值字段决定**用矩阵里的哪一列**去匹配当前用户，必需，且取值来源分两种：

- **真矩阵**（`--matrix`）：值字段自动取该矩阵的值字段配置；也可用 `--matrix-value 名称` 指定其中几个。
- **e-Builder 表单**（`--eb-form`）：候选来自**该表单自己的字段**（与设计器字段选择器一致）：
  - **创建者**（系统值，`valueType=system_creator`）
  - **人员 / 部门 / 人员范围 / 人员条件 / 人员组织**类型的字段；其中人员字段（Employee）`valueType=resource`
  - 可直接按字段名指定，如 `--matrix-value 负责人`；其余仍可用 `<id>:<名称>:<valueType>` 明写，
    或用 `--matrix-value-raw '<JSON 数组>'` 整体透传

### 矩阵相关的「条件」

矩阵相关比另外三类多一层**条件**：拿矩阵自己的**条件列**去比「固定值」或「本表单字段」，只有命中的行才生效。
落库是行报文里的 `matrixConditionData`（一棵条件树的 JSON 串）。
真矩阵的条件列来自矩阵配置；**e-Builder 表单的条件列就是它自己的主表字段**（自动从字段表取）。

```bash
# 一条：所属门店 等于 固定值
--matrix-condition '{"column":"所属门店","func":"等于","value":"123测试的"}'

# 一条：所属门店 等于 本表单字段（field 走字段表按 id/名解析）
--matrix-condition '{"column":"所属门店","func":"eq","field":"创建人部门"}'

# 两条 + 任一
--matrix-condition '{"column":"所属门店","func":"等于","value":"上海门店"}' \
--matrix-condition '{"column":"所属门店","func":"不属于","value":"临时门店"}' \
--matrix-condition-relation or

# e-Builder 表单当矩阵：负责人 不为空
e10-cli form permission archive add <objId> <appId> --workflow <workflowId> \
  --target matrix --eb-form 项目任务 \
  --matrix-value 负责人 \
  --matrix-condition '{"column":"负责人","func":"不为空"}' \
  --rights view

# e-Builder 表单当矩阵：所属项目 = 当前记录（「当前项目信息」）
e10-cli form permission archive add <objId> <appId> --workflow <workflowId> \
  --target matrix --eb-form 项目任务 \
  --matrix-value 负责人 \
  --matrix-condition '{"column":"所属项目","func":"等于","field":"数据ID"}' \
  --rights view
```

> 「当前记录」用本表单的系统字段 **数据ID**（`field:"数据ID"`，即 `id=5`）表示，不要写固定值。
> 关联列（Ebuilder）引用数据ID 是设计器实证的跨类型例外（关联列按字符串比）。

| 参数 | 说明 |
|---|---|
| `--matrix-condition <json>` | 一条条件，**可重复**；也可 `@文件` 给一个数组。对象三件套：`column`（条件列的 id 或列名）+ `func` + 右值 |
| `--matrix-condition-relation` | 条件之间的关系：`and`=所有（默认）/ `or`=任一 |
| `--matrix-condition-comp-type` | 条件列的组件键。**仅真矩阵需要**（列类型的组件键目前只实证了「部门」→`Department`，其余类型会报错要求显式给）；e-Builder 表单由字段类型自动取 |
| `--matrix-condition-raw <json>` | 整棵树透传（不做校验），形状以设计器请求为准 |

**右值三选一**：

- `"value": "字面值"` —— 固定值。**6 个算子都能配**。
- `"field": "字段名或 id"` —— 引用**本表单字段**，按字段表解析。
- `"fieldRef": {"id":"…","compType":"…","text":"…"}` —— 直接给字段描述符。**「创建人部门」这类运行时变量必须用这个** ——
  它出现在设计器的字段选择器里，但 `ds/fields` 与 `getFormFieldPage` 都查不到；描述符从设计器报文里抄。

> ⚠ **引用本表字段（`field` / `fieldRef`）平台卡两条**，CLI 会当场拦下而不是发出去：
> ① **算子只能是「等于」**；② **字段类型必须与条件列一致** —— 部门列只能引用部门类型的字段，
> 文本字段在设计器里根本选不到。所以「所属门店（部门）等于 [创建人部门]」成立，
> 「所属门店（部门）等于 [名称（文本）]」和「所属门店 不等于 [创建人部门]」都会报错。
> 例外：关联列（Ebuilder）可以引用本表单的 **数据ID**（当前记录），用于「所属项目 = 当前项目信息」这类限定。

算子只有界面下拉那 6 个：**等于 / 不等于 / 属于 / 不属于 / 为空 / 不为空**（`eq` / `neq` / `aggregate` / `unaggregate` / `empty` / `nempty`）。
其中**只有「等于」是对着真机报文核实的**，其余 5 个是按同一族条件树的码表推的 —— 内容平台会原样存下、回读也一模一样，
**只会在设计器里露馅**（渲染成 `undefined`）。用它配完请在设计器里过一眼。

两条限制：

- **e-Builder 表单也能配条件** —— 条件列取自该表单自己的主表字段，不需要 `--matrix-condition-comp-type`。
- **右值不能引用明细表字段**（只支持主表字段）。

台账那边的矩阵权限（`form list-permission --add-matrix`）**同一套参数与语义**。

## 权限码

归档权限 `--rights`（可组合，逗号或空格分隔，也可用编号）：

| 编号 | 别名 | 含义 |
|---|---|---|
| 5 | `view` / `read` | 归档查看（**系统必选**） |
| 6 | `edit` / `update` | 归档编辑 |
| 7 | `delete` | 归档删除 |

> **归档查看是系统默认勾选、界面上不能取消的**。所以 `--rights` 只写 `edit delete` 时，命令会自动把 `view` 并进去（5,6,7），并在输出里提示。

归档附件权限 `--file-rights`（与上面的查看/编辑/删除**互相独立**，是另一处勾选）：

| 编号 | 别名 | 含义 |
|---|---|---|
| 501 | `view` / `read` | 归档附件查看 |
| 502 | `download` | 归档附件下载 |
| 503 | `edit` | 归档附件编辑 |

> 归档附件用的是 `501/502/503`，**不是**共享权限的 `401/402/403`，两套别混。

`--file-rights` 不给就不发生成附件权限键，该行只有数据权限。

## 幂等与回读

- 添加前先查一遍：同一个授权对象 + 同一权限组合已存在时直接跳过并报「已存在」，不会重复创建。
- 保存后按新增 ID 回读，逐项核对 `codeType` / `orgType` / `rightType` / `fileRight` / 创建人关系 / 取值字段映射；
  `rightType` 与 `fileRight` 按**集合**比对（平台保留提交时的顺序，但顺序不承载语义）。
- 回读的 `orgTypeName` 会和该类别的预期名称对照（如 `field_employee` 对应「人员字段」）。对不上直接报错 ——
  那意味着授权对象写错了，不能静默放过。
- 字段相关这类计算型授权，平台会回 `isShowRebuild=2`，此时按提示执行
  `e10-cli form permission rebuild <objId> <appId> <权限ID>` —— 等价于在权限行上点【重构】。
  这一步不做，权限列表是不完整的（界面上表现为该行还要重构）。

## 归档卡片

每个流程还有一个「归档卡片」开关（`0` 关 / `1` 开）。不带 `--set` 时只读；带 `--set` 时先写再回读，以回读值为准。
