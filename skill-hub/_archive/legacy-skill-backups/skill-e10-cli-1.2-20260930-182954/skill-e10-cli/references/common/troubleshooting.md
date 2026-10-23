# e10-cli 搭建实战错误排查手册

> 适用场景：Ebuilder 应用搭建（建表/流程/动作流/菜单/页面）
> 来源：实战问题沉淀（验证应用搭建任务），经「错误复盘协议」逐条确认后入库
> 维护：每次完整任务后按 SKILL.md「错误复盘协议」追加用户确认的条目
>
> **使用方式：报错先查本文档**，命中现象直接按「解决」执行；未命中再排查，并记入下次复盘。

---

## 一、环境与平台限制

### 1.1 CLI 建表报错「当前环境未启用物理表，不能自定义数据库表名」

- **现象**：`e10-cli form create` 直接失败，报「当前环境未启用物理表，不能自定义数据库表名」
- **根因**：CLI 建表路径先查询平台存储设置 `POST /api/ebuilder/form/form/comp/queryFormStorageSetting`，要求 `storageSettings` 含 `physical`。部分环境（如 weapp.eteams.cn）只有 `["share"]` → CLI 拒绝建表
- **解决**：该环境只能建**逻辑表**（`isPhysical=false`，浏览器手动建表同样走此路径）：
  1. 平台接口建壳：`POST /api/bs/ebuilder/form/obj/saveOrUpdate`（**不带 tableName/tableType**，`isAdvance:false` + `layoutType:FLOW`），返回 objId/formId
  2. 复用 CLI 内部函数 `addInitialFieldsToCustomPhysicalForm`（`node_modules/e10-cli/dist/services/form-create.js`，**不依赖物理表**）：字段+布局+明细表+台账菜单一步完成
  3. 建壳后 `form add-field / serial-mark / validate / ebuilder-scope / list-columns` 等在逻辑表上全部可用
- **预防**：建表前先探测环境（SKILL.md 工作流 step 0.5）：`node scripts/probe-env.mjs <appId>` → physical=false 直接走逻辑表脚本，不试 form create

### 1.2 Ecode 页面创建报错「e-code授权校验失败」（401）

- **现象**：`e10-cli project create`、`project tree` 均返回 401「e-code授权校验失败！」
- **根因**：当前登录账号在该环境**未开通 E-code 开发权限**（环境级授权，与 Ebuilder 权限相互独立）
- **解决**：需环境管理员给账号开通 Ecode 开发者权限；开通前无法创建自定义页面（项目工作台等）
- **预防**：接到含自定义页面需求时，工作流 step 0.c 先 `e10-cli project tree 0` 探测授权；401 则提前告知用户（不阻塞段①②），避免做到最后一步才暴露

### 1.3 平台接口返回中文乱码（`????` / `å®¢æˆ·ä¿¡æ¯`）

- **现象**：PowerShell `Invoke-RestMethod` 发中文 body，平台存的名字变 `????`；读取时控制台显示 `å®¢æˆ·ä¿¡æ¯`
- **根因**：PowerShell 5.1 默认编码（GBK/ANSI）与平台 UTF-8 不一致：写时 body 字节被破坏，读时显示层解码错位
- **解决**：
  - 写操作：改用 **Node 脚本**（CLI 同款 `fetch` + `JSON.stringify`，天然 UTF-8），不用 PowerShell 拼 JSON body
  - 读操作：控制台乱码 ≠ 平台数据错；用 Node 读取验证（如 `e10-cli form list` 显示空名时，用 getList 接口核实）
- **预防**：涉及中文的 API 直连一律走 Node；PowerShell 只跑 CLI 命令

---

## 二、PowerShell / Windows 兼容陷阱

### 2.1 JSON 传参被 PowerShell/Windows 转义破坏（CLI 与 py 通用，主条目）

