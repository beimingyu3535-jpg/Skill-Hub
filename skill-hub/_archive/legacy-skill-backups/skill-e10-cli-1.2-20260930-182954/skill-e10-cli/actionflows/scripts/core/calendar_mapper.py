"""会议和日程组件的真实 DTO 映射。"""
from __future__ import annotations

from typing import Any, Optional

from core.formula_service import _make_config_str, build_person_formula, formula_container_string, formula_fixed, formula_fixed_for_assign_switch

def _map_meeting_create(draft_params: dict, meta: Optional[dict] = None,
                        app_id: str = "") -> dict:
    """MeetingCreate 新建会议 → 真实 data.

    平台契约 (二分法定位 500 根因):
      - setting 必须是 Map<字段key, FormulaBean> (不是表单结构 {opType,main,detail}),
        后端 MeetingPendingCreateEntity.setting = Map<String, FormulaBean>,
        saveCommonForm(null, settingMap) 直接消费该 Map; 传表单结构会 500 "组件内部异常".
      - type 是 OperateTypeEnum 枚举: 'SUBMIT'(正常) / 'SUBMIT_APPROVE'(待审批)
        (前端 getMettingSelectData 接口返回, 验证可用)
      - moduleType 是 EntityType 枚举: 'workflow' (前端 selectModuleData 只有这一项)
      - operators 是 FormulaBean (公式 bean, 与 ApproveCreate.operator 同构)
      - 新组件插入不带 data.id (save() 里 data.getId() null 走新增分支)
    """
    result: dict[str, Any] = {
        "ebActionId": "-1",
        "moduleType": "workflow",
    }

    # MeetingCreate 使用的 SetForm 直接把 FormulaBean 交给 AssignSwitch。该前端
    # 只读取 ``formula.config.switchType``（对象），不是后端快照中的 config JSON 字符串。
    # 因此此组件的 setting/flag 固定值必须保留 config 对象；不能复用其它组件的
    # config-string 序列化形态，否则 UI 会默认回退到“动态赋值”。
    def meeting_formula_fixed(value: Any, field_type: str = "string") -> dict:
        bean = formula_fixed(value, field_type=field_type)
        bean["fieldType"] = field_type
        bean["config"] = {
            "originValue": value,
            "switchType": "fixvalue",
            "formulaVersion": "V1",
        }
        return bean

    # SetForm → AssignSwitch 对 BROWSER/UPLOAD 字段的固定值结构不是普通文本：
    # value/name = 首个资源 id，config.originValue = 资源对象数组。
    # 若把 {id,name} 直接 formula_fixed，会把对象 stringify，界面无法回显“召集人”。
    _meeting_resource_fields = {
        "mtType", "caller", "contacter", "address", "hrmMembers", "orgMembers",
        "crmMembers", "mtAccessorys",
    }

    def meeting_fixed(field_key: str, value: Any) -> dict:
        if field_key not in _meeting_resource_fields:
            return meeting_formula_fixed(value)
        items = value if isinstance(value, list) else [value]
        if not items or not all(isinstance(item, dict) for item in items):
            raise ValueError(f"MeetingCreate.{field_key} 必须传平台选择器返回的对象或对象数组，不能传纯文本")
        first = items[0]
        resource_id = first.get("id") or first.get("fileid")
        if resource_id in (None, ""):
            raise ValueError(f"MeetingCreate.{field_key} 缺少资源 id/fileid")
        result_formula = meeting_formula_fixed(str(resource_id))
        display_name = str(first.get("name") or first.get("content") or resource_id)
        # 会议 SetForm 的选择器标签读取 FormulaBean.name；value 才是实际资源 ID。
        # 将 name 写成 ID 虽能暂存，却会在 UI 中显示一串数字而非人员名称。
        result_formula["name"] = display_name
        result_formula["value"] = str(resource_id)
        result_formula["config"] = {
            "originValue": items,
            "switchType": "fixvalue",
            "formulaVersion": "V1",
        }
        return result_formula

    # operators: 会议创建人公式 bean
    op = draft_params.get("operators")
    if isinstance(op, dict):
        result["operators"] = build_person_formula(op, meta, app_id)

    # moduleType (EntityType 枚举, 前端仅 workflow)
    if draft_params.get("moduleType"):
        result["moduleType"] = str(draft_params["moduleType"])

    # type (OperateTypeEnum 枚举, 前端 getMettingSelectData: SUBMIT/SUBMIT_APPROVE)
    mt = draft_params.get("meetingType")
    if mt:
        result["type"] = str(mt)

    # 关联标识：前端仅提供 workflow/wfcRequest Browser 固定选择；后端将其
    # FormulaBean 的求值结果写入 requestId，不能把 Browser 对象文本化。
    flag = draft_params.get("flag")
    if flag is not None:
        if not isinstance(flag, dict) or not (flag.get("id") or flag.get("fileid")):
            raise ValueError("MeetingCreate.flag 必须传 workflow/wfcRequest Browser 返回的 {id,name} 对象")
        flag_id = str(flag.get("id") or flag.get("fileid"))
        result["flag"] = meeting_formula_fixed(flag_id)
        result["flag"]["name"] = flag_id
        result["flag"]["value"] = flag_id
        result["flag"]["config"] = {
            "originValue": [flag], "switchType": "fixvalue", "formulaVersion": "V1",
        }

    # setting: Map<字段key, FormulaBean>. meeting-fields (平台组件上下文) 的 key 是事实源；
    # 命名参数只是不让调用方再猜 constants 的 key，不会替调用方补必填值。
    # 平台契约: 上下文 bean(type=3, source=0) 保存 500;
    #    固定值 bean(type=1) 保存 200. 平台 saveCommonForm 只接受固定值/已验证形态,
    #    上下文引用需真实上游 source, 暂不支持 → setting 只用固定值.
    setting_map: dict[str, Any] = {}
    constants = draft_params.get("constants") or {}
    if isinstance(constants, dict):
        for field_key, value in constants.items():
            setting_map[str(field_key)] = meeting_fixed(str(field_key), value)
    meeting_fields = draft_params.get("meetingFields") or {}
    if isinstance(meeting_fields, dict):
        for field_key, value in meeting_fields.items():
            if field_key in setting_map and setting_map[field_key].get("value") != str(value):
                raise ValueError(f"MeetingCreate 字段 '{field_key}' 同时出现在 constants 与 meetingFields，且取值不同")
            setting_map[str(field_key)] = meeting_fixed(str(field_key), value)
    for param_name, field_key in {
        "meetingTitle": "name", "secretLevel": "secretLevel",
        "caller": "caller", "contacter": "contacter",
    }.items():
        value = draft_params.get(param_name)
        if value is not None and field_key not in setting_map:
            setting_map[field_key] = meeting_fixed(field_key, value)
    if setting_map:
        result["setting"] = setting_map
    custom_form_setting = draft_params.get("customFormSetting")
    if isinstance(custom_form_setting, dict):
        result["formSetting"] = custom_form_setting

    if app_id:
        result["currentApplication"] = app_id
        result["applicationId"] = app_id
    return result

