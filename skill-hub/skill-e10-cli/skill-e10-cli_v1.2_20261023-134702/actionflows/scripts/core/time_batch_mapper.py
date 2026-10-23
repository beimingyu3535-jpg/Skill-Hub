"""定时批量触发器的真实 DTO 映射。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Optional

from core.query_field_defaults import _default_query_fields_all

def _map_time_batch_trigger(draft_params: dict, meta: Optional[dict] = None,
                            app_id: str = "", filter_builder: Callable[..., dict] | None = None) -> dict:
    """TimeBatchTrigger 定时批量触发 → 真实 data.

    平台数据实证 (8 个 TimeBatchTrigger 样本, 询价单批量任务/物料成本分析):
      data keys: sourceId/tableNames/radioVal/groupId/schedulerId/hourDb/cycle/
                 filterInput/operator/lastWeekDb/rate/dayDb/startTime/day/weekDb/
                 operatorId/creator/atWeekDetailDb/queryFields/filterText/monthDb/
                 typeFrom/cycleNum/atWeekDb/dataSource/applicationName/cornString/
                 endTime/openRetryFlag/appId/month/physical/openRetry
      dataSource: {sourceId, isPhysical, groupId, id, text, type, physical}
      rate: 真实 2(按小时)/5(按月)/6(每天?)/其他; radioVal: cycle/day/week
      新组件插入不带 data.id (save() 里 data.getId() null 走新增分支)
    """
    result: dict[str, Any] = deepcopy(_TIME_BATCH_DEFAULTS)

    # dataSource → sourceId/tableNames/groupId/typeFrom/physical + dataSource 对象
    ds = draft_params.get("dataSource") or {}
    ds_id = str(ds.get("id") or ds.get("tableId") or ds.get("sourceId", "")) if isinstance(ds, dict) else ""
    ds_group = str(ds.get("groupId", ds.get("appId", "-98"))) if isinstance(ds, dict) else "-98"
    if isinstance(ds, dict):
        result["dataSource"] = {
            "sourceId": ds_id,
            "isPhysical": True,
            "groupId": ds_group,
            "id": ds_id,
            "text": str(ds.get("text") or ds.get("name") or ""),
            "type": str(ds.get("type", "FORM")),
            "physical": True,
        }
        result["sourceId"] = ds_id
        result["tableNames"] = str(ds.get("text") or ds.get("name") or "")
        result["groupId"] = ds_group
        result["typeFrom"] = str(ds.get("type", "FORM"))
        result["physical"] = True
        result["appId"] = ds_group

    # rate 映射: plan 1=每天 2=每周 3=每月 4=一次性 5=Cron
    # 真实 radioVal: cycle/day/week; cycleNum 与 cycle 同值
    plan_rate = str(draft_params.get("rate", "1"))
    cycle = draft_params.get("cycle")
    day = draft_params.get("day") or []
    month = draft_params.get("month") or []
    hour = draft_params.get("hour") or []
    cyc = int(cycle) if str(cycle).isdigit() else 1

    if plan_rate == "1":      # 每天
        result["rate"] = 6
        result["radioVal"] = "cycle"
        result["cycle"] = cyc
    elif plan_rate == "2":    # 每周
        result["rate"] = 5
        if day:
            result["radioVal"] = "week"
            result["week"] = [str(d) for d in day]
        else:
            result["radioVal"] = "cycle"
            result["cycle"] = cyc
    elif plan_rate == "3":    # 每月
        result["rate"] = 5
        if day:
            result["radioVal"] = "day"
            result["day"] = [str(d) for d in day]
        result["month"] = [str(m) for m in (month or range(1, 13))]
        result["radioVal"] = result.get("radioVal", "day")
    elif plan_rate == "4":    # 一次性
        result["rate"] = 1
        result["radioVal"] = "cycle"
        result["cycle"] = cyc
    elif plan_rate == "5":    # Cron
        result["rate"] = 6
        result["cornString"] = draft_params.get("cornString", "")
        result["radioVal"] = "cycle"

    result["cycleNum"] = result.get("cycle", cyc)

    # hour → hourDb (逗号分隔字符串; 平台结构多为空, schedulerId 由后端生成)
    if hour:
        result["hour"] = [str(h) for h in hour]

    if draft_params.get("startTime"):
        result["startTime"] = str(draft_params["startTime"])
    if draft_params.get("endTime"):
        result["endTime"] = str(draft_params["endTime"])
    # 前端的周/月细化、排序与重试开关，旧实现从 Draft 接收后静默丢失。
    for key in ("radioVal", "week", "atWeek", "atWeekDetail", "lastWeek", "orderFields"):
        value = draft_params.get(key)
        if value not in (None, "", []):
            result[key] = deepcopy(value)
    if draft_params.get("openRetryFlag") is not None:
        result["openRetryFlag"] = bool(draft_params["openRetryFlag"])
        result["openRetry"] = bool(draft_params["openRetryFlag"])

    # filterInput: 复用 _build_filter_input (真实结构 isNewFilter/isParent/datas/...)
    fc = draft_params.get("filterCondition")
    if isinstance(fc, dict) and fc:
        if filter_builder is None:
            raise ValueError("TimeBatchTrigger.filterCondition requires a filter builder")
        result["filterInput"] = filter_builder(result, fc, meta, app_id,
                                               component_type="TimeBatchTrigger")

    # operator: 真实是人员数组 [{id, name}]
    op = draft_params.get("operator")
    if isinstance(op, dict) and op.get("id"):
        result["operator"] = [{"id": str(op["id"]), "name": str(op.get("name", ""))}]

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

    result["applicationName"] = str((draft_params.get("dataSource") or {}).get("text", "")) if isinstance(draft_params.get("dataSource"), dict) else ""
    if app_id:
        result["currentApplication"] = app_id
        result["applicationId"] = app_id
    return result

_TIME_BATCH_DEFAULTS = {
    "radioVal": "cycle",
    "rate": 6,
    "cycle": 1,
    "hourDb": "",
    "dayDb": "",
    "weekDb": "",
    "monthDb": "",
    "atWeekDb": "",
    "atWeekDetailDb": "",
    "lastWeekDb": "",
    "cornString": "",
    "endTime": "",
    "startTime": "",
    "openRetry": False,
    "openRetryFlag": False,
    "physical": True,
    "typeFrom": "FORM",
    "filterInput": {"isNewFilter": True, "isParent": True, "datas": [], "parentNode": "", "relationship": "1", "key": ""},
    "operator": [],
    "queryFields": [],
    "filterText": "",
}