- **现象**（同根因多个场景，按同类合并规则归并为一条）：
  - CLI：`--rules '[{"field":"客户状态",...}]'` 报「不是有效 JSON」；`--constants '{"...":"..."}'` 报「JSON 解析失败」
  - py：PowerShell 单引号包 JSON → 「Expecting property name enclosed in double quotes」；cmd /c 转义后 → 「缺少 name/baseUrl/eteamSid 参数」
- **根因**：PowerShell 引号/转义规则与 cmd 不同，内联 JSON 双引号丢失；Windows 双层转义进一步破坏 JSON
- **解决**：统一用 `@文件` 传参（CLI 与 py 均支持）：
  ```bash
  # CLI 侧
  e10-cli form ebuilder-scope set ... --rules @scope.json
  e10-cli workflow action create ... --constants @constants.json --sysvar @sysvar.json
  # py 侧（py 的 load_json_arg 原生支持 @文件，UTF-8 无 BOM）
  python actionflow_skill.py env-add @env.json
  python actionflow_skill.py generate @plan.json
  ```
- **预防**：规则：CLI/py 选项带 JSON 值 → 写文件再 `@` 引用，禁止命令行内联 JSON
- **补充场景（py 特有）**：
  - 环境注册参数名是 **`eteamSid`**（不是 eteamsId）
  - `@文件` 必须是 **UTF-8 无 BOM**：PowerShell `Set-Content -Encoding UTF8` 会写 BOM → py 报「Unexpected UTF-8 BOM」；用 Node / `write` 工具 / `[System.IO.File]::WriteAllText(..., (New-Object System.Text.UTF8Encoding($false)))` 写入
  - 中文内容文件读取必须 `-Encoding UTF8`，否则读到乱码（椤圭洰绔...）

### 2.2 PowerShell 把 CLI 的 stderr 输出当错误（NativeCommandError）

- **现象**：每个命令都显示 `node.exe : [AUTH] 认证文件: ...` 红字 + `[exit code: 1]`，但命令实际成功
- **根因**：CLI 把 `[AUTH]` 等日志写 stderr，PowerShell 将 stderr 渲染为错误
- **解决**：判断成败看**业务输出**（`已创建/已保存/已配置`）而非 exit code；过滤用 `2>&1 | Out-String` 后 `Select-String`，或 `2>$null`
- **预防**：不要因 exit code=1 就判定失败；先看 stdout 业务行

### 2.3 管道截断导致 CLI 命令中断

- **现象**：循环里 `e10-cli ... | Select-Object -First 1`，后续命令显示失败/未执行
- **根因**：`Select-Object -First` 提前关闭管道，CLI 进程被中断（写操作可能已执行但输出丢失）
- **解决**：批量执行用完整捕获：`$r = e10-cli ... 2>&1 | Out-String; if ($r -match "已保存") {...}`
- **预防**：循环内不截断输出流

### 2.4 form read 导出的 JSON 含重复键，PowerShell ConvertFrom-Json 报错

- **现象**：`ConvertFrom-Json : duplicated keys 'tenant_key' and 'TENANT_KEY'`
- **根因**：平台返回大小写重复键，PowerShell 解析器严格拒绝
- **解决**：用 Node `JSON.parse` 解析，或只取需要的字段
- **预防**：读取 CLI 导出的 JSON 用 Node 脚本

---

## 三、CLI 命令使用陷阱

### 3.1 `workflow condition add` 第二个参数是**连线 ID**，不是源节点 ID

- **现象**：条件保存提示「已保存并绑定」，但 `condition list` 显示 0 个、`link-list` 的 hasCondition=false
- **根因**：`condition add <wf> <sourceId> <nodeId> <name>` 的 sourceId 实际是 **linkId**（内部走 `saveLinkConditionKey {workflowId, linkId: sourceId, ...}`）；传节点 ID 会静默绑定失败
- **解决**：先 `link-list` 拿目标连线 ID，再 `condition add <wf> <linkId> <目标节点ID> "名称" --rule "..."`
- **预防**：条件绑定后必须 `condition list` + `link-list` 双重验证 hasCondition

