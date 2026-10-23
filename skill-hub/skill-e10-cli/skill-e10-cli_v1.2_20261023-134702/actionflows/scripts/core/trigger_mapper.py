"""定时与日期触发器的真实 DTO 映射。"""
from __future__ import annotations

from copy import deepcopy
import time
from typing import Any, Callable, Optional

from core.query_field_defaults import _default_query_fields_all
def _map_date_trigger(draft_params: dict, meta: Optional[dict] = None,
                      app_id: str = "",
                      filter_builder: Callable[..., dict] | None = None) -> dict:
    """DateTrigger 按日期字段触发 → 真实 data.

    平台数据实证 (价格库自动失效, 9 个 DateTrigger 样本):
      data keys: triggerDateTime/beforeOrAfterNum/remindEndDataVal/queryFields/
                 timeField/remindRunDayVal/repeatType/dateField/operator/
                 remindEndData/remindRunDayUnit/numConstOrField/dataFilter/
                 triggerDateType/remindFinishWay/timeConstOrField/
                 beforeOrAfterGrade/remindRunDay/id/dataSource/endTimesType/
                 executeMethod/applicationName
      dateField: {optionType, compType, showName, objId, name, id, text, formatType, type}
      dataSource: {isPhysical, groupId, id, text, type, physical}
    """
    result: dict[str, Any] = deepcopy(_DATE_TRIGGER_DEFAULTS)
    # 不要生成 data.id:
    # DateTriggerComponent.save() 里 data.getId() 非 null 走更新分支,
    # selectOne(initSelectOne(data.getId())) 查不到旧记录 → NPE 500 "组件内部异常".
    # 新组件插入必须不带 id (SimpleScheduler data 无 id 同理).
    # result["id"] = str(gen_id())  ← 已删除

    # dataSource (真实 DateTrigger 结构 + appId 兼容后端 setAppId)
    ds = draft_params.get("dataSource") or {}
    ds_id = str(ds.get("id") or ds.get("tableId") or ds.get("sourceId", "")) if isinstance(ds, dict) else ""
    ds_group = str(ds.get("groupId", ds.get("appId", "-98"))) if isinstance(ds, dict) else "-98"
    if isinstance(ds, dict):
        # 真实 dataSource 是 6 键 {isPhysical,groupId,id,text,type,physical}, 无 appId
        #
        result["dataSource"] = {
            "isPhysical": True,
            "physical": True,
            "groupId": ds_group,
            "id": ds_id,
            "text": str(ds.get("text") or ds.get("name") or ""),
            "type": str(ds.get("type", "FORM")),
        }

    # dateField (formatType 必填: 4=日期 5=日期时间 6=时间; 平台结构 formatType='4')
    df = draft_params.get("dateField") or {}
    if isinstance(df, dict):
        df_id = str(df.get("id", df.get("name", "")))
        df_format = str(df.get("formatType", df.get("type", "Date")))
        if df_format in ("Date", "日期"):
            df_format = "4"
        elif df_format in ("DateTime", "日期时间"):
            df_format = "5"
        elif df_format in ("Time", "时间"):
            df_format = "6"
        result["dateField"] = {
            "optionType": str(df.get("optionType", "")),
            "compType": str(df.get("compType", "DateComponent")),
            # 平台结构 showName/name 是字段 id 字符串 (如 '<字段id>'),
            # 不是中文名 (服务端保存时剥离中文, 用 id)
            "showName": df_id,
            "objId": str(df.get("objId", ds_id)),
            "name": df_id,
            "id": df_id,
            "text": str(df.get("text") or df.get("label") or ""),
            "formatType": df_format,
            "type": str(df.get("type", "Date")),
        }
    else:
        result["dateField"] = {"optionType": "", "compType": "DateComponent",
                               "showName": "", "objId": "", "name": "", "id": "",
                               "text": "", "formatType": "4", "type": "Date"}

    if draft_params.get("triggerDateTime"):
        result["triggerDateTime"] = str(draft_params["triggerDateTime"])
    if draft_params.get("repeatType") is not None:
        result["repeatType"] = int(draft_params["repeatType"])
    # triggerDateType(0准时/1提前/2延迟/3当天)/beforeOrAfterNum(提前/延迟天数)/
    # beforeOrAfterGrade(0天/4小时/5分钟) 被丢弃 → plan 写"提前1天"默认变"当天".
    # 平台数据: triggerDateType 字符串 '1'/'2'/'3', beforeOrAfterGrade 混用 str '0' 与 int 4/5.
    if draft_params.get("triggerDateType") is not None:
        result["triggerDateType"] = str(draft_params["triggerDateType"])
    if draft_params.get("beforeOrAfterNum") is not None:
        result["beforeOrAfterNum"] = int(draft_params["beforeOrAfterNum"])
    if draft_params.get("beforeOrAfterGrade") is not None:
        result["beforeOrAfterGrade"] = str(draft_params["beforeOrAfterGrade"])
    # 日期触发的值来源与结束策略必须按前端字段原样保留，不能退回 defaultData。
    for key in ("numConstOrField", "numField", "timeConstOrField", "timeField",
                "remindFinishWay", "remindEndDataVal", "remindRunDayVal",
                "remindRunDayUnit", "executeMethod"):
        value = draft_params.get(key)
        if value not in (None, "", []):
            result[key] = deepcopy(value)

    # DateTrigger 前端同样使用 ConditionSet；旧实现只保留空 dataFilter，导致
    # plan 中配置了筛选条件也会被静默丢弃。
    date_filter = draft_params.get("filter") or draft_params.get("filterCondition")
    if date_filter:
        if filter_builder is None:
            raise ValueError("DateTrigger 的筛选条件需要 filter_builder")
        result["dataFilter"] = filter_builder(
            result, date_filter, meta, app_id, component_type="DateTrigger")

    # lastTriggerTime: 平台结构必有 (毫秒时间戳字符串), 缺失可能触发 500
    if not result.get("lastTriggerTime"):
        result["lastTriggerTime"] = str(int(time.time() * 1000))

    # queryFields: 未指定 → 默认全选目标表单字段 ; 缓存缺失回退数据ID
    _qf = draft_params.get("queryFields")
    if _qf:
        result["queryFields"] = []
        for f in _qf if isinstance(_qf, list) else []:
            if isinstance(f, dict) and f.get("id"):
                result["queryFields"].append({
                    "formId": str(f.get("formId", ds_id)),
                    "parseMark": bool(f.get("parseMark", False)),
                    "id": str(f["id"]),
                    "content": str(f.get("content", f.get("id"))),
                })
    else:
        result["queryFields"] = _default_query_fields_all(ds_id)

    # 前端的“操作人”是必填资源浏览器；必须把语义计划中的当前租户人员
    # 原对象转换为 DateTrigger DTO 的人员数组，不能让默认空数组静默通过。
    operator = draft_params.get("operator")
    if isinstance(operator, dict) and operator.get("id"):
        result["operator"] = [{
            "id": str(operator["id"]),
            "name": str(operator.get("name") or operator.get("text") or ""),
        }]
    elif isinstance(operator, list):
        result["operator"] = [
            {"id": str(item["id"]), "name": str(item.get("name") or item.get("text") or "")}
            for item in operator if isinstance(item, dict) and item.get("id")
        ]
    result["applicationName"] = str((draft_params.get("dataSource") or {}).get("text", "")) if isinstance(draft_params.get("dataSource"), dict) else ""
    if app_id:
        result["currentApplication"] = app_id
        result["applicationId"] = app_id
    return result

