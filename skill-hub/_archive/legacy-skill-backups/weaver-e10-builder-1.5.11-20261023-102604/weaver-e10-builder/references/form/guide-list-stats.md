# 顶部统计：主表与明细

`form list-stats` 配置已有台账视图的统计。支持 sum/count/avg/max/min，以及千分位、小数位、万/亿单位、条件统计；还能配**每条统计项的启用状态**与**统计面板三项**（显示位置 / 手动加载统计值 / 点击统计结果过滤列表数据）。来源表单 `objId`、应用 `appId`、目标视图 `listId` 与明细子表 `subFormId` 是不同 ID。

## 查询及单项配置

```bash
e10-cli form list-stats <objId> <appId> <listId> --json
e10-cli form list-stats <objId> <appId> <listId> --add @stat.json
e10-cli form list-stats <objId> <appId> <listId> --remove <statId>
```

主表与明细字段均使用真实 fieldId；CLI 展开 `ds/fields` 的明细分组，未命中时按 `getFormField` 补查。字段必须属于当前表单，指定 subFormId 时必须与字段实际归属一致。

付款金额统计示例：

```json
{
  "fieldId": "1310832033224278033",
  "type": "sum",
  "name": "合同付款金额",
  "decimalPlaces": "2",
  "thousandths": true
}
```

明细记录计数可省略 fieldId：

```json
{
  "type": "count",
  "subFormId": "1310832033224278030",
  "name": "付款记录数"
}
```

计数写为 `fieldId="5" + subFormId`，统计明细记录数。传明细字段做 count 也会转成该子表的记录计数，并非此字段非空值计数。主表记录计数可使用 `{"type":"count","name":"记录数"}`；已有传主表 fieldId 的用法继续接受。

主表的 subFormId 写 `-1`，明细写实际子表 ID。**当前平台会将明细字段 sum 等字段聚合回读的 subFormId 规范化为 `-1`，仍由唯一 fieldId 定位明细字段；明细 count 必须保留子表 ID。** 回读校验兼容这种规范化，不允许字段或计数子表发生变化。

格式参数：`thousandths` 为布尔值；`decimalPlaces` 为 -1 或 0–20 的整数；单位支持 `unit: "万"/"亿"` 或 `unitType: "none"/"tenThousand"/"hundredMillion"`。主表保持原默认小数位 -1，明细非计数默认 2，计数默认 -1。sum/avg 要求数值字段。

## 条件统计

```json
{
  "fieldId": "1310832033224278033",
  "type": "sum",
  "name": "正数付款金额",
  "conditions": [
    {"fieldId": "1310832033224278033", "func": "gt", "value": 0}
  ]
}
```

条件支持主表字段和本次统计子表字段，多个条件默认 AND。`valueField` 可引用字段 ID 或唯一名称，字段引用也校验子表归属。跨其他明细子表的条件拒绝保存，避免产生不明确的关联语义。

条件写入明文 `rootdata`，无需 LZW。明细节点携带 `mainField=false`、`subTableId` 等信息；不能把它当成主表字段。操作符与现有条件构建器一致：eq/neq/gt/lt/range/aggregate/unaggregate/contains/uncontains/empty/nempty/startWith/endWith，支持原兼容别名。

## 批量明细统计

```bash
e10-cli form list-stats detail <objId> <appId> <listId> <subFormId> --fields <金额fieldId> --name-prefix "付款-"
```

为指定数值字段分别生成 sum，并增加一项子表 count；一次保存。省略 `--fields` 时使用字段目录中该子表的全部数值字段。名称为“前缀+字段名+合计”和“前缀+子表名+记录数”。

重复运行时，已有同名同配置项会复用并返回 `unchanged/reused`，不会重复新增；同名不同配置则报错，应先查询并明确移除旧项。批量操作同样可以使用 `--pc-only`。

## 启用状态

每条统计项**单独**有启用状态。建的时候可以直接建成停用：

```json
{ "fieldId": "1310832033224278033", "type": "sum", "name": "备用金额", "enable": false }
```

改**已有**项的启用状态用 `--enable` / `--disable`（逗号分隔统计项 ID）：

```bash
e10-cli form list-stats <objId> <appId> <listId> --disable 1310832033224278099
e10-cli form list-stats <objId> <appId> <listId> --enable  1310832033224278099
```

⚠ `--add` 遇到**同名同配置**已存在的项会复用，**不会**顺带改它的启用状态 —— 要改就用 `--enable` / `--disable`。已经是目标状态时跳过、不算改动（重复执行返回 `unchanged`）。