### 3.2 `workflow node validate` 的限制（SUM 不支持 / 字段列表截断 / 单规则覆盖）

- **现象 1**：规则「付款信息.付款金额 等于 项目金额」语义错误——比较的是**单行明细值**，不是累加
- **根因**：node validate 只支持「字段 vs 字段/字面值」，**不支持 SUM() 表达式**
- **解决（累加校验正确姿势）**：
  1. 表单加隐藏字段「付款金额合计/付款比例合计」：`form add-field` + `form formula set --expression "SUM({付款信息.付款金额})"` + `form layout set-read-only`
  2. `node validate` 比较合计字段：「付款金额合计 等于 项目金额」
- **现象 2**：规则引用字段提示「找不到主题字段」，但 `form read` 里字段存在
- **根因**：node validate 的 `conditionFieldBrowser` 默认只返回**前 10 个字段**（无分页参数），后面的字段解析不到
- **解决**：直连接口时加 `pageNo:1, pageSize:200`；或 searchValue 查询
- **现象 3**：CLI 每次设置只有一条规则（重复调用会覆盖/合并）
- **解决**：多条规则（AND）需脚本直连平台 API：`saveConformance`（set 建壳 → set 挂 conditionKey → base 启用），规则数无限制
- **预防**：多规则校验、SUM 校验走脚本；单规则简单校验用 CLI

### 3.3 `menu permission add` 报「未找到角色: xxx」

- **现象**：`--type role` 授权报未找到角色，但 `role list` 里有该角色
- **根因**：CLI 用 `n.name === keyword` 匹配，而角色树接口（`role/tree?menuCode=roleSettings`）返回字段是 `title`/`content`，**没有 name 字段** → 永远匹配不上
- **解决**：直连授权接口 `POST /api/cusapp/permissionForm/table/add`（payload 按 CLI `buildAddPayload` 结构，targetType:10=角色）
- **预防**：角色授权优先脚本直连；或等 CLI 修复

### 3.4 菜单权限的「正解」是 shareMap，不是独立授权接口

- **现象**：`permissionForm/table/add` 返回 200 但查询接口查不到授权；直接回传菜单原对象调 `savePublishMenu` 会把菜单改坏（pageType 变 EMPTY、pageId 清空）
- **根因**：菜单可见性最终由导航对象的 `shareMap` 决定；savePublishMenu 回传时字段结构不完整导致页面信息丢失
- **解决**：构造**完整 navigation**（含 `page:{pageId,pageName,pageType,terminalScopes,appid}` + `shareMap:[{targetId,targetType:10,...}]`）调 `savePublishMenu`；保存后校验 `pageType` 未变、shareMap 含角色
- **预防**：改菜单前先备份完整菜单对象；改后必须用 `allMenus` 接口验证 pageType/pageId/shareMap

---

## 四、动作流 py 生成器（actionflows）使用陷阱

> JSON 传参转义问题已并入 2.1（主条目），本章只列 py 特有陷阱。

### 4.1 generate 的 plan 结构（event/actions）

- **现象**：`planFile` 传 `semantic_plan` / `trigger` 键名均报「event.type is required」
- **根因**：generate 期望顶层结构 `{"plan":{"event":{"type":"ApproveTrigger","params":{...}},"actions":[{...}]},"appName":"..."}`；event 组件对象必须含 `type` + `params`
- **解决**：按上述结构编写；最小可跑示例先验证结构（actions 可空数组），再加内容
- **预防**：先 `previewOnly:true` 验证结构，再正式 generate

### 4.2 ActionEbUpdate/ActionEbDelete 的 filterCondition 格式

- **现象**：数组形式 `[{field:"ID",operator:"=",value:...}]` 报「filterCondition must be an object」；field 传纯 ID 字符串报「左侧字段 id='' 不在目标表单」
- **根因**：filterCondition 是**单对象**（非数组），且 field 必须是 **`{id, name}` 对象**
- **解决**：
  ```json
  "filterCondition": {
    "field": {"id": "目标表字段ID", "name": "字段名"},
    "operator": "=",
    "value": {"type": "context", "paramKey": "<工作流ID>.requestId", "label": "流程ID"}
  }
  ```
