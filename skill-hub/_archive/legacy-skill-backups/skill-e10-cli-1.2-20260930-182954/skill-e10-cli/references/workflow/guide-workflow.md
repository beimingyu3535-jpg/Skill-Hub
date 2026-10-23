# 流程表单指南

## 流程页面 URL

提交流程的页面后缀是 `/sp/workflow/flowpage/create/流程id`：

```
/sp/workflow/flowpage/create/1281910260426555393
```

---

## URL 传参预填

流程页面支持通过 URL query string 传参来预填表单字段。参数名使用**字段 ID**，参数值为要预填的内容。

```js
var WORKFLOW_ID = '1281935012370612224';
var workflowUrl = publicUrl + '/sp/workflow/flowpage/create/' + WORKFLOW_ID;

// 根据上下文拼接预填参数
if (selectedCell) {
  var params = [];
  if (selectedCell.roomId) {
    params.push(F.roomNo + '=' + encodeURIComponent(selectedCell.roomId));
  }
  if (selectedCell.date) {
    params.push(F.bookingDate + '=' + encodeURIComponent(selectedCell.date));
  }
  if (params.length > 0) {
    workflowUrl = workflowUrl + '?' + params.join('&');
  }
}
// 最终 URL 示例：
// /sp/workflow/flowpage/create/1281935012370612224?1281934337846132742=1356890123456789&1281934337846132739=2026-06-17
```

---

## 注意事项

| 规则 | 说明 |
|------|------|
| 参数名 | 用表单字段 ID（纯数字字符串） |
| 参数值 | 需要 `encodeURIComponent` |
| Select 字段 | 传参时用**选项 ID**（`valueKey`），不能传显示名称 |
| 参数名不生效 | 可能需要换成流程表单里定义的字段标识（短码），让用户确认 |

---

## CLI 流程管理

### 创建流程

```bash
e10-cli workflow create <appId> <formObjId> <name> [desc]
# 自动设置所有人可发起；建流程后自动加「发起菜单」（LAYOUT，指向表单新建页，点开即触发流程）
# 加 --no-menu 可跳过自动菜单
```

### 查看节点

```bash
e10-cli workflow nodes <workflowId>
# 输出节点名称、类型（发起/审批/归档）、操作者、连线关系
```

### 设置审批人

```bash
# 指定人
e10-cli workflow set-operator <workflowId> <nodeId> 张三
# 指定角色
e10-cli workflow set-operator <workflowId> <nodeId> 财务主管 --type role
# 发起人上级
e10-cli workflow set-operator <workflowId> <nodeId> --type superior
# 所有人
e10-cli workflow set-operator <workflowId> <nodeId> --type all
# 自由选择（发起时自己选）
e10-cli workflow set-operator <workflowId> <nodeId> --type free
# 上一节点操作者
e10-cli workflow set-operator <workflowId> <nodeId> --type prev-node
# 指定部门（含下级）
e10-cli workflow set-operator <workflowId> <nodeId> 开发部 --type dept
# 指定岗位
e10-cli workflow set-operator <workflowId> <nodeId> 财务经理 --type position
# 签署顺序 + 批次
e10-cli workflow set-operator <workflowId> <nodeId> 张三 --sign-order 竞签 --orders 0.10
# 组内多操作者（一个节点配多人，任一人或全部审批）
e10-cli workflow set-operator <workflowId> <nodeId> "区域经理,部门领导" --type role --sign-order 竞签
```

**签署方式（--sign-order）概念**——决定"多个审批人之间怎么算通过"：

| 签署方式 | 含义 |
|---------|------|
| **会签**（默认） | 选择的多人**必须都审批通过**才继续流转 |
| **非会签** | 选择的多人中**只要一个人审批通过**就流转下去 |
| **竞签** | 非会签的一种：多人同时可见、**先到先审**，谁先提交谁生效（其他人无需再审） |
| **依次处理** | 按人员选择顺序逐个审批，**全部审完**才流转 |
| **抄送** | 抄送对象，**不影响流转**；需批注的抄送对象批注后转入已办，不需批注的查看即转入已办 |

