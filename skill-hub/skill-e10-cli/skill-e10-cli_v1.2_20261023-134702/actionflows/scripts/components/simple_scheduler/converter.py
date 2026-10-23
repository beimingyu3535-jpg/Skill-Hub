"""SimpleScheduler 的专用平台 DTO 转换。"""
from __future__ import annotations

def CONVERTER(draft_params: dict, **_kwargs) -> dict:
    """将简化的定时语义转换为平台 rate/radioVal 结构。

    plan rate：1=每天、2=每周、3=每月、4=一次性、5=Cron；平台 rate：
    1=一次、3=按日、4=按周、5=按月、6=Cron。
    """
    plan_rate = str(draft_params.get("rate", "1"))
    cycle = draft_params.get("cycle")
    day = draft_params.get("day") or []
    start_time = draft_params.get("startTime", "")
    end_time = draft_params.get("endTime", "")
    corn = draft_params.get("cornString", "")

    result: dict = {"openRetry": False}
    cyc = int(cycle) if str(cycle).isdigit() else 1

    if plan_rate == "1":
        result.update({"rate": "3", "radioVal": "cycle", "cycle": cyc})
    elif plan_rate == "2":
        result["rate"] = "4"
        if day:
            result.update({"radioVal": "week", "week": [str(value) for value in day]})
        else:
            result.update({"radioVal": "cycle", "cycle": cyc})
    elif plan_rate == "3":
        result["rate"] = "5"
        if day:
            result.update({
                "radioVal": "day",
                "day": [str(value) for value in day],
                "month": [str(month) for month in range(1, 13)],
            })
        else:
            result.update({"radioVal": "cycle", "cycle": cyc})
    elif plan_rate == "4":
        result["rate"] = "1"
    elif plan_rate == "5":
        result["rate"] = "6"
        if corn:
            result["cornString"] = corn

    if start_time:
        result["startTime"] = start_time
    if end_time:
        result["endTime"] = end_time
    return result