- **预防**：`describe` 说的「[{field,...}]」与实际校验器要求不符，以校验器报错为准

### 4.3 context 引用（paramKey）必须是完整路径

- **现象**：`paramKey` 写裸字段 ID（如 `1304902242637365511`）报「unresolved context reference」
- **根因**：context 引用必须是 `<workflowId/tableId>.<fieldId>` 完整格式
- **解决**：用 `workflow-context-fields` / `component-context` 返回的原始 paramKey，不手写
- **预防**：动态映射一律先查 context，禁止猜路径（禁止 FormData.xxx/ApprovalData.xxx 设计器路径）

### 4.4 动作流名称乱码（AI-椤圭洰绔嬮」...）

- **现象**：py 生成的动作流绑定后名称显示乱码
- **根因**：命令行内联传参时中文被编码破坏（GBK↔UTF-8）
- **影响**：仅名称显示问题，动作流实体/绑定/触发均正常；可在设计器手动重命名
- **预防**：已由 `@文件` 传参规范规避（见 2.1）——appName 等中文参数一律走 `@文件`（UTF-8 无 BOM），不再命令行内联

---

## 五、动作流配置（CLI 侧）要点

### 5.1 update/delete 含 requestId 定位必须走 py 生成器

- **现象**：CLI `action create` 的 `--match-field` 只认流程表单字段，**无法引用 requestId** 定位台账记录
- **解决**：py 生成器生成（filterCondition 动态右值 = `{type:context, paramKey:"<wfId>.requestId"}`）→ 得到 appId → CLI `action create <wf> <node> 名称 --app-id <appId> --event leave/revert` 绑到节点
- **事件时机**：归档更新用 `--event leave`（py 端 triggerTiming=workflow_completed）；退回删除用 `--event revert`
- **预防**：涉及 requestId 定位的 update/delete 直接规划 py 生成器，不要尝试 CLI 硬配

### 5.2 表单级动作流（无流程表单）

- **场景**：工时台账（直接录入，无流程）变更时累加项目工时
- **解决**：py `EventFormData`（triggerTimes:["afterAdd"]）+ `ActionEbUpdate`（opType:"id"，updateId=context 关联项目字段，mapping `"源字段":"+目标字段"` 累加）
- **注意**：`fieldDataChange` 触发仅物理表支持，逻辑表必须用 `afterAdd/afterUpdate/afterDelete`
- **预防**：无流程表单的联动先想清楚触发时机，逻辑表环境避开 fieldDataChange

---

## 通用排查顺序（建议流程）

```
报错 → 判断环境类 vs 命令类 vs 转义类：
1. 环境类（物理表/授权/权限）→ 查第一节：探测接口先行
2. 转义类（JSON 解析失败/乱码）→ 查第二节：全部改 @文件 + Node 脚本
3. 命令类（找不到字段/静默失败）→ 查第三节：先看 CLI help 参数语义，验证用回读接口
4. 动作流类 → 查第四/五节：py 生成器结构先行
验证铁律：配置后必须回读验证（condition list / link-list / allMenus / list-node），不轻信「已保存」
```

---

## 维护记录

| 日期 | 来源任务 | 新增/变更条目 |
|------|---------|---------|
| 2026-04（首次） | 验证应用搭建（e10-cli-work/验证应用） | 新增 1.1~1.3、2.1~2.4、3.1~3.4、4.1~4.5、5.1~5.2 |
| 2026-04（优化） | skill 调优（物理表探测/@文件传参/同类合并） | 变更：1.1/1.2 预防段引用探测脚本；2.1 扩为主条目（并入 py 传参+BOM+eteamSid 补充场景）；4.1 并入 2.1，第四章重排为 4.1~4.4；4.4（原 4.5）标注已由 @文件 规避 |