> **「A 或 B 审批」= 一个节点多人 + 竞签/非会签**，不是物理分两条线。比如"区域经理 或 部门领导审核"：`set-operator <wf> <node> "区域经理,部门领导" --type role --sign-order 竞签`，图上只有一根线。**需求里出现"或/任一人"的审批，优先用竞签/非会签**，只有按条件真正分流（不同分支走不同流程）才拆节点。
> 
> **一个节点多人**：keyword 用逗号分隔（`"角色1,角色2"` 或 `"张三,李四"`）。`set-operator` 每次全量重建该节点操作者组（先清空旧组再新建），重复设置不会堆积。
# 矩阵对应（查矩阵表动态获取审批人）
e10-cli workflow set-operator <workflowId> <nodeId> --type matrix \
  --matrix-id <矩阵ID> --value-config-id <值字段configId> \
  --matrix-rule "<条件configId>:1:1:1" \
  --batch-condition "(申请人 等于 '张三')"
# matrix-rule 格式: 条件configId:数据来源type:匹配operate:维度virtualId
#   type: 0=指定部门 1=发起人部门 5=当前操作人部门
#   operate: 1=本部门 2=本及下级 3=本及上级 49=逐级向上 67=本及下级逐级向上
#   virtualId: 1=行政组织
# 表单相关人员（从表单数据中动态获取审批人）
e10-cli workflow set-operator <workflowId> <nodeId> --type form \
  --source <表单ID> --target <人员字段ID>
```

### 节点签字意见必填（退回时意见必填）

```bash
e10-cli workflow node sign <workflowId> <nodeId>              # 查看当前意见必填配置
e10-cli workflow node sign <wf> <node> --all-required         # 全部操作类型意见必填
e10-cli workflow node sign <wf> <node> --none-required        # 全部不必填
e10-cli workflow node sign <wf> <node> --select "退回,加签"    # 指定操作类型意见必填
```

> 「退回时意见必填」= `--select 退回`（如：上级审核节点退回时要求填写意见）。操作类型以该节点可选范围为准（不同节点类型可操作类型不同）。

### 节点提交校验（智能审批规则，字段 vs 字段）

```bash
e10-cli workflow node validate <workflowId> <nodeId> --view                          # 查看校验状态
e10-cli workflow node validate <wf> <node> --name "一致性校验" \
  --rule "行程明细.行程开始时间 等于 出差开始日期"     # 设置校验：行程开始时间=出差开始日期
e10-cli workflow node validate <wf> <node> --disable                                # 关闭校验
```

> **规则语法**：`--rule "主题字段 操作 值字段"`。主题字段用「**明细表名.字段名**」可定位明细字段，操作支持 等于/不等于/大于/大于等于/小于/小于等于，值字段为比较引用的另一字段（字段 vs 字段，非字面值）。重复执行是**更新**同一条规则；对已配置节点会复用原 conformanceId。校验不通过默认**阻止提交**（FORBID_SUBMIT）。

**表单相关人员**（`--type form`）从指定表单的 Employee 字段动态获取审批人，支持筛选条件：

```bash
# 无筛选：取表单中所有员工
e10-cli workflow set-operator <wf> <nodeId> --type form \
  --source 1294600110549819401 --target 1294600110549819393

# 带筛选：人员级别 > 100
e10-cli workflow set-operator <wf> <nodeId> --type form \
  --source 1294600110549819401 --target 1294600110549819393 \
  --condition '{"fieldId":"1294600110549819396","fieldType":"Number","fieldName":"人员级别","func":"gt","value":"100"}'

# 筛选值引用表单字段：申请人 == 创建者（valueFieldId 在流程表单中查找）
e10-cli workflow set-operator <wf> <nodeId> --type form \
  --source 1294602202274390029 --target 1294602202274390020 \
  --workflow-form 1294601678154162216 \
  --condition '{"fieldId":"1294602202274390020","fieldType":"Employee","fieldName":"申请人","func":"eq","valueFieldId":"2"}'

# 或签
e10-cli workflow set-operator <wf> <nodeId> --type form \
  --source 1294600110549819401 --target 1294600110549819393 \
  --sign-order 或签
