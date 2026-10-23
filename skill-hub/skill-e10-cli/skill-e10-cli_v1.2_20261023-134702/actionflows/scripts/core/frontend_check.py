"""前端检查 (frontend_check) — 完全复刻设计器前端各组件 checkData 的本地校验。

来源: weapp-esb-develop/src/components/efdesigner/main/components/*/index.tsx 中
每个组件注册的 `checkData` 函数 (base/index.tsx:86 通过 pushCheckData 注册,
store.ts:2211 validateCheckData 汇总执行, 保存前 `onCheckDataByFront` 校验)。

规则逐条对照前端源码翻译:
- SimpleScheduler / TimeBatchTrigger: 定时频率必填 + 到期≥开始 + 频率细化字段条件必填
- DateTrigger: 每天重复的结束方式字段必填 + 提前/延迟整数必填 + 时间字段必填
- ApproveTrigger: multiApprove 模式必须有触发设置
- ActionEbUpdate: fieldUpdate 模式必须设置更新字段条件
- EnquiryForm: 排序字段每项必填

与后端 flow/design/check (结构完整性) 互补: 本模块校验的是**前端条件规则**,
即设计器画布上保存前会拦的错误, 承担本地必填校验。
"""

from __future__ import annotations

from typing import Any

from core.assignment_contracts import audit_dynamic_assignments

# ── 工具 ──────────────────────────────────────────────────────────────────

