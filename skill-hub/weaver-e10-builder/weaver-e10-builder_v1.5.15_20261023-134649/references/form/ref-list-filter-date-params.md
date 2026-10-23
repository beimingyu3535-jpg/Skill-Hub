# 条件里的日期系统参数占位符

适用于视图数据条件（`form list-filter`，写入 `saveNListConfig` 的 `config.filter`）里的**日期字段**。
日期字段的算子为**等于（`func: "eq"`）**时，右值可以直接写平台系统参数占位符；平台把占位符**原样存成字符串**，查询时按当时时间求值，不会像 `quick` 那样展开成死日期。

```json
{"fieldId":"<日期字段fieldId>","func":"eq","value":"{curryear}","text":"本年"}
```

- `value`：占位符原文（含花括号），原样保存，不要自己先算成日期。
- `text`：界面显示名（如「本年」）。设计器回读时用它渲染条件，建议一并给出。
- 已确认只用于 `eq`；其它算子请走普通值或 `quick`。命令对日期字段的非 `eq` 占位符会直接报错。
- `n` 为整数，`:+n` / `:-n` 表示当前值之后 / 之前 n 个单位。

> `quick`（今天 / 本周 / 今年…）与占位符是两条路：`quick` 是区间快捷档，保存时算成固定起止日期；占位符是动态右值，运行期才求值。要「每年自动跟进」用占位符，不要用 `quick`。

## 占位符清单

| 占位符 | 含义 |
|---|---|
| `{date}` | 当前日期（`yyyy-MM-dd`） |
| `{date:+n}` | 当前日期后 n 天 |
| `{date:-n}` | 当前日期前 n 天 |
| `{time}` | 当前时间（`HH:mm:ss`） |
| `{thisweek}` | 当前周所在的日期区间 |
| `{thismonth}` | 当前月所在的日期区间 |
| `{thisyear}` | 当前年所在的日期区间 |
| `{lastweek}` | 上一周所在的日期区间 |
| `{lastmonth}` | 上个月所在的日期区间 |
| `{lastquarter}` | 上一季度所在的日期区间 |
| `{lastyear}` | 上一年所在的日期区间 |
| `{recentdays:-n}` | 距当前日期近 n 天的日期区间 |
| `{recentmonths:-n}` | 距当前日期近 n 个月的日期区间 |
| `{recentyears:-n}` | 距当前日期近 n 年的日期区间 |
| `{year}` | 当前年 |
| `{year:+n}` | 当前年的后 n 年 |
| `{year:-n}` | 当前年的前 n 年 |
| `{half}` | 当前半年度（`01-01` ~ `06-30`） |
| `{yearhalf}` | 当前年的当前半年度 |
| `{yearhalf:+n}` | 当前半年度的后 n 个半年 |
| `{yearhalf:-n}` | 当前半年度的前 n 个半年 |
| `{quarter}` | 当前季度 |
| `{yearquarter}` | 当前年的当前季度 |
| `{yearquarter:+n}` | 当前季度的后 n 个季度 |
| `{yearquarter:-n}` | 当前季度的前 n 个季度 |
| `{thisquarter}` | 当前季度是当前年的第几季度 |
| `{firstdayinthismonth}` | 当前月的第一天 |
| `{lastdayinthismonth}` | 当前月的最后一天 |
| `{month}` | 当前月（`01`~`12`） |
| `{yearmonth:+n}` | 当前年月的后 n 个月（`yyyy-MM`） |
| `{yearmonth:-n}` | 当前年月的前 n 个月（`yyyy-MM`） |
| `{day}` | 当前日 |
| `{hour}` | 当前时 |
| `{minute}` | 当前分 |
| `{second}` | 当前秒 |
| `{dateweek}` | 当前日期的星期（如「星期三」） |
| `{weekinmonth}` | 当前日期在本月的第几周 |
| `{weekinyear}` | 当前日期在本年的第几周 |
| `{weekinyear:+n}` | 当前日期在本年的周数往后加 n 周 |
| `{weekinyear:-n}` | 当前日期在本年的周数往前减 n 周 |
| `{week}` | 当前周（`01-01` ~ `01-07` 这种月日区间） |
| `{mon}` / `{tue}` / `{wed}` / `{thu}` / `{fri}` / `{sat}` / `{sun}` | 当前周的周一 / 周二 / … / 周日所在日期 |
| `{mon:+n}` 等 | 对应星期几所在日期的后 n 天 |
| `{mon:-n}` 等 | 对应星期几所在日期的前 n 天 |
| `{curryear}` | 当前年（设计器「本年」条件实测使用；与 `{year}` 同类） |

## 命令示例

```bash
# 台账只显示「等于本年」的数据
e10-cli form list-filter <objId> <appId> <listId> \
  --add '{"conditions":[{"fieldId":"<日期字段fieldId>","func":"eq","value":"{curryear}","text":"本年"}]}'

# 近 7 天
e10-cli form list-filter <objId> <appId> <listId> \
  --add '{"conditions":[{"fieldId":"<日期字段fieldId>","func":"eq","value":"{recentdays:-7}","text":"近7天"}]}'

# 当前日期后 3 天
e10-cli form list-filter <objId> <appId> <listId> \
  --add '{"conditions":[{"fieldId":"<日期字段fieldId>","func":"eq","value":"{date:+3}","text":"3天后"}]}'
```

保存后 `--json` 回读，`conditions.value` 应仍是 `{...}` 原文；被展开成具体日期说明走错了路径（多半是用了 `quick`）。