```

> `--condition` 格式：`{"fieldId":"字段ID","fieldType":"字段类型","fieldName":"字段名","func":"比较符","value":"固定值"}`。func 支持：`gt`(大于)、`lt`(小于)、`eq`(等于)、`gte`(≥)、`lte`(≤)、`like`(包含)。用 `valueFieldId` 代替 `value` 表示值引用了表单字段，需同时指定 `--workflow-form <流程表单objId>` 告诉 CLI 在哪个表单里找引用字段。`--sign-order` 默认 `会签`。

### 添加节点

```bash
e10-cli workflow add-node <workflowId> <type> "节点名称"
# type: 0=发起 1=审批 2=确认/会签 3=归档 5=投递 7=自动处理 8=等待
#        forkstart=分流点  forkend=合流点  forkmiddle=分流中间点
# 结束节点 = 归档节点（type=3）；流程末尾的归档节点就是「结束」，二者是同一个节点类型
# --node-attr: 0=一般(默认) 1=分流点 2=分流中间点 3=合流点
```

> **分流节点不能做审批**：`forkstart` / `forkmiddle` / `forkend`（nodeAttr 1/2/3）是**纯路由节点**，配不了审批操作者——节点一旦被标成分流/合流点，`set-operator` 就设不上审批人。分流职责和审批职责必须分开：分流节点只负责分叉/合流，审批人放在各分支的**审批节点（type=1）**上，即 `forkstart → 各分支审批节点(type=1) → forkend`。

### 重命名节点

```bash
e10-cli workflow rename-node <workflowId> <nodeId> "新名称"
```

### 添加连线（节点→节点）

一键添加连线：
```bash
e10-cli workflow add-link <workflowId> <fromNodeId> <toNodeId> "标签"
e10-cli workflow add-link <workflowId> <fromNodeId> <toNodeId> "退回" --reject
e10-cli workflow add-link <workflowId> <fromNodeId> <toNodeId> "主线路" --default
```

批量添加连线：
```bash
e10-cli workflow add-links <workflowId> @links.json
# links.json: [{"from":"nodeId","to":"nodeId","label":"发起→审批","reject":true,"default":false}]
```

> **多条连线用 `add-links`**：`add-link` 内部 fetch→修改→save，并行的会覆盖。`add-links` 按顺序逐条执行，每条都从服务端拉最新 XML 再改，不会丢数据。不要用 `&` 或 `parallel` 并跑 add-link。

### 删除连线

```bash
# 先用 workflow nodes --json 获取连线的 linkId
e10-cli workflow nodes <workflowId> --json
# 返回的 links 数组每条都有 linkId，可直接删除
e10-cli workflow delete-link <workflowId> <linkId>
# 支持一次删多条
e10-cli workflow delete-link <workflowId> <linkId1> <linkId2>
```

> **注意**：`workflow nodes --json` 返回的每条连线都带 `linkId`，用它来删除，不要用 nodeId。

### 查看出口列表

```bash
e10-cli workflow link-list <workflowId>
# 显示源节点→目标节点、默认出口[默认]、退回出口[退回]、条件状态[有条件]
# --node-id 过滤单个源节点的出口
e10-cli workflow link-list <workflowId> --node-id <nodeId>
```

### 修改/删除出口（列表方式）

```bash
# 先获取当前出口列表作为基线
e10-cli workflow link-list <workflowId> --json > links.json
# 修改后保存
e10-cli workflow link-save <workflowId> @links.json
# 删除指定出口
e10-cli workflow link-save <workflowId> @links.json --delete-rows "linkId1,linkId2"
```

### 查看节点列表（含分流/合流属性）

```bash
e10-cli workflow nodes <workflowId> --mode list
# 显示 nodeAttr（0=一般/1=分流点/2=分流中间点/3=合流点）+ mergeType（全部分支/指定分支/分支数/比例）
```

### 全流程搜索（不依赖 appId）

```bash
e10-cli workflow search --name "费用报销"
e10-cli workflow search --id <workflowId>
e10-cli workflow search --name "审批" --belong 1 --page-size 50
```

### 节点操作菜单

```bash
# 查看菜单
e10-cli workflow node menu <workflowId> <nodeId>
# 切换菜单启用状态
e10-cli workflow node menu <workflowId> <nodeId> --toggle <menuId>
```

### 节点退回设置

```bash
# 查看
e10-cli workflow node reject <workflowId> <nodeId>
# 修改
e10-cli workflow node reject <workflowId> <nodeId> \
  --remind 1 --type 1 --checked-node 1 --submit-type 1
```

### 节点超时处理

```bash
# 查看
e10-cli workflow node timeout <workflowId> <nodeId>
# 新增超时规则（指定时间 48h，下一操作者，超时前 2h 提醒）
e10-cli workflow node timeout <workflowId> <nodeId> \
  --time-type 1 --time-value 48 --flow-type 1 --remind-type 0 --remind-hours 2