_DATE_TRIGGER_DEFAULTS = {
    "triggerDateTime": "00:00",
    "beforeOrAfterNum": 1,
    "remindEndDataVal": "",
    "timeField": "",
    "remindRunDayVal": "",
    "repeatType": 1,
    # operator 是人员数组 (List<Map>), 空必须用 [] 不是 "" (否则反序列化失败)
    "operator": [],
    "remindEndData": "",
    "remindRunDayUnit": "",
    "numConstOrField": "numConst",
    "dataFilter": {"isNewFilter": True, "isParent": True, "datas": [], "parentNode": "", "relationship": "1", "key": ""},
    # 字段类型对齐平台数据:
    #   triggerDateType 是字符串 '1'/'2'/'3' (int 会反序列化异常)
    #   beforeOrAfterGrade 是字符串 '0' 或 int 4/5 (混合, 默认 '0')
    #   executeMethod 真实 '1' (2 条) 或缺失 (7 条)
    #   remindFinishWay/remindRunDayUnit 几乎全 '' (默认 notEnd/day 是错的)
    "triggerDateType": "3",
    "remindFinishWay": "",
    "timeConstOrField": "timeConst",
    "beforeOrAfterGrade": "0",
    "remindRunDay": "",
    "endTimesType": "fix",
    "executeMethod": "1",
}
