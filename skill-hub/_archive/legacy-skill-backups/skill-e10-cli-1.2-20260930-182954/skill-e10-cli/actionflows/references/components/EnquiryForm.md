# 数据源查询（`EnquiryForm`）

## 用途

查询指定数据源下的数据。用于校验拦截（先查台账是否已有记录）、数据准备等场景。数据源必须通过 form-list / 数据源接口查到真实 id + text。

## Plan 位置

作为动作流的动作（action）使用。

## 最小示例

```json
{
  "type": "EnquiryForm",
  "params": {
    "dataSource": "<按 describe 填写>",
    "person": "<按 describe 填写>"
  }
}
```

参数的完整类型、默认值、动态必填和平台对象形状，使用 `component-search` 选型后再调用 `describe` 获取。