def _is_empty(value: Any) -> bool:
    """与前端 isEmpty 语义对齐: None/''/[]/{}/0 视为空。"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    if isinstance(value, (int, float)) and value == 0:
        return True
    return False

def _fmt_time(value: Any) -> str:
    """时间字符串归一化, 便于比较。"""
    if value is None:
        return ""
    return str(value).strip().replace("T", " ")

# ── SimpleScheduler / TimeBatchTrigger ────────────────────────────────────

def _check_scheduler(data: dict, comp_label: str) -> list[str]:
    """SimpleScheduler / TimeBatchTrigger 通用规则。

    前端源码 (simple-scheduler/index.tsx + timeBatchTrigger/index.tsx checkData):
    - rate 必填: "定时频率需要必填"
    - rate>1 且有 startTime/endTime 时, endTime <= startTime: "到期时间不得小于开始时间"
    - rate==2(按小时): radioVal==cycle→cycle必填, radioVal==hour→hour必填
    - rate==3(按日):   radioVal==cycle→cycle必填
    - rate==4(按周):   radioVal==cycle→cycle必填, radioVal==week→week必填
    - rate==5(按月):   radioVal==day→day必填, radioVal==atWeek→atWeek+atWeekDetail必填,
                       radioVal==lastWeek→lastWeek必填
    """
    errors: list[str] = []
    rate = data.get("rate")
    if _is_empty(rate):
        return [f"{comp_label}: 定时频率需要必填 (rate)"]

    # 到期时间不得小于开始时间 (rate>1 且两者都有值才比较)
    start_time = data.get("startTime")
    end_time = data.get("endTime")
    try:
        rate_num = int(str(rate))
    except (TypeError, ValueError):
        rate_num = 0
    if rate_num > 1 and not _is_empty(start_time) and not _is_empty(end_time):
        st, et = _fmt_time(start_time), _fmt_time(end_time)
        if st and et and et <= st:
            errors.append(f"{comp_label}: 到期时间不得小于开始时间 (startTime={st}, endTime={et})")

    radio_val = data.get("radioVal")
    if rate_num == 2:  # 按小时
        if radio_val == "cycle" and _is_empty(data.get("cycle")):
            errors.append(f"{comp_label}: 每多少小时需必填 (cycle)")
        elif radio_val == "hour" and _is_empty(data.get("hour")):
            errors.append(f"{comp_label}: 指定时需必填 (hour)")
    elif rate_num == 3:  # 按日
        if radio_val == "cycle" and _is_empty(data.get("cycle")):
            errors.append(f"{comp_label}: 每多少日需必填 (cycle)")
    elif rate_num == 4:  # 按周
        if radio_val == "cycle" and _is_empty(data.get("cycle")):
            errors.append(f"{comp_label}: 每多少周需必填 (cycle)")
        elif radio_val == "week" and _is_empty(data.get("week")):
            errors.append(f"{comp_label}: 指定具体星期需必填 (week)")
    elif rate_num == 5:  # 按月
        if radio_val == "day" and _is_empty(data.get("day")):
            errors.append(f"{comp_label}: 指定具体日期必填 (day)")
        elif radio_val == "atWeek":
            if _is_empty(data.get("atWeek")):
                errors.append(f"{comp_label}: 指定具体周需必填 (atWeek)")
            if _is_empty(data.get("atWeekDetail")):
                errors.append(f"{comp_label}: 指定具体周的星期需必填 (atWeekDetail)")
        elif radio_val == "lastWeek" and _is_empty(data.get("lastWeek")):
            errors.append(f"{comp_label}: 最后一周需必填 (lastWeek)")
    if radio_val in {"hour", "week", "day", "atWeek", "lastWeek"} and rate_num not in {2, 4, 5}:
        errors.append(f"{comp_label}: 调度细分方式与频率不匹配 (rate={rate}, radioVal={radio_val})")
    return errors

# ── DateTrigger ───────────────────────────────────────────────────────────

def _check_date_trigger(data: dict, comp_label: str) -> list[str]:
    """DateTrigger 规则。

    前端源码 (date-trigger/index.tsx checkData):
    - repeatType==2(每天): remindFinishWay==endDate→remindEndDataVal必填;
                            remindFinishWay==runDate→remindRunDayVal必填
    - triggerDateType==1/2(提前/延迟): numConstOrField==numField→numField必填
    - 日期字段下 (triggerDateType in 0/1/2/3):
        timeConstOrField==timeConst→triggerDateTime必填;
        timeConstOrField==timeField→timeField必填
    - 非日期字段 (else 分支):
        triggerDateType==0 且 timeConstOrField==currentDateFix→triggerDateTime必填;
        triggerDateType==1/2 且 timeConstOrField==currentDateFix→triggerDateTime必填
    """
    errors: list[str] = []
    repeat_type = str(data.get("repeatType", ""))
    if repeat_type == "2":  # 每天
        finish_way = data.get("remindFinishWay")
        if finish_way == "endDate" and _is_empty(data.get("remindEndDataVal")):
            errors.append(f"{comp_label}: 触发结束日期需必填！ (remindEndDataVal)")
        if finish_way == "runDate" and _is_empty(data.get("remindRunDayVal")):
            errors.append(f"{comp_label}: 触发持续时间需必填！ (remindRunDayVal)")

    trigger_date_type = str(data.get("triggerDateType", ""))
    if trigger_date_type in ("1", "2"):
        if data.get("numConstOrField") == "numField" and _is_empty(data.get("numField")):
            errors.append(f"{comp_label}: 整数字段需必填！ (numField)")
        if data.get("numConstOrField", "numConst") == "numConst" and _is_empty(data.get("beforeOrAfterNum")):
            errors.append(f"{comp_label}: 提前/延迟数量需必填！ (beforeOrAfterNum)")

    time_const = data.get("timeConstOrField")
    if trigger_date_type in ("0", "1", "2", "3"):
        if time_const == "timeConst" and _is_empty(data.get("triggerDateTime")):
            errors.append(f"{comp_label}: 触发时间的固定时间需必填！ (triggerDateTime)")
        if time_const == "timeField" and _is_empty(data.get("timeField")):
                errors.append(f"{comp_label}: 触发时间的选择字段需必填！ (timeField)")
    else:
        if time_const == "currentDateFix" and _is_empty(data.get("triggerDateTime")):
            if trigger_date_type == "0":
                errors.append(f"{comp_label}: 触发时间的当天需必填！ (triggerDateTime)")
            elif trigger_date_type in ("1", "2"):
                errors.append(f"{comp_label}: 触发时间的固定时间需必填！ (triggerDateTime)")
    if _is_empty(data.get("operator")):
        errors.append(f"{comp_label}: 操作人需必填！ (operator)")
    return errors

# ── ApproveTrigger ────────────────────────────────────────────────────────

def _check_approve_trigger(data: dict, comp_label: str) -> list[str]:
    """ApproveTrigger 规则。

    前端源码 (Approve/ApproveTrigger/index.tsx checkData):
    - triggerType==multiApprove(多流程审批) 时 approveList 必须非空:
      "触发设置未添加" / "选择工作流-此项必填"
    """
    if data.get("triggerType") == "multiApprove" and _is_empty(data.get("approveList")):
        return [f"{comp_label}: 触发设置未添加 (approveList, multiApprove 模式必填)"]
    return []

# ── ActionEbUpdate ────────────────────────────────────────────────────────

def _check_action_eb_update(data: dict, comp_label: str) -> list[str]:
    """ActionEbUpdate 规则。

    前端源码 (ActionEbUpdate/index.tsx checkData):
    - opType==fieldUpdate 时 updateFieldCondition.updateField 必须非空:
      "条件字段设置-此项必填"
    """
    op_type = data.get("opType")
    if op_type not in {"id", "updateData", "fieldUpdate"}:
        return [f"{comp_label}: 更新方式无效 (opType={op_type})"]
    if op_type == "fieldUpdate":
        cond = data.get("updateFieldCondition") or {}
        if _is_empty(cond) or _is_empty(cond.get("updateField")):
            return [f"{comp_label}: 条件字段设置-此项必填 (updateFieldCondition.updateField)"]
        if not all(isinstance(item, dict) and item.get("fieldKey") and item.get("assign")
                   for item in cond.get("updateField", [])):
            return [f"{comp_label}: 条件字段设置存在不完整行 (每行需要 fieldKey 和 assign)"]
        if data.get("updatePolicy") not in {"ALL", "FIRST", "LAST", "ZERO", "EXCEPTION"}:
            return [f"{comp_label}: 更新策略无效 (updatePolicy)"]
    return []

# ── EnquiryForm ───────────────────────────────────────────────────────────

def _check_enquiry_form(data: dict, comp_label: str) -> list[str]:
    """EnquiryForm 规则。

    前端源码 (enquiry-form/index.tsx checkData):
    - orderFields 每项 field 必须非空: "排序字段-此项必填"
    """
    errors: list[str] = []
    for item in data.get("orderFields") or []:
        if _is_empty(item.get("field")):
            errors.append(f"{comp_label}: 排序字段-此项必填 (orderFields[].field)")
    return errors

# ── 组件 → 检查函数映射 ───────────────────────────────────────────────────

_CHECKS: dict[str, Any] = {
    "SimpleScheduler": _check_scheduler,
    "TimeBatchTrigger": _check_scheduler,
    "DateTrigger": _check_date_trigger,
    "ApproveTrigger": _check_approve_trigger,
    "ActionEbUpdate": _check_action_eb_update,
    "EnquiryForm": _check_enquiry_form,
}

# ── 前端必填表 (items required + 平台数据校准) ─────────────────────────────
# 用平台数据 (采购动作流配置详情数据.json, 1068 条) 出现率校准:
#   - 出现率 ~100% 且 items required → 硬必填 (缺失报错)
#   - items required 但真实出现率低 (如 classification 0/71) → 条件隐藏字段, 不检查
# 动态必填 (setItemProps 按 opType 切换) 单独用 _check_dynamic_required 处理。

_REQUIRED_STATIC: dict[str, list[str]] = {
    # 前端 items required:true 且平台数据出现率 ≥ 90% 的字段
    "ActionEbAdd": ["targetForm", "person", "opType", "setting"],
    # targetForm 84%/195, person 100%, opType 100%, setting 99%
    "ActionEbUpdate": ["targetForm", "person", "opType", "setting"],
    "ActionEbDelete": ["targetForm", "person", "filterInput"],  # 全 100%
    "EnquiryForm": ["dataSource", "person", "opType", "filterInput", "queryFields"],
    # queryFields 93%, 其余 ~100%
    "ApproveCreate": ["workflowPath", "operator", "requestName"],  # 新建流程三项必填
    "MeetingCreate": ["operators", "type", "setting"],  # 前端 items required
    # 平台已保存成功的 SendMessage 节点没有 channelSetting；它是前端渠道配置 UI
    # 的可选原生状态，不是执行 DTO 的硬必填。
    "TimeBatchTrigger": ["rate", "dataSource", "filterInput", "queryFields", "operator"],  # 前端 items
    "ScheduleCreate": ["creatorUser", "managerFormulaId", "title", "startTime", "endTime", "secret"],
    # ApproveTrigger 的流程绑定随 triggerType 切换：单流程使用
    # workflowPath/singleApproveConfigs，多流程使用 approveList；由
    # _check_approve_trigger 按实际模式校验，不能在此静态表中一概要求。
    "ApproveTrigger": ["triggerType"],
    # SimpleScheduler/DateTrigger: 前端无 items required, 必填全在 checkData (已复刻)
}

# SendMessage: msgTitle/msgTitlev 与 msgContent/msgContentv 是"或"关系
# (前端 isCompatiblev: msgTitle 和 msgContent 都为空时用 v 字段)
_SENDMESSAGE_OR_GROUPS = [
    ("msgTitle", "msgTitlev"),
    ("msgContent", "msgContentv"),
]

def _check_dynamic_required(ctype: str, data: dict, comp_label: str) -> list[str]:
    """动态必填 (前端 setItemProps 按 opType 切换 required)。"""
    errors: list[str] = []
    if ctype == "ActionEbUpdate":
        op_type = data.get("opType")
        if op_type == "id" and _is_empty(data.get("updateId")):
            errors.append(f"{comp_label}: 更新条件(数据ID)-此项必填 (updateId, opType=id)")
        elif op_type == "updateData" and _is_empty(data.get("filterInput")):
            errors.append(f"{comp_label}: 更新条件-此项必填 (filterInput, opType=updateData)")
        elif op_type == "fieldUpdate" and _is_empty(data.get("updateFieldCondition")):
            errors.append(f"{comp_label}: 条件字段设置-此项必填 (updateFieldCondition, opType=fieldUpdate)")
    elif ctype == "SendMessage":
        for a, b in _SENDMESSAGE_OR_GROUPS:
            if _is_empty(data.get(a)) and _is_empty(data.get(b)):
                errors.append(f"{comp_label}: {a}/{b} 至少一个必填 (前端 isCompatiblev 二选一)")
    elif ctype == "MeetingCreate":
        # 不能只检查外层 setting 非空：meeting-fields 返回的基础表单必填项也必须写入。
        setting = data.get("setting") if isinstance(data.get("setting"), dict) else {}
        for field in ("name", "secretLevel", "caller", "beginDatetime", "endDatetime"):
            if _is_empty(setting.get(field)):
                errors.append(f"{comp_label}: 会议信息.{field}-此项必填 (meeting-fields required)")
    elif ctype == "EventFormData":
        if "fieldDataChange" in (data.get("triggerTimes") or []) and _is_empty(data.get("changeFields")):
            errors.append(f"{comp_label}: changeFields-此项必填 (triggerTimes=fieldDataChange)")
        target_form = data.get("targetForm") if isinstance(data.get("targetForm"), dict) else {}
        if "fieldDataChange" in (data.get("triggerTimes") or []) and not target_form.get("isPhysical"):
            errors.append(f"{comp_label}: e-builder 表单不支持 fieldDataChange；请使用 afterUpdate。")
    elif ctype == "ApproveTrigger" and data.get("triggerType") != "multiApprove":
        if _is_empty(data.get("workflowPath")):
            errors.append(f"{comp_label}: workflowPath-此项必填 (singleApprove 模式)")
        if _is_empty(data.get("singleApproveConfigs")):
            errors.append(f"{comp_label}: singleApproveConfigs-此项必填 (singleApprove 模式)")
    return errors

def _check_required(ctype: str, data: dict, comp_label: str,
                    warnings: list[str]) -> list[str]:
    """静态必填表检查: items required 且平台数据出现率高 → 缺失报错。"""
    errors: list[str] = []
    for field in _REQUIRED_STATIC.get(ctype, []):
        if _is_empty(data.get(field)):
            errors.append(f"{comp_label}: {field}-此项必填 (前端 items required)")
    return errors

# ── 对外入口 ──────────────────────────────────────────────────────────────

def frontend_check(design: dict) -> tuple[list[str], list[str]]:
    """对生成的设计执行前端检查 (复刻设计器前端 checkData + items required)。

    design: convert_draft_to_real 输出的真实设计 (含 event + actions)。

    检查层次 (与设计器保存前一致):
    1. 各组件 checkData 条件规则 (定时频率/时间比较/分支条件等)
    2. items required 静态必填表 (平台数据校准, 排除条件隐藏字段)
    3. 动态必填 (ActionEbUpdate opType 切换 / SendMessage v 字段二选一)

    返回 (errors, warnings):
    - errors: 与设计器保存前拦截一致的错误, 非空则不应保存
    - warnings: 软提示 (如依赖环境的密级校验), 不阻断保存
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 事件节点 (触发组件)
    event = design.get("event") or {}
    if isinstance(event, dict):
        ev_type = event.get("type")
        ev_data = event.get("data") or {}
        check_fn = _CHECKS.get(str(ev_type))
        if check_fn and isinstance(ev_data, dict):
            errors.extend(check_fn(ev_data, f"触发节点[{ev_type}]"))
        if isinstance(ev_data, dict):
            errors.extend(_check_required(str(ev_type), ev_data, f"触发节点[{ev_type}]", warnings))
            errors.extend(_check_dynamic_required(str(ev_type), ev_data, f"触发节点[{ev_type}]"))

    # 动作节点
    for action in design.get("actions") or []:
        if not isinstance(action, dict):
            continue
        act_type = action.get("type")
        act_data = action.get("data") or {}
        if not isinstance(act_data, dict):
            continue
        check_fn = _CHECKS.get(str(act_type))
        if check_fn:
            errors.extend(check_fn(act_data, f"动作[{act_type}]"))
        errors.extend(_check_required(str(act_type), act_data, f"动作[{act_type}]", warnings))
        errors.extend(_check_dynamic_required(str(act_type), act_data, f"动作[{act_type}]"))

    assignment_errors, assignment_warnings = audit_dynamic_assignments(design)
    errors.extend(assignment_errors)
    warnings.extend(assignment_warnings)

    return errors, warnings