## 面板三项

显示位置、手动加载统计值、点击统计结果过滤列表数据是**每视图一份**的统计面板设置：

```bash
# 显示位置：顶部显示 / 顶部简约显示 / 右上角显示（也收中文标签）
e10-cli form list-stats <objId> <appId> <listId> --position topRight
# 手动加载统计值（开了就不进视图自动跑）
e10-cli form list-stats <objId> <appId> <listId> --manual-load on
# 点击统计结果过滤列表数据
e10-cli form list-stats <objId> <appId> <listId> --filter-data on
```

三项都是**三态**：`on|off`，**不传就是保持原值**，不会把没提到的开关覆盖掉。位置三档的取值 `top` / `topSimple` / `topRight` 对应界面上的「顶部显示 / 顶部简约显示 / 右上角显示」。

⚠ **别被报文骗了**：设计器保存请求里带的 `statisticsPositionSpan` 是**陈旧值** —— 切到「顶部简约显示」或「右上角显示」时，请求体里仍然发「顶部显示」。但服务端读回来会**按 `position` 重算**成对应文案（`topSimple` → 顶部简约显示、`topRight` → 右上角显示）。命令两边都写死，发出去的报文自洽，并在回读时同时核对位置与文案。

⚠ 面板三项只写 PC 侧，**不动移动端配置**。统计随 `listId` 共享，平台会把它同步到移动端读回；正因为如此，移动端一致性校验会把这四个面板键和 `statisticsList` 一起排除（它们的变化是共享造成的，不是「移动端其它配置被冲掉」）。

## 条件里的日期快捷档

统计条件的日期字段选「区间」时，可以直接用设计器那排快捷（今天 / 本周 / 今年 …，共 16 档）代替起止日期：

```json
{
  "fieldId": "1310832033224278033",
  "type": "sum",
  "name": "今年付款额",
  "conditions": [{ "fieldId": "<创建时间fieldId>", "quick": "今年" }]
}
```

`quick` 与 `func` / `value` / `valueField` **互斥**（快捷档本身已经决定了区间）。口径与设计器一致：起点为首日 `00:00:00`、终点为末日 `23:59:59`，**周从周一起算**。

⚠ 与设计器行为相同，落下来是**静态**起止日期（不是运行期动态刷新），每次执行按当时日期重算。中文标签在部分终端经命令行传参会遇到编码问题，此时可用英文别名（`thisYear` / `thisMonth` / `lastWeek` …）或 `--add @文件`。

## 保存与移动端

- 保留 PC 完整配置，仅更新 `listStatistics`；删除用 `operation: DELETE`，不能只从数组移除。
- 读取真实移动端配置作为 `mConfig` 原样回传。默认移动端读取失败就停止；仅明确不使用移动端时加 `--pc-only`。
- 保存后校验新增项、原有项、删除结果及移动端配置。`verified: true` 表示配置回读一致，不等于已经核对实际统计数值。
- **维森测试93当前平台按 listId 共享 PC/MOBILE 统计项。** 当保存前后两端统计集合均对应一致时，返回 `mobileStatistics: "shared"`；改统计会同时影响两端。移动端独有统计丢失或其他配置变化仍报错。不要承诺共享环境下“只改 PC 统计”。
- 比较移动端配置时，仅排除已实证每次读取会重建的按钮事件临时 ID，以及**随 `listId` 共享的统计项与统计面板键**（`statisticsList` / `statisticsPosition` / `statisticsPositionSpan` / `statisticsManualLoad` / `enableStatisticsFilterData`）；业务按钮 ID、动作内容、列配置等仍核对。`mobilePreserved` 表示移动端其余配置及独立统计得到保护。
- 如果提示“已保存，但回读不一致”，先查询统计和移动端状态，不直接重试新增。

## 计划与验收

计划模板 3.3 的顶部统计项应记录：视图 ID、主表/明细范围、子表名称/ID、字段名称/ID、聚合方式、条件、格式、统计项 ID、PC/MOBILE 共享状态及验证结果。

在“合同付款”视图验证：明细金额 sum、子表 count、明细条件、主表回归、重复运行、删除回读和移动端保护。不要改写用户已经配置的“合同付款金额”“付款记录数”；使用独立名称测试，结束清理临时项。实际金额与记录数须另用已知数据核对，不能仅凭保存成功认定数值正确。