```

### 工作流维度设置

```bash
# 提交确认
e10-cli workflow setting submit <workflowId> --confirm 1
# 签字意见
e10-cli workflow setting sign <workflowId> --show-order 1
# 评论
e10-cli workflow setting comment <workflowId> --enable 1
# 批量操作
e10-cli workflow setting batch <workflowId> --enable-batch 1 --enable-reject 1
# 自动处理
e10-cli workflow setting auto <workflowId> --enable 1 --way 0
# 其他设置
e10-cli workflow setting other <workflowId> --message-op 1 --auto-save 1
# 流程标题规则（保存/提交后生成标题）
e10-cli workflow setting title <workflowId>                                   # 查看可用变量
e10-cli workflow setting title <wf> --rule "工作流名称|发起人|提交日期" --sep "-"  # 标题=流程名-发起人-提交日期
e10-cli workflow setting title <wf> --disable                                 # 关闭自动生成标题
```

> **流程标题**：`--rule` 用竖线分隔字段名（可用 `工作流名称`/`发起人`/`提交日期`/`流程编号` 等系统字段或任意表单字段名），`--sep` 指定分隔符（默认 `-`）。CLI 自动把字段名解析成占位编码（如 `工作流名称=-100`）并启用 `subtitleType` 开关。

### 高级设置

```bash
# 流程存档
e10-cli workflow advanced doc <workflowId> --enable 1 --doc-types "0,1"
# 定时触发（每日 09:00）
e10-cli workflow advanced schedule <workflowId> \
  --enable 1 --frequency '{"item1":1,"item2":1}' --time "09:00:00" --weekday-only 1
# 定时触发人员范围
e10-cli workflow advanced schedule-range <workflowId> --list
```

### 整体重写流程图（save-layout）

大规模调整节点连线时，构造完整 XML → 一次性保存覆盖当前布局：

```bash
# 1. 将 XML 文件保存为流程布局（覆盖当前）
e10-cli workflow save-layout <workflowId> @layout.xml

# 2. 构造完整 XML（浏览器 mxGraph 格式）
```

XML 格式示例（浏览器 mxGraph 格式：节点 cell id 用纯数字，带真实 `nodeId`；连线带真实 `linkId`，`source`/`target` 引用节点的数字 id）：
```xml
<mxGraphModel grid="0" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1331" pageHeight="888" background="#ffffff"><root>
<mxCell id="0"/><mxCell id="1" parent="0"/>
<!-- 节点：vertex="1"，带 nodeId -->
<mxCell id="2" value="发起节点" style="rounded=1;whiteSpace=wrap;html=1;resizable=1;rotatable=0;arcSize=10;fillColor=#5D9CEC;strokeColor=#5D9CEC;" vertex="1" nodeType="0" nodeId="节点ID" operatorNameStr="    " parent="1"><mxGeometry x="465" y="80" width="170" height="64" as="geometry"/></mxCell>
<mxCell id="3" value="审批节点" style="..." vertex="1" nodeType="1" nodeId="节点ID" parent="1"><mxGeometry x="465" y="220" width="170" height="64" as="geometry"/></mxCell>
<!-- 连线：edge="1"，带 linkId、source、target -->
<mxCell id="6" value="发起 至 审批" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor=#5D9CEC;" edge="1" linkId="连线ID" isDefault="0" isReject="0" orderId="0.0" source="2" target="3" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
</root></mxGraphModel>
```

**关键规则**：
- 节点的 `id` 用数字（2, 3, 4...），连线的 `source`/`target` 引用节点的 `id`
- 连线的 `linkId` 是服务端分配的唯一标识，删除连线用这个
- 保存：`e10-cli workflow save-layout <workflowId> @修改后的.xml`
- **务必保持浏览器格式**：服务器 saveLayout 只认纯数字 cell id。`getXml` 输出的 `node_xxx`/`link_xxx` 格式直接回传会解析失败（节点被判为 null/已删除）

### 节点自动排版（auto-layout）

CLI 搭建的流程（add-node 加节点）节点通常挤在一列，用自动排版重排：

```bash
# 默认左右分层（发起在最左）
e10-cli workflow auto-layout <workflowId>

# 上下排布（发起在最顶，平台连线默认纵向）
e10-cli workflow auto-layout <workflowId> --direction ttb

# 只算不打回（看分层结果）
e10-cli workflow auto-layout <workflowId> --dry-run
```

**算法**：读 getXml → 按连线最长路径分层（忽略退回线）→ 全量重排节点 mxGeometry → saveLayout 回写 → 回读验证。分支（forkstart→分支们→forkend）自然融入分层，同层节点垂直排开。只改节点坐标，连线自动正交路由。

---

## 相关指南

- **分支条件 / 出口条件 / 条件 JSON** → `workflow/guide-workflow-condition.md`
- **动作流（跨表单写入）/ 提交事件 / 角色管理** → `workflow/guide-workflow-action.md`