def _map_schedule_create(draft_params: dict, meta: Optional[dict] = None,
                         app_id: str = "") -> dict:
    """ScheduleCreate 创建日程 → 真实 data.

     前后端契约实证 (平台数据 0 条, 日程系统集成):
      ScheduleInfoDTO 字段全部是 FormulaBean:
        creatorUser/title/startTime/endTime/participants/content/
        meetingRoom/otherMeetingRoom/typeFormulaId/sharedFormulaId/managerFormulaId
      简单字段: allDay(bool)/placeChoice(string 1会议室 2其他)/secret(string 1上级可见 2仅自己)
      save() 里 data.getId() null 走新增 (插入不带 data.id)
    """
    meta = meta or {}
    result: dict[str, Any] = {
        "ebActionId": "-1",
        "allDay": bool(draft_params.get("allDay", False)),
    }

    def schedule_resource(value: Any, *, multiple: bool = False) -> dict:
        """按 ScheduleCreate 的 AssignSwitch Browser 固定值形态生成资源公式。"""
        values = value if isinstance(value, list) else [value]
        if not values or not all(isinstance(v, dict) and (v.get("id") or v.get("fileid")) for v in values):
            raise ValueError("ScheduleCreate 资源字段必须传平台 Browser 返回的对象或对象数组")
        if multiple:
            children = []
            for item in values:
                rid = str(item.get("id") or item.get("fileid"))
                child = formula_fixed_for_assign_switch(rid)
                child["name"] = str(item.get("name") or item.get("text") or rid)
                child["value"] = rid
                child["config"]["originValue"] = [item]
                children.append(child)
            container = formula_container_string(children, app_id=app_id)
            # ScheduleCreate 的参与人控件把 type=8 外层 FormulaBean 交给
            # AssignSwitch 判定模式；外层 config 若为字符串/assign，会被 UI
            # 误显示为“动态赋值”。固定 Browser 必须在外层也明确 fixvalue。
            container["configObject"] = {
                "paramType": "string", "switchType": "fixvalue", "formulaVersion": "V1",
            }
            container["config"] = {
                "originValue": values, "paramType": "string",
                "switchType": "fixvalue", "formulaVersion": "V1",
            }
            return container
        rid = str(values[0].get("id") or values[0].get("fileid"))
        bean = formula_fixed_for_assign_switch(rid)
        bean["name"] = str(values[0].get("name") or values[0].get("text") or rid)
        bean["value"] = rid
        bean["config"]["originValue"] = values
        return bean

    def schedule_fixed(field_name: str, value: Any, *, field_type: str = "string") -> dict:
        # 会被 str() 成文本（例如 "{'kind': 'context', ...}"）并悄悄落库，是错误的。
        if isinstance(value, dict):
            raise ValueError(
                f"ScheduleCreate.{field_name} 当前只支持固定值；"
                "流程上下文引用尚未完成平台 DTO/readBack 验证。"
            )
        return formula_fixed_for_assign_switch(str(value), field_type=field_type)

    # creatorUser: 创建人公式 (resource 型, 与 SendMessage person 同构)
    cu = draft_params.get("creatorUser")
    if isinstance(cu, dict):
        result["creatorUser"] = schedule_resource(cu)
    manager = draft_params.get("manager")
    if isinstance(manager, dict):
        result["managerFormulaId"] = schedule_resource(manager)

    # 标题/时间/内容等: 固定值 FormulaBean
    if draft_params.get("title"):
        result["title"] = schedule_fixed("title", draft_params["title"])
    if draft_params.get("startTime"):
        result["startTime"] = schedule_fixed("startTime", draft_params["startTime"], field_type="datetime")
    if draft_params.get("endTime"):
        result["endTime"] = schedule_fixed("endTime", draft_params["endTime"], field_type="datetime")
    if draft_params.get("content"):
        result["content"] = schedule_fixed("content", draft_params["content"])
    if draft_params.get("participants"):
        result["participants"] = schedule_resource(draft_params["participants"], multiple=True)
    if draft_params.get("sharedUsers"):
        result["sharedFormulaId"] = schedule_resource(draft_params["sharedUsers"], multiple=True)
    if draft_params.get("scheduleType"):
        result["typeFormulaId"] = schedule_resource(draft_params["scheduleType"])
    if draft_params.get("meetingRoom"):
        result["meetingRoom"] = schedule_resource(draft_params["meetingRoom"], multiple=True)
    if draft_params.get("otherMeetingRoom"):
        result["otherMeetingRoom"] = schedule_fixed("otherMeetingRoom", draft_params["otherMeetingRoom"])
    if isinstance(draft_params.get("customFormSetting"), dict):
        result["settingId"] = deepcopy(draft_params["customFormSetting"])

    # 简单枚举字段
    if draft_params.get("placeChoice"):
        result["placeChoice"] = str(draft_params["placeChoice"])
    if draft_params.get("secret"):
        result["secret"] = str(draft_params["secret"])

    if app_id:
        result["currentApplication"] = app_id
        result["applicationId"] = app_id
    return result
