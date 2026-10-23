"""动态赋值的字段引用、公式树与资源对象构造。"""
from __future__ import annotations

import json
from core.id_generator import gen_id
from core.runtime_metadata import (
    _TARGET_FORM_FIELDS,
    _WORKFLOW_CONTEXT_FIELDS,
    _WORKFLOW_CONTEXT_FIELDS_BY_KEY,
    _WORKFLOW_DETAIL_NAMES,
    find_in_metadata,
    workflow_field_id,
)

_SOURCE_COMPONENT_KEY_TO_PARAMTYPE: dict[str, str] = {
    # 基础文本
    "Text": "string", "TextArea": "string", "String": "string",
    "AutoSerial": "string", "Barcode": "string",
    # 日期/时间
    "Date": "date", "DateComponent": "datetime", "DateTimeComponent": "datetime",
    "DateTime": "datetime", "Time": "string",
    # 数字
    "NumberComponent": "number", "Number": "number", "Calculation": "number",
    "Money": "number", "Rate": "number", "Formula": "number",
    # 布尔
    "Switch": "boolean", "Boolean": "boolean",
    # 选择类 (前端按文本渲染, value 是 valueKey 字符串)
    "RadioBox": "string", "Checkbox": "string", "Select": "string",
    "MultiSelect": "string", "Radio": "string",
    # 复杂对象字段 (Employee/Department/Ebuilder 等): 在组件上下文里 paramType
    # 就是 string (存的是 id/姓名), 设计器字段类型列也显示"文本" — 不要映射成 object!
    "Employee": "string", "Department": "string", "SubCompany": "string",
    "Position": "string", "Role": "string", "Group": "string",
    "Ebuilder": "string", "RelateBrowser": "string", "Browser": "string",
    "Connect": "string", "Area": "string", "Folder": "string",
    "File": "string", "Image": "string", "Attachment": "string",
    # 公式/汇总
    "Summary": "number", "CrossStatement": "number",
}

def _resolve_source_field_type(param_key: str, meta: dict | None) -> str:
    """读 source 字段在**组件上下文**里的真实 paramType → 决定 formula field_type.

    约束: 设计器右侧"字段类型"列 (文本/日期时间/JSON) 就是
    component-context 返回的 paramType 渲染的 — 会议负责人字段在上下文里 paramType=string
    (设计器显示"文本"), 不是 object! 之前:
      1. _fill_setting mapping 分支硬编码 "Text" → 日期字段被当文本
      2. 上一版按表单 componentKey 映射 Employee→object → 前端显示"json" (错)
    修复: **优先查 _WORKFLOW_CONTEXT_FIELDS[formId][field].paramType** (preflight 已注册),
    那是设计器字段类型列的权威来源; 缓存缺失才 fallback componentKey 映射.

    param_key 可能是:
      - '{formId}.{fieldId}'         (mapping/operator 编译后)
      - 'dataResponse.{fieldId}'     (DateTrigger component-context 原始)
      - '{wfId}.{fieldId}'           (ApproveTrigger flow-context)
    取最后一段数字作为 fieldId, formId = workflow_id (DateTrigger = dataSource.id,
    ApproveTrigger = workflowId, EventFormData = targetForm.id).
    """
    if not param_key:
        return "string"
    pk = str(param_key)
    parts = pk.rsplit(".", 1)
    if len(parts) != 2:
        return "json" if pk.rstrip().endswith("[]") else "string"
    head, tail = parts[0], parts[1].rstrip("[]")
    if not tail:
        return "json" if pk.rstrip().endswith("[]") else "string"
    # 平台当前是纯数字 fieldId，但测试/迁移环境也可能使用临时或复合 ID；
    # 真实类型的匹配依据是 context.paramKey 尾段，不应把非数字 ID 直接降级。
    field_id = str(tail)
    # 明细表整体（`{workflowId}.{detailId}[]`）和明细子字段
    # （`{workflowId}.{detailId}[].{fieldId}`）都必须先走实时 context。
    # 旧版在此提前把所有 `[]` 引用归为 string，造成依据值 type=json、
    # config.paramType=string 的自相矛盾 JSON。
    if not isinstance(meta, dict):
        return "json" if pk.rstrip().endswith("[]") else "string"
    form_id = str(meta.get("_workflow_id", "") or meta.get("_event_form_id", ""))
    if not form_id:
        return "json" if pk.rstrip().endswith("[]") else "string"
    # 1) 权威: component-context 缓存的 paramType (设计器字段类型列来源)
    ctx_fields = _WORKFLOW_CONTEXT_FIELDS.get(form_id, {})
    exact_field = _WORKFLOW_CONTEXT_FIELDS_BY_KEY.get(form_id, {}).get(pk)
    if isinstance(exact_field, dict):
        exact_type = str(exact_field.get("paramType") or exact_field.get("paramTypeString") or "")
        if exact_type and exact_type != "None":
            return exact_type.lower() if exact_type.isupper() else exact_type
    for _name, _f in ctx_fields.items():
        if not isinstance(_f, dict):
            continue
        _fpk = str(_f.get("paramKey") or "")
        # 注册时 paramKey 是 component-context 原始格式 ('dataResponse.{fieldId}'),
        # 查询时是编译后 '{formId}.{fieldId}' — 按尾段 fieldId 匹配 (同一表单内唯一).
        _ftail = _fpk.rsplit(".", 1)[-1].rstrip("[]")
        if _ftail != field_id:
            continue
        pt = str(_f.get("paramType") or _f.get("paramTypeString") or "")
        if pt and pt != "None":
            # paramTypeString 是大写枚举 (STRING/DATETIME/JSON), paramType 是
            # 小写 (string/datetime/json) — 归一化小写, 但保留设计器显示用词
            return pt.lower() if pt.isupper() else pt
    # 2) 兜底: componentKey → paramType (仅基础类型; 对象类字段映射 string)
    field_meta = _TARGET_FORM_FIELDS.get(form_id, {}).get(field_id)
    if isinstance(field_meta, dict):
        ck = str(field_meta.get("componentKey") or field_meta.get("type") or "")
        if ck and ck in _SOURCE_COMPONENT_KEY_TO_PARAMTYPE:
            return _SOURCE_COMPONENT_KEY_TO_PARAMTYPE[ck]
    # 没有可查询上下文时，列表/明细表整体在平台契约中仍是 JSON；其余字段
    # 不猜复杂类型，维持 string 以便上层预检拒绝不可解析的资源对象。
    return "json" if pk.rstrip().endswith("[]") else "string"

def _resolve_source_field_label(param_key: str, meta: dict | None, fallback: str = "") -> str:
    """从实时组件上下文补回源字段中文名，禁止把数字 paramKey 当作赋值芯片名称。

    映射 plan 为了便于机器生成可以只给 ``<formId>.<fieldId>``，但前端 Assignment
    保存的 ``name`` 必须是 ``showName/paramName``。否则 readBack 虽成功，设计器会把
    右侧动态赋值显示成 ``1300...``，看起来像已失效引用。
    """
    if not isinstance(meta, dict):
        return str(fallback or param_key)
    pk = str(param_key or "")
    tail = pk.rsplit(".", 1)[-1].rstrip("[]")
    form_id = str(meta.get("_workflow_id", "") or meta.get("_event_form_id", ""))
    if form_id:
        exact_field = _WORKFLOW_CONTEXT_FIELDS_BY_KEY.get(form_id, {}).get(pk)
        if isinstance(exact_field, dict):
            label = exact_field.get("showName") or exact_field.get("paramName") or exact_field.get("content") or exact_field.get("name")
            if label:
                return str(label)
        for field in _WORKFLOW_CONTEXT_FIELDS.get(form_id, {}).values():
            if not isinstance(field, dict):
                continue
            field_pk = str(field.get("paramKey") or "")
            if field_pk == pk or field_pk.rsplit(".", 1)[-1].rstrip("[]") == tail:
                label = field.get("showName") or field.get("paramName") or field.get("content") or field.get("name")
                if label:
                    return str(label)
    if form_id:
        field = _TARGET_FORM_FIELDS.get(form_id, {}).get(tail)
        if isinstance(field, dict):
            label = field.get("showName") or field.get("name") or field.get("label") or field.get("content")
            if label:
                return str(label)
        # EventFormData 的运行时系统字段采用 ``<formId>.id``，但 component-context
        # 列表把同一个字段公开成数值键（当前平台为 .5）。不能让该别名退化为原始 id。
        system_label = {
            "id": "数据ID",
            "name": "数据名称",
            "creator": "创建者",
            "createTime": "创建时间",
            "lastUpdateTime": "最后更新时间",
            "lastUpdateUser": "最后更新人",
        }.get(tail)
        if system_label:
            return system_label
    return str(fallback or param_key)

# ── Formula 对象生成器(真实结构)───────────────────────────────────────────

def _resolve_param_key(workflow_id: str, key: str) -> str:
    """统一把 中文/裸字段名 → 完整 paramKey '{workflowId}.{fieldId}'.

     所有生成 context 字段引用的路径必须经此函数 —
    (build_setting_entry 的 is_update/is_add/else 分支、formula 复杂赋值
    _build_assign_bean、updateId/basisValueFormula _build_formula_reference).
    否则 value='FormData.{中文}' → 前端 cacheContext(paramKey 是数字) 找不到 →
    设计器字段标红 ("Object"/"文本" 类型不匹配) 或标"已删除".

    规则:
      - 中文名 (如 "请假事由") → 查 _WORKFLOW_FIELD_IDS 缓存 → "{wfId}.{fieldId}"
      - 已是 "{wfId}.{fieldId}" 数字格式 / 含 "[].{子字段id}" (依据值下级) → 原样保留
      - **'dataResponse.{fieldId}' 前缀 → 原样保留** (  钉死, **仅 DateTrigger
        事件**的上下文是这个格式; workflow_field_id 会把 dataResponse.xxx 拆成 xxx 再拼
        formId → '{formId}.{fieldId}' 与前端 cacheContext 不匹配 → 标红.
        实证: EventFormData/TimeBatchTrigger 是 '{formId}.{fieldId}' 格式,
        **不是** dataResponse — 格式必须按组件 component-context 验证, 不要泛化)
      - 缓存缺失 → 原样返回 (不破坏)
    """
    if not key:
        return key
    _key_s = str(key)
    if _key_s.startswith("dataResponse.") or ".dataResponse." in _key_s:
        return _key_s
    # 表单类事件的系统字段在 component-context 中不使用英文别名：例如用户语义
    # ``<formId>.id`` 对应实时返回的 ``<formId>.5``（showName=数据ID）。优先
    # 按实时上下文的中文系统字段名消解，避免把不存在的 `.id` 传给前端而标红。
    _system_aliases = {
        "id": "数据ID", "name": "标题", "creator": "创建者", "create_time": "创建时间",
        "update_time": "最后更新时间", "updater": "最后更新人", "data_status": "数据状态",
    }
    if workflow_id and "." in _key_s:
        _head, _tail = _key_s.rsplit(".", 1)
        _label = _system_aliases.get(_tail.rstrip("[]"))
        if _head == str(workflow_id) and _label:
            for _field in _WORKFLOW_CONTEXT_FIELDS.get(str(workflow_id), {}).values():
                if not isinstance(_field, dict):
                    continue
                if str(_field.get("showName") or _field.get("name") or "") != _label:
                    continue
                _resolved = str(_field.get("paramKey") or "")
                if _resolved:
                    return _resolved
    field_id = workflow_field_id(str(workflow_id), _key_s)
    if workflow_id and field_id and field_id != _key_s:
        return f"{workflow_id}.{field_id}"
    return _key_s

def _make_config_obj(config: dict) -> dict:
    """生成 configObject(同时附 config 字符串版本)"""
    return config

def _make_config_str(config: dict) -> str:
    """生成 config 字符串(后端快照格式).

    真实 capture 实证: 保存的设计 JSON 中,formula 的 config 字段必须是 JSON.stringify 后的字符串,
    不是对象.设计器前端在编辑态会用对象形式,但提交保存到后端后端会序列化为字符串.
    我们要直接发送字符串,否则设计器读不到 comId/paramKey 就会显示"已删除".
    """
    return json.dumps(config, ensure_ascii=False)

def formula_fixed(value, field_type="string") -> dict:
    """type=1 固定值公式，双写前端与后端均读取的固定值开关。"""
    fid = gen_id()
    return {
        "configObject": _make_config_obj({"paramType": field_type, "switchType": "fixvalue"}),
        "formulaType": field_type,
        "name": str(value),
        "id": fid,
        "type": "1",
        "value": str(value),
        "childs": [],
        "config": _make_config_str({
            "originValue": value,
            "switchType": "fixvalue",
            "formulaVersion": "V1",
        }),
        "sortWeight": 0.0,
    }


def formula_fixed_for_assign_switch(value, field_type="string") -> dict:
    """固定值专用：供 AssignSwitch 直接读取的 config 对象形态。

    通用组件持久化 FormulaBean 时可使用 ``formula_fixed`` 的 config 字符串；
    Approve、日程、消息等设计器控件则直接访问 ``bean.config.switchType``，
    因而必须保留对象。动态公式不调用本函数。
    """
    bean = formula_fixed(value, field_type=field_type)
    bean["fieldType"] = field_type
    bean["config"] = {
        "originValue": value,
        "switchType": "fixvalue",
        "formulaVersion": "V1",
    }
    return bean

def formula_context(source_component_id: str, field_key: str, *, name: str = "", business_id: str = "",
                    component_type: str = "ApproveTrigger", field_type: str = "string",
                    parent_com_id: str = "0", is_mult: bool = False) -> dict:
    """type=3 上下文引用公式 (完整版,与 e10-cli reloadFormula 结构对齐).

    source 必须是非空的真实节点 ID,name/value 也必须非空.
    补全 comId/comType/tableName/fieldInfo/multTypeObj/frontId 等平台所需字段.
    """
    fid = gen_id()
    source_id = str(source_component_id or "0")
    field_name = str(name or field_key)
    #  formulaType 必须用 _ft_norm(field_type) 归一化,
    # 不能写死 "json" — 设计器右侧"字段类型"列直接读 formulaType 渲染
    # 引用(会议负责人等)在设计器显示"JSON"类型, 约束错误.
    # 对齐 _assign_flat_context_direct (真实 type=3 结构 formulaType=string).
    return {
        "formulaType": _ft_norm(field_type),
        "name": field_name,
        "businessId": str(business_id or "0"),
        "id": fid,
        "source": source_id,
        "type": "3",
        "value": f"FormData.{field_key}",
        "frontId": str(field_key),
        "paramKey": str(field_key),
        "paramType": field_type,
        "childs": [],
        "config": _make_config_str({
            "paramKey": str(field_key),
            "paramType": field_type,
            "parentName": field_name,
            "newParentName": field_name,
            "multKey": "",
            "multName": "",
            "multTypeObj": {
                "allName": field_name,
                "currentName": field_name,
                "currentParamKey": f"FormData.{field_key}",
                "allParamKey": f"FormData.{field_key}",
            },
            "comId": source_id,
            "isMultCom": is_mult,
            "tableName": "表单数据",
            "fieldInfo": {
                "paramKey": str(field_key),
                "tablePrimaryKey": "FormData",
            },
            "comType": component_type,
            "parentComId": str(parent_com_id),
            "switchType": "assign",
            "formulaVersion": "V1",
        }),
        "sortWeight": 0.0,
    }

def formula_system_var(var_name: str = "{userid}") -> dict:
    """type=9 系统变量子节点"""
    fid = gen_id()
    return {
        "configObject": _make_config_obj({"paramType": "string"}),
        "formulaType": "string",
        "name": var_name,
        "id": fid,
        "type": "9",
        "value": var_name,
        "childs": [],
        "config": _make_config_str({"paramType": "string", "formulaVersion": "V1"}),
        "sortWeight": 0.0,
    }

def formula_container_string(child_formulas: list, value_placeholder: str = "", app_id: str = "") -> dict:
    """type=8 字符串公式容器(person/setting 根节点常用)"""
    fid = gen_id()
    vid = gen_id()
    # 给子节点设置 parentId
    for c in child_formulas:
        c["parentId"] = fid

    return {
        "configObject": _make_config_obj({"paramType": "string", "switchType": "assign"}),
        "formulaType": "string",
        "name": "",
        "id": fid,
        "type": "8",
        "applicationId": app_id,
        "value": value_placeholder or f"textarea#{vid}#",
        "childs": child_formulas,
        "config": _make_config_str({
            "paramType": "string", "switchType": "assign", "formulaVersion": "V1",
        }),
        "parentId": 0,
        "sortWeight": 0.0,
    }

def build_person_formula(person_ref: dict, meta: dict, app_id: str = "", for_send_message: bool = False,
                         direct_person: bool = False) -> dict:
    """根据 Draft person 引用生成完整 person formula 对象

    EbAction 的 person 字段(如"数据更新人")默认是"当前执行人".
    约束: 数据动作 (ActionEbAdd/Update/Delete/EnquiryForm) 的
    person **不要** type=8 容器 + textarea# 占位, 直接把 type=9 {userid} 本体放
    person 上 (direct_person=True). 其他组件 (MeetingCreate.operators /
    ApproveCreate.operator) 保持容器 (真机验证过).
    SendMessage 的 person 字段(如"操作人")用直接公式(1/3/9),
    具体类型由 person_ref.type 决定.
    """
    person = find_in_metadata(meta, "persons", person_ref)
    ptype = person.get("type", person_ref.get("type", "role")) if person else person_ref.get("type", "role")
    pid = person_ref.get("id", "")

    if for_send_message:
        # SendMessage: 直接公式
        if ptype == "role":
            return formula_system_var("{userid}")
        elif ptype in ("context", "user_reference"):
            #  接收人=流程表单人员字段 (如请假流程.姓名).
            # field_key 从 receiver 的 key/paramKey 取, 不只 id (receiver
            # {type:"context", key:"{wfId}.{fieldId}", label:"姓名"}).
            _ckey = str(person_ref.get("key") or person_ref.get("paramKey") or pid or "")
            return formula_context("", _ckey, name=str(person_ref.get("label") or person_ref.get("name") or _ckey))
        else:
            return formula_fixed(pid or person_ref.get("name", ""))

    # 约束: 数据动作 person 直连 (不包容器, 不用 textarea# 占位)
    if direct_person:
        if ptype == "context":
            # context 类型 person: type=3 本体直接返回 (不包容器)
            return formula_context("", pid)
        # role / user / 默认 -> 当前用户: type=9 本体直接返回
        return {
            "formulaType": "string",
            "name": "{userid}",
            "businessId": str(gen_id()),
            "id": str(gen_id()),
            "position": str(gen_id()),
            "type": "9",
            "value": "{userid}",
            "childs": [],
            "config": {"paramType": "string", "formulaVersion": "V1"},
        }

    # EbAction "数据更新人": 默认用当前执行人(type=9 系统变量)
    # 只有 Draft 明确指定为 context 时才引用上游输出
    if ptype == "context":
        # 显示 'dataResponse.{fieldId}' 而非 "{表单名}.{字段名}").
        # 与 SendMessage context 分支 (369 行) 同规则: key/paramKey 优先于 id.
        _ckey = str(person_ref.get("key") or person_ref.get("paramKey") or pid or "")
        # 上下文 → operator 引用标红. mapping assign 的 source 就是 event 节点 id.
        _src = str((meta or {}).get("_upstream_w_id", "")) if isinstance(meta, dict) else ""
        # plan 里 DateTrigger 上下文 key 写 component-context 返回的 paramKey
        # (如 'dataResponse.{fieldId}', 预检 _validate_references 按 store
        # 里的这个 key 校验), 转换后必须变回 '{formId}.{fieldId}' 数字格式
        # (前端 cacheContext 认, 与 mapping assign 一致) — 否则 value 写
        # 'FormData.dataResponse.xxx' 前端找不到 → operator 标红.
        _wf_id = str((meta or {}).get("_workflow_id", "")) if isinstance(meta, dict) else ""
        _pk = _resolve_param_key(_wf_id, _ckey)
        # (人员/关联 → object, 日期 → datetime, 文本 → string 等), 见
        _ft = _resolve_source_field_type(_pk, meta)
        # 生成 child**, 不用 formula_context — formula_context 无条件写
        # frontId=field_key (完整 paramKey), 而前端 vaildContext 第一分支
        # [field.id].includes(frontId) 拿 frontId 精确定位字段 — FormData 主表字段
        # 不需要 frontId (那是 ApprovalData 专用, 且是真实数字 id 如 "3"),
        # 写完整 paramKey → 前端找不到 → operator 标红.
        # _assign_flat_context_direct 与 mapping assign 同构: 无 frontId /
        # businessId=app_id / parentId="0" — 已验证正常渲染.
        _disp = str(person_ref.get("label") or person_ref.get("name") or _ckey)
        _pname = ""
        if isinstance(meta, dict):
            _pname = str(meta.get("_upstream_workflow_name", "") or "")
            if not _pname:
                _pname = str(meta.get("_upstream_form_name", "") or "")
        _full = f"{_pname}.{_disp}" if _pname else f"表单数据.{_disp}"
        child = _assign_flat_context_direct(
            _pk, _disp, _src, app_id, _ft,
            parent_name=_full, meta=meta,
        )
    else:
        # role / user / 默认 -> 当前用户
        child = formula_system_var("{userid}")
        child["position"] = str(gen_id())
        child["configObject"]["paramType"] = "string"
        child["config"] = _make_config_str({"paramType": "string"})
    return formula_container_string([child], app_id=app_id)

def _build_person_object(person_id: str, person_name: str, app_id: str = "") -> dict:
    """构建 shareList/person 用的 originValue 人员对象(最小可用字段).

    设计器 SendMessage「提醒对象」表格通过 getName() 读取
    obj_id.config.originValue[0].name/.content 渲染「对象」列,
    故 name/content/title/contentDesc 至少需有真实姓名.
    来源:captures/actionflows-测试/SendMessage.json 记录3 originValue 实证.
    """
    pid = str(person_id)
    pname = str(person_name or pid)
    return {
        "templateType": "default",
        "stopDepartment": False,
        "departmentId": "",
        "mobile": "",
        "pid": "",
        "avatar": {
            "name": pname,
            "appPreviewPath": "/api/app/file/preview?type=redirect&fileId=",
            "previewPath": "/api/file/preview?type=redirect&fileId=",
            "userId": pid,
        },
        "title": pname,
        "contentDesc": pname,
        "leaf": True,
        "userid": pid,
        "isLeaf": True,
        "content": pname,
        "name": pname,
        "id": pid,
        "position": "",
        "department": "",
        "mainId": pid,
        "cid": "",
        "statusCode": "normal",
    }

def _build_share_list(receiver: dict, meta: dict, app_id: str = "",
                      event_id: str = "") -> list:
    """从 Draft receiver 生成 shareList(设计器「提醒对象」表格数据源).

    真实 capture 实证(SendMessage.json 记录3/4): shareList 条目结构为
    {sourceId, permissionId:"esb", permissionType:1, user_type, obj_id{公式},
     targetId, sourceType:1, targetType, id, objType}.
    设计器 fieldContentMapUtils 将表单项 objectList 映射到 comData.shareList;
    EditableTable 通过 getName(rowData) 读取 obj_id.config.originValue[0].name
    渲染「对象」列.objType=resource(人力资源)时 targetType=1;
    switchType 必须为 "fixvalue"(MenuType.FixValue,小写v).

    receiver 支持全部设计器对象类型 (SendMessage/auth/constants.ts objectOptions):
      {type:"user", id, name}                     -> 人员 objType=resource (默认 user_type=1 当前人员)
      {type:"user", id, name, userType:"2"}       -> 人员 + 二级细化(2直接上级/3所有上级/4本部门/5本分部/6当前岗位)
      {type:"user", persons:[{id,name},...]}      -> 多人
      {type:"department", id, name}               -> 部门 obj_id_department
      {type:"subcompany", id, name}               -> 分部 obj_id_subcompany
      {type:"role", id, name}                     -> 角色 obj_id_role
      {type:"group", id, name}                    -> 群组 obj_id_group
      {type:"position", id, name}                 -> 岗位 obj_id_position
      {type:"external", id, name}                 -> 外部联系人 obj_id_external
      {type:"all"}                                -> 所有人(无需具体值)
      {type:"employeeScope", id, name}            -> 人员范围选择 obj_id_employeeScope
      {type:"employeeShare", id, name}            -> 人力资源条件 obj_id_employeeShare
      {type:"employeeOrganization", id, name}     -> 人员组织多选 obj_id_employeeOrganization

    附加属性:
      user_type:        "1"~"6"                          (resource)
      department_attribute: ["include_superior","subordinate","partTimeStaff"] (department/subcompany)
        id 含义: include_superior=含上级 subordinate=含下级 partTimeStaff=含兼职
        (前端 SendMessage/index.tsx getName 仅对 department/subcompany 生效)
      seclevel:         {"min": 0, "max": 100}           (所有类型, 安全级别范围)
      role_level:       "0"=总部/"1"=分部/"2"=部门       (role)
      position_attribute: ["partTimeStaff"]              (position, 含兼职)
      position_level:   "1"=总部/"2"=指定分部/"3"=指定部门 (position)
      position_level_subcompany: [{id,name}]             (position_level="2" 时必填)
      position_level_department: [{id,name}]             (position_level="3" 时必填)
    """
    if not isinstance(receiver, dict):
        return []

    obj_type = str(receiver.get("type", "user"))

    #  接收人=流程表单人员字段 (如 请假流程.姓名).
    # shareList objType=resource, obj_id=type=3 context 公式引用流程字段,
    # 不做 fixvalue/originValue (人员随流程实例动态).
    if obj_type in ("context", "user_reference"):
        key = str(receiver.get("key") or receiver.get("paramKey") or receiver.get("id") or "")
        if not key:
            return []
        label = str(receiver.get("label") or receiver.get("name") or key)
        obj_id_formula = formula_context(
            str(event_id) if event_id else str(gen_id()), key, name=label, field_type="string")
        return [{
            "sourceId": str(event_id) if event_id else str(gen_id()),
            "permissionId": "esb",
            "permissionType": 1,
            "objType": "resource",
            "user_type": "1",
            "targetId": key,
            "sourceType": 1,
            "targetType": 1,
            "id": str(gen_id()),
            "obj_id": obj_id_formula,
        }]

    # 设计器 objType 枚举 (SendMessage/auth/constants.ts getObjectOptions):
    #   resource/department/subcompany/role/group/position/employeeScope/
    #   employeeShare/employeeOrganization/all/external/allExternal
    # plan "user" (人员) 平台数据用 "resource", 不能直接发 "user" → 设计器下拉找不到
    # 见采购动作流配置详情数据.json shareList[0].objType="resource"
    if obj_type == "user":
        _objtype_for_designer = "resource"
    else:
        _objtype_for_designer = obj_type

    # 无值类型: all/allExternal 只需要 objType, 不需要对象值
    if obj_type in ("all", "allExternal"):
        return [{
            "sourceId": str(event_id) if event_id else str(gen_id()),
            "permissionId": "esb",
            "permissionType": 1,
            "objType": _objtype_for_designer,
            "sourceType": 1,
            "targetType": 1,
            "id": str(gen_id()),
        }]

    value_field = "obj_id" if obj_type == "user" else f"obj_id_{obj_type}"

    persons = receiver.get("persons")
    if not isinstance(persons, list):
        pid = str(receiver.get("id", "")).strip()
        pname = str(receiver.get("name", receiver.get("label", ""))).strip()
        persons = [{"id": pid, "name": pname}] if pid else []
    if not persons:
        return []

    user_type = str(receiver.get("userType", "1"))

    # 解析附加属性
    seclevel = receiver.get("seclevel")
    if isinstance(seclevel, (list, tuple)) and len(seclevel) == 2:
        seclevel = {"min": int(seclevel[0]), "max": int(seclevel[1])}

    role_level = str(receiver.get("roleLevel", "")) if obj_type == "role" else ""
    position_level = str(receiver.get("positionLevel", "")) if obj_type == "position" else ""
    position_level_subcompany = receiver.get("positionLevelSubcompany") if obj_type == "position" else None
    position_level_department = receiver.get("positionLevelDepartment") if obj_type == "position" else None
    position_attribute = receiver.get("positionAttribute") if obj_type == "position" else None
    department_attribute = receiver.get("departmentAttribute") if obj_type in ("department", "subcompany") else None

    share_list = []
    for p in persons:
        pid = str(p.get("id", "")).strip()
        pname = str(p.get("name", p.get("label", pid))).strip()
        if not pid:
            continue
        person_obj = _build_person_object(pid, pname, app_id)
        obj_id_formula = {
            "formulaType": "string",
            "name": pid,
            "id": str(gen_id()),
            "position": str(gen_id()),
            "type": "1",
            "applicationId": str(app_id),
            "value": pid,
            "fieldType": "string",
            "config": {
                "switchType": "fixvalue",
                "originValue": [person_obj],
            },
        }
        entry = {
            "sourceId": str(event_id) if event_id else str(gen_id()),
            "permissionId": "esb",
            "permissionType": 1,
            "objType": _objtype_for_designer,
            "targetId": pid,
            "sourceType": 1,
            "targetType": 1,
            "id": str(gen_id()),
        }
        if obj_type == "user":
            entry["user_type"] = user_type
        entry[value_field] = obj_id_formula

        # 附加属性(按 objType 应用, 未提供则不发字段)
        if seclevel and isinstance(seclevel, dict):
            entry["seclevel"] = seclevel
        if role_level:
            entry["role_level"] = role_level
        if position_level:
            entry["position_level"] = position_level
        if isinstance(position_level_subcompany, list) and position_level_subcompany:
            entry["position_level_subcompany"] = position_level_subcompany
        if isinstance(position_level_department, list) and position_level_department:
            entry["position_level_department"] = position_level_department
        if isinstance(position_attribute, list) and position_attribute:
            entry["position_attribute"] = position_attribute
        if isinstance(department_attribute, list) and department_attribute:
            entry["department_attribute"] = department_attribute

        share_list.append(entry)
    return share_list

def _ft_norm(field_type: str) -> str:
    """将表单字段类型归一化为 formula 的 formulaType 常用取值(用于 type4/5/6 叶子)."""
    return {
        "Text": "string", "String": "string", "string": "string",
        "Number": "number", "NumberComponent": "number", "number": "number",
        "DateComponent": "date", "Date": "date", "date": "date",
        "DateTime": "datetime", "datetime": "datetime",
    }.get(field_type, field_type or "string")

def formula_constant(constant_id, name: str = "", field_type: str = "string", app_id: str = "") -> dict:
    """type=5 常量引用公式.

    引擎按 value(平台常量 id)查常量表取内容(Eval.java case CONST).
    无 childs,直接作为 assign 叶子(与 type=1 固定值同构,只是 value 语义为 id).
    """
    fid = gen_id()
    ft = _ft_norm(field_type)
    return {
        "configObject": _make_config_obj({"paramType": ft, "switchType": "assign"}),
        "formulaType": ft,
        "name": name,
        "id": fid,
        "type": "5",
        "applicationId": app_id,
        "value": str(constant_id),
        "childs": [],
        "config": _make_config_str({"paramType": ft, "switchType": "assign", "formulaVersion": "V1"}),
        "parentId": 0,
        "sortWeight": 0.0,
    }

def formula_transform(rule_id, name: str = "", field_type: str = "string", app_id: str = "") -> dict:
    """type=4 转换规则公式.

    引擎按 value(平台转换规则 id)套用规则(Eval.java case CONVERT).
    无 childs,直接作为 assign 叶子.
    """
    fid = gen_id()
    ft = _ft_norm(field_type)
    return {
        "configObject": _make_config_obj({"paramType": ft, "switchType": "assign"}),
        "formulaType": ft,
        "name": name,
        "id": fid,
        "type": "4",
        "applicationId": app_id,
        "value": str(rule_id),
        "childs": [],
        "config": _make_config_str({"paramType": ft, "switchType": "assign", "formulaVersion": "V1"}),
        "parentId": 0,
        "sortWeight": 0.0,
    }

def _get_formula_fn(op: str) -> dict:
    """映射数学运算到 e10-cli 硬编码的 formula function ID."""
    MAP = {
        "add": {"fnId": "682682659616530901", "name": "+",
                "clazz": "com.weaver.common.formula.core.function.aggregate.Addition",
                "functionType": "operation"},
        "sub": {"fnId": "682682659616530902", "name": "−",
                "clazz": "com.weaver.common.formula.core.function.aggregate.Subtraction",
                "functionType": "operation"},
        "mul": {"fnId": "682682659616530903", "name": "×",
                "clazz": "com.weaver.common.formula.core.function.aggregate.Multiplication",
                "functionType": "operation"},
        "div": {"fnId": "682682659616530904", "name": "÷",
                "clazz": "com.weaver.common.formula.core.function.aggregate.Division",
                "functionType": "operation"},
    }
    return MAP.get(str(op).casefold(), MAP["add"])

def formula_function(func_id, name: str, childs: list, field_type: str = "string",
                     excel_func: dict = None, function_type: str = None,
                     detail: list = None, app_id: str = "") -> dict:
    """type=6 公式/函数公式(来自真实 capture 实证).

    value 拼接规则(招聘/E10 captures 验证):
        funcId # childId1 # childId2 # ... #
    即 functionId 与每个参数子节点的 id 用 '#' 连接,末尾补一个 '#'.
    childs 为空时 value = '<funcId>##'(如 NOW()).
    childs 为各参数子公式(可嵌套 type=3 引用或 type=6 函数).
    """
    fid = gen_id()
    ft = _ft_norm(field_type)
    child_ids = [str(c.get("id")) for c in childs if isinstance(c, dict)]
    value = f"{func_id}#" + "#".join(child_ids) + "#"
    config = {
        "paramType": ft,
        "originId": str(func_id),
        "paramSize": str(len(childs)),
        "excelFunc": excel_func if excel_func else {
            "formatString": name, "type": "function", "name": name,
            "validForm": "current_data", "paramCount": len(childs),
            "paramArray": [], "paramData": [], "returnType": ft,
        },
        "functionType": function_type or ft,
        "detail": detail or [],
        "formulaVersion": "V1",
    }
    return {
        "configObject": _make_config_obj({"paramType": ft, "switchType": "assign"}),
        "formulaType": ft,
        "name": name,
        "id": fid,
        "detail": detail or [],
        "type": "6",
        "applicationId": app_id,
        "value": value,
        "childs": childs,
        "config": _make_config_str(config),
        "parentId": 0,
        "sortWeight": 0.0,
    }

def _build_assign_bean(raw, field_id: str, field_type: str, meta: dict, app_id: str,
                       default_source_id: str = "") -> dict:
    """返回裸 formula bean(不含 setting.main 的 value wrapper).

    用于 formula 的参数子节点----真实 capture 中 type:6 的 childs 直接是裸
    type:3 / type:6 等 bean,不能包 value wrapper.
    """
    if not isinstance(meta, dict):
        meta = {}
    # 归一化引用层
    if isinstance(raw, dict):
        raw_value = raw.get("value", raw)
    else:
        raw_value = raw
    if isinstance(raw, dict) and ("kind" in raw or "assignmentKind" in raw):
        ref = raw
    elif isinstance(raw_value, dict):
        ref = raw_value
    else:
        ref = raw
    kind = (ref.get("kind") or ref.get("assignmentKind") or ref.get("type")) if isinstance(ref, dict) else None
    if kind is None:
        kind = "fixed"

    if kind in ("context",) or (isinstance(ref, dict) and "sourceRef" in ref):
        src = ref.get("sourceRef", ref) if isinstance(ref, dict) else ref
        # 兼容多种字段名(key/paramKey/fieldKey,谁先有值用谁)
        key = ""
        if isinstance(src, dict):
            key = src.get("key") or src.get("paramKey") or src.get("fieldKey") or ""
        if not key:
            key = field_id
        source_id = src.get("comId", src.get("source", "")) if isinstance(src, dict) else ""
        if str(source_id) in {"", "event", "event_1", "trigger"}:
            source_id = default_source_id
        label = src.get("label", src.get("name", key)) if isinstance(src, dict) else key
        #  中文/裸 key 统一映射成完整 paramKey (与 build_setting_entry 一致),
        # 否则 formula childs 引用中文 → 前端 cacheContext 找不到 → 标红.
        wf_id = str(meta.get("_workflow_id", "")) if isinstance(meta, dict) else ""
        resolved_key = _resolve_param_key(wf_id, str(key))
        return formula_context(
            str(source_id), resolved_key, name=str(label), business_id=app_id,
        )

    if kind == "system_variable":
        key = ref.get("key", "{userid}") if isinstance(ref, dict) else "{userid}"
        return formula_system_var(key)

    if kind == "constant":
        cid = (ref.get("id") or ref.get("key")) if isinstance(ref, dict) else None
        if not cid:
            raise ValueError(f"[constant] 缺少已解析的常量 id;ref={ref!r}")
        return formula_constant(cid, name=(ref.get("name", "") if isinstance(ref, dict) else ""),
                                field_type=field_type, app_id=app_id)

    if kind == "transform":
        rid = (ref.get("id") or ref.get("key")) if isinstance(ref, dict) else None
        if not rid:
            raise ValueError(f"[transform] 缺少已解析的转换规则 id;ref={ref!r}")
        return formula_transform(rid, name=(ref.get("name", "") if isinstance(ref, dict) else ""),
                                 field_type=field_type, app_id=app_id)

    if kind == "formula":
        fid = ref.get("id") if isinstance(ref, dict) else None
        if not fid:
            raise ValueError(f"[formula] 缺少已解析的函数 id;ref={ref!r}")
        childs = []
        for arg in (ref.get("arguments", []) if isinstance(ref, dict) else []):
            if isinstance(arg, dict):
                arg_name = arg.get("name", field_id)
                arg_val = arg.get("value", arg)
            else:
                arg_name, arg_val = field_id, arg
            childs.append(_build_assign_bean(arg_val, arg_name, field_type, meta, app_id))
        return formula_function(
            fid, name=(ref.get("name", "") if isinstance(ref, dict) else ""),
            childs=childs, field_type=field_type,
            excel_func=ref.get("excelFunc") if isinstance(ref, dict) else None,
            function_type=(ref.get("functionType") or ref.get("valueType")) if isinstance(ref, dict) else None,
            detail=ref.get("detail") if isinstance(ref, dict) else None,
            app_id=app_id)

    # fixed(标量 / 未识别)-> type 1
    if isinstance(ref, dict):
        val = ref.get("value", "")
        if isinstance(val, dict):
            val = val.get("value", "")
    else:
        val = ref
    if not isinstance(val, (str, int, float, bool)):
        val = "" if val is None else str(val)
    return formula_fixed(str(val), _ft_norm(field_type))

# ── 扁平 assign 公式(前端精简格式,非完整 formula bean) ──────────────────

# 固定值 / 系统变量 / 常量 / 转换规则 / 公式 的"语义层"中英文别名
# (设计器「固定值」对话框的 文本/整数/浮点数/布尔型/日期/时间/日期时间
#  + 流程相关/组织相关/业务表单相关 都映射到这三种 kind 之一.)
_SYSTEM_VALUE_ALIASES = {
    # 组织相关 (当前执行上下文)
    "currentUser": "{userid}", "currentDept": "{deptid}",
    "currentSubCompany": "{subcompanyid}", "currentPosition": "{positionid}",
    "currentRole": "{roleid}", "currentLoginId": "{loginid}",
    # 流程相关
    "workflowId": "{workflowid}", "formId": "{formid}",
    "requestId": "{requestid}", "workflowNo": "{workflowno}",
    # 业务表单相关
    "formData": "{formdata}", "currentTime": "{currenttime}",
    "currentDate": "{currentdate}",
}

_VALUE_TYPE_ALIASES = {
    "text": "Text", "string": "Text", "Text": "Text",
    "integer": "Number", "int": "Number", "Number": "Number",
    "long": "Number", "float": "Number", "double": "Number",
    "decimal": "Number", "number": "Number",
    "boolean": "Boolean", "bool": "Boolean", "Boolean": "Boolean",
    "date": "Date", "Date": "Date",
    "time": "Time", "Time": "Time",
    "datetime": "DateTime", "DateTime": "DateTime",
}

def _normalize_constant_assignment(value, default_field_type: str = "Text") -> tuple:
    """把 plan constants 值归一化为 (assignment, field_type), 支持:
      1. 简单字符串 → ({"kind":"fixed", "value":str}, default)
      2. {"value":..., "valueType":"integer"} → ({"kind":"fixed", "value":...}, 真实 type)
      3. {"systemValue":"currentUser"} → ({"kind":"system_variable", "key":"{userid}"}, "Text")
      4. {"kind":"system_variable", "key":"..."} → 原样
      5. {"kind":"constant", "id":"..."} → 原样
      6. {"kind":"transform", "id":"..."} → 原样
      7. {"kind":"formula", ...} → 原样
    返回 (assignment_dict, field_type_str) 供 build_setting_entry 使用.
    """
    if not isinstance(value, dict):
        return ({"kind": "fixed", "value": str(value) if value is not None else ""},
                default_field_type)

    # 已带 kind 的, 透传
    if "kind" in value or "assignmentKind" in value:
        # 即使有 kind, 也尝试从 valueType 取真实类型
        ft = _VALUE_TYPE_ALIASES.get(value.get("valueType", ""), default_field_type)
        return (value, ft)

    # systemValue 简写
    if "systemValue" in value:
        key = str(value["systemValue"])
        sys_var = _SYSTEM_VALUE_ALIASES.get(key, key)
        ft = _VALUE_TYPE_ALIASES.get(value.get("valueType", ""), default_field_type)
        return ({"kind": "system_variable", "key": sys_var}, ft)

    # valueType + value
    if "value" in value:
        ft = _VALUE_TYPE_ALIASES.get(value.get("valueType", ""), default_field_type)
        assignment = {"kind": "fixed", "value": value["value"]}
        #  Select 固定值支持 label — value 用 option valueKey
        # (如 "0"), label 用显示名 (如 "草稿"), build_setting_entry fixed 分支据此
        # 设 assign.name (前端 Select 下拉按 valueKey 命中 option, name 作展示).
        if value.get("label") is not None:
            assignment["label"] = value["label"]
        return (assignment, ft)

    # 兜底: 整个 dict 当 assignment
    return (value, default_field_type)

def _resolve_enum_constant(value, field_meta: dict | None) -> object:
    """把枚举字段的显示名解析为 getEbField 返回的真实 valueKey。

    Select/RadioBox 的保存值不是展示文本。若把“待确认”原样写入，服务端虽可
    保存，但前端 Select 无法命中选项而显示“请选择”。没有实时 option 样本时
    不猜 valueKey，直接拒绝该固定值。
    """
    if not isinstance(field_meta, dict):
        return value
    component_key = str(field_meta.get("componentKey") or field_meta.get("type") or "")
    if component_key not in {"Select", "RadioBox", "Checkbox", "MultiSelect", "Radio"}:
        return value
    if isinstance(value, dict):
        # 调用者已明确提供 valueKey + label 时保持原样；否则继续按 value 查找。
        if value.get("kind") or value.get("assignmentKind") or value.get("label") is not None:
            return value
        raw_value = value.get("value")
    else:
        raw_value = value
    options = field_meta.get("selectData") or (field_meta.get("fieldConfig") or {}).get("options") or []
    for option in options:
        if not isinstance(option, dict):
            continue
        option_value = str(option.get("valueKey") or option.get("value") or option.get("id") or "")
        option_name = str(option.get("name") or option.get("label") or "")
        if str(raw_value) in {option_value, option_name}:
            return {"value": option_value, "label": option_name or str(raw_value)}
    raise ValueError(
        f"枚举字段 '{field_meta.get('showName') or field_meta.get('name') or ''}' 的固定值"
        f" '{raw_value}' 未在实时选项中找到，拒绝伪造 option valueKey"
    )

def _lookup_target_field_meta(target_field_id: str, result: dict) -> dict | None:
    """按当前目标表单优先、全局实时缓存兜底取字段元数据。

    registry 的 dataMapping 顺序不保证 `_targetForm` 先于 `_setting_constants`
    执行，因此不能只依赖 result.targetForm；字段 ID 在 e-builder 中全局唯一，
    回退扫描已经由本轮 getEbField 注册过的实时缓存仍是确定的，不会猜字段。
    """
    target_form = result.get("targetForm") if isinstance(result, dict) else {}
    target_form_id = str((target_form or {}).get("id") or "")
    direct = _TARGET_FORM_FIELDS.get(target_form_id, {}).get(str(target_field_id))
    if isinstance(direct, dict):
        return direct
    matches = [fields[str(target_field_id)] for fields in _TARGET_FORM_FIELDS.values()
               if isinstance(fields, dict) and isinstance(fields.get(str(target_field_id)), dict)]
    return matches[0] if len(matches) == 1 else None

def _assign_flat_fixed(value_str: str, app_id: str, field_type: str = "string") -> dict:
    """生成前端精简版固定值 assign(formulaType 不做空/Unknown 兜底)."""
    fid = gen_id()
    return {
        "id": str(fid),
        "name": str(value_str),
        "value": str(value_str),
        "type": "1",
        "fieldType": field_type,
        "formulaType": field_type,
        "applicationId": str(app_id) if app_id else "",
        "config": {
            "originValue": value_str,
            "switchType": "fixvalue",
        },
    }

def _assign_flat_context(param_key: str, field_label: str,
                         source_id: str, app_id: str,
                         field_type: str = "string", parent_name: str = "",
                         temp_formula_id: str = "", table_id: str = "",
                         component_key: str = "Text",
                         param_key_full: str = "", value_full: str = "") -> dict:
    """生成前端精简版上下文引用 assign.

    最小字段版(原版能 saved=True),仅比初始版多 paramTypeString/dataTypeSting 等
    几个 e10-cli 字段,但不含 paramKey 重写等可能影响服务端的字段.
    """
    fid = gen_id()
    src = str(source_id) if source_id else "0"
    pname = str(parent_name or field_label)
    val = value_full or (f"FormData.{table_id}.{param_key}" if table_id else f"FormData.{param_key}")
    pkey = param_key_full or (f"{table_id}.{param_key}" if table_id else str(param_key))
    return {
        "id": fid,
        "name": str(field_label),
        "value": val,  # 用 param_key_full 构造的 id 格式 (FormData.{workflowId}.{fieldId})
        "type": "3",
        "fieldType": field_type,
        "formulaType": field_type,
        "businessId": str(app_id) if app_id else "",
        "applicationId": str(app_id) if app_id else "",
        "source": src,
        "paramTypeString": "STRING",
        "dataTypeSting": "ATTRIBUTE",
        "config": _make_config_str({
            "switchType": "assign",
            "comId": src,
            "paramKey": pkey,  # 用 id 格式 ({workflowId}.{fieldId}),中文会标"已删除"
            "paramType": field_type,
            "parentName": pname,
            "newParentName": pname,
            "multName": "",
            "multKey": "",
            "multTypeObj": {
                "currentName": pname,
                "allName": pname,
                "currentParamKey": val,
                "allParamKey": val,
            },
            "isMultCom": False,
            "comType": "ApproveTrigger",
            "tableName": "表单数据",
            "fieldInfo": {
                "tablePrimaryKey": "FormData",
                "paramKey": pkey,
            },
            "tempFormulaId": str(temp_formula_id) if temp_formula_id else "",
            "formulaVersion": "V1",
        }),
        # 顶层加 parentName/tempFormulaId 让设计器能正确解析
        "parentName": pname,
        "tempFormulaId": str(temp_formula_id) if temp_formula_id else "",
    }

def _assign_flat_context_direct(param_key: str, field_label: str,
                                source_id: str, app_id: str,
                                field_type: str = "string",
                                parent_name: str = "",
                                meta: dict | None = None) -> dict:
    """type=3 直连动态赋值 — 主表单值字段的标准形态 .

    前端 assignment 组件源码实证 (components/common/assignment/store.ts onSave):
    单值、非 textarea 字段保存时走 ``onSaveCallBack(assigns[0])`` —— 直接保存
    单个 type=3 assign (config 为**对象**), 不包 type=8 容器, 不用 textarea# 占位.
    只有 Text/TextArea 字段 (openTextarea=true) 或 multiple 才走 transSaveData
    生成 type=8 容器 + textarea#/multipleSelect#.

    结构对齐  平台回读实证 (成功版 type=8 容器内的 child):
      formulaType/name/businessId/id/source/type/value/childs/config(对象)/parentId.
    区别: name 用中文 label (设计器显示), parentId="0" (无容器包裹).

    用户手动版回读实证 (ApprovalData 系统字段, paramKey 末段非数字
    如 requestId/dataId/formId):
      1. **frontId = 真实字段 id (数字, requestId→"3")** — 前端 vaildContext 第一分支
         `[field.id].includes(frontId)` 用它精确定位「流程触发[流程数据]」组.
      2. **config.tableName = "流程数据"** (前端 context 组件 `tableName: table?.name`,
         ApprovalData 组 name=「流程数据」, 不是写死的「表单数据」) — 前端渲染
         「所属组件:流程触发[流程数据]」读的就是它.
      3. **parentName 用流程名前缀** (如 "采购合同报备.流程ID") — 前端渲染
         「参数路径」用 parentName + showName.
    缺任一 → 前端错归「表单数据」组 / 参数路径显示数字 paramKey / 标"已删除".

    FormData 主表数字字段 (如 关联合同) 不需要 frontId, tableName="表单数据",
    parentName="目标表单名.xxx" (前端归类到「流程触发[表单数据]」组).

    之前主表普通字段无条件包 type=8 容器 + textarea# (formula_container_string),
    设计器里 value 显示 "textarea#..." 且 name 是数字 paramKey → 用户视觉错误.
    """
    fid = gen_id()
    src = str(source_id) if source_id else "0"
    pkey = str(param_key)
    pname = str(parent_name or f"表单数据.{field_label}")
    #  is_approval 判断先去末尾 [] — 人员多值字段
    # (Employee, paramKey '...3825[]') 是 FormData 组, 不能误判为 ApprovalData.
    #  明细子字段 (含 '[].' 如 '{wfId}.{明细表id}[].rowId') 也是
    # FormData 组 — rowId 末段非数字但不能归 ApprovalData. 只有 '{wfId}.requestId'
    # 这类无 '[].' 且末段非数字的才是流程数据.
    _tail = str(pkey).rsplit(".", 1)[-1].rstrip("[]")
    _plain_approval_shape = (not _tail.isdigit()) and ("[]. " not in str(pkey) and "[]." not in str(pkey))
    #  ApprovalData 系统字段判定 — 末段非数字 **且缓存字段无
    # componentKey**. ApprovalData 字段 (requestId/dataId/...) 无 componentKey;
    # 普通流程表单字段 (Text/Select 等) 有 componentKey (如测试模拟 wf-1.src-text),
    # 归 FormData 组, 不能用 ApprovalData 前缀. frontId 查询与 componentKey 判定
    # 共用一次缓存遍历.
    front_id = ""
    _ctx_component_key = ""
    # frontId 仅是 ApprovalData 的字段定位键。FormData（包括 EventFormData、
    # TimeBatchTrigger、DateTrigger）依赖 paramKey + component context 查找；给它
    # 塞入字段 id 会触发前端 vaildContext 的错误分支，动态赋值被标红。
    wf_id = str(meta.get("_workflow_id", "") or meta.get("_event_form_id", "")) if isinstance(meta, dict) else ""
    ctx_fields = _WORKFLOW_CONTEXT_FIELDS.get(wf_id, {}) if wf_id else {}
    pkey_tail = pkey.rsplit(".", 1)[-1].rstrip("[]")
    for _name, _field in ctx_fields.items():
        if not isinstance(_field, dict):
            continue
        candidate = str(_field.get("paramKey") or "")
        if candidate != pkey and candidate.rsplit(".", 1)[-1].rstrip("[]") != pkey_tail:
            continue
        if str(_field.get("id") or ""):
            front_id = str(_field["id"])
        _ctx_component_key = str(_field.get("componentKey") or "")
        break
    is_approval = _plain_approval_shape and not _ctx_component_key
    # DateTrigger 的上下文键固定为 ``dataResponse.<fieldId>``。它虽然不以数字
    # 表单 ID 开头，但仍属于日期触发器的表单数据组，绝不能按“末段非数字”误归入
    # ApprovalData；否则会保存为 ``ApprovalData.dataResponse.id``，设计器找不到
    # 该上下文并把“数据ID/人员”等动态赋值标错。
    if pkey.startswith("dataResponse.") and isinstance(meta, dict) and \
            str(meta.get("_upstream_component_type", "")) == "DateTrigger":
        is_approval = False
    #  FormData 系统字段判定 — 末段非数字且无 componentKey 的不全是
    # ApprovalData. FormData 组系统字段 (paramKey 前缀=表单id, 如 '{formId}.id' 数据ID /
    # '{formId}.name' / '{formId}.creator') 也 componentKey=None, 但必须归 FormData 组.
    # 用事件绑定表单 id (_event_form_id) 区分: paramKey 前缀=表单id → FormData 组;
    # 前缀=流程id (ApprovalData 的 requestId 等) 才可能归流程数据组.
    if is_approval and isinstance(meta, dict):
        _form_id = str(meta.get("_event_form_id", "") or "")
        _pkey_head = str(pkey).split(".", 1)[0] if "." in str(pkey) else ""
        if _form_id and _pkey_head == _form_id:
            is_approval = False
    if not is_approval:
        front_id = ""
    prefix = "ApprovalData" if is_approval else "FormData"
    # 上游事件并不总是 ApproveTrigger。表单/日期/定时触发的动态赋值必须保留
    # 真实组件类型，否则设计器会把引用归到错误的组件上下文并显示“已删除”。
    source_component = "ApproveTrigger"
    if isinstance(meta, dict) and meta.get("_upstream_component_type"):
        source_component = str(meta["_upstream_component_type"])
    result = {
        "formulaType": field_type,
        "name": str(field_label),
        "businessId": str(app_id) if app_id else "",
        "id": fid,
        "source": src,
        "type": "3",
        "value": f"{prefix}.{pkey}",
        "frontId": front_id,
        "paramKey": pkey,
        "parentName": pname,
        "childs": [],
        "config": {
            "paramKey": pkey,
            "isMultCom": False,
            "comType": source_component,
            "switchType": "assign",
            "formulaVersion": "V1",
            "fieldInfo": {"paramKey": pkey, "tablePrimaryKey": prefix},
            #  ApprovalData 系统字段 → "流程数据" (前端 context 组件
            # tableName: table?.name; ApprovalData 组 name=「流程数据」); FormData 字段 → "表单数据".
            "tableName": "流程数据" if is_approval else "表单数据",
            "paramType": field_type,
            "parentName": pname,
            "multName": "",
            "multKey": "",
            "multTypeObj": {
                "allName": pname,
                "currentName": pname,
                "currentParamKey": f"{prefix}.{pkey}",
                "allParamKey": f"{prefix}.{pkey}",
            },
            "comId": src,
            "newParentName": pname,
        },
        "parentId": "0",
    }
    if front_id:
        result["frontId"] = front_id
    return result

def _assign_flat_esb_self(param_key: str, field_label: str,
                          source_id: str, app_id: str,
                          field_type: str = "string") -> dict:
    """type=10 esbAssignSelf —— Update 模式下"依据值本身"���值.

    e10-cli 实证: ActionEbUpdate + OPERATE_EQUAL 时使用 type=10,
    switchType="sub", value="esbAssignSelf", 内嵌上下文引用在 config 中.
    """
    fid = gen_id()
    src = str(source_id) if source_id else "0"
    return {
        "id": str(fid),
        "name": f"{field_label}(依据值本身)",
        "value": "esbAssignSelf",
        "type": "10",
        "fieldType": field_type,
        "formulaType": field_type,
        "applicationId": str(app_id) if app_id else "",
        "config": {
            "originValue": "esbAssignSelf",
            "switchType": "sub",
            "id": "esbAssignSelf",
            "content": f"{field_label}(依据值本身)",
            "source": src,
            "frontId": str(param_key),
            "value": f"FormData.{param_key}",
            "paramKey": str(param_key),
            "config": {
                "paramKey": str(param_key),
                "paramType": field_type,
                "parentName": field_label,
                "newParentName": field_label,
                "multKey": "", "multName": "",
                "multTypeObj": {
                    "allName": field_label, "currentName": field_label,
                    "currentParamKey": f"FormData.{param_key}",
                    "allParamKey": f"FormData.{param_key}",
                },
                "comId": src, "isMultCom": False,
                "tableName": "表单数据",
                "fieldInfo": {"tablePrimaryKey": "FormData", "paramKey": str(param_key)},
                "comType": "ApproveTrigger", "parentComId": "0",
                "switchType": "assign",
            },
            "level": 0, "basisType": "formSetting",
        },
        "childs": [],
    }

def _assign_flat_esb_child(param_key: str, field_label: str,
                           source_id: str, app_id: str,
                           field_type: str = "string",
                           detail_param_key: str = "",
                           detail_label: str = "",
                           workflow_name: str = "") -> dict:
    """type=10 依据值下级 (明细表子字段) — batchInsert 批量新增的字段映射.

     用户手动保存回读实证 (ActionEbAdd batchInsert):
      assign: {type:10, value:'<子字段id>', name:'<子字段名>',
               config:{paramKey:'{wfId}.{明细表id}[].{子字段id}', level:1,
                       switchType:'sub', basisType:'formSetting',
                       id:'<子字段id>', content:'<子字段名>', originValue:'<子字段id>',
                       value:'FormData.{wfId}.{明细表id}[]',
                       config:{paramKey:'{wfId}.{明细表id}[]', parentName:'<明细表名>[]',
                               ...}}}
    与"依据值本身"(esbAssignSelf, level=0) 的区别: value/originValue/id/content 是子字段,
    paramKey 带 '[].{子字段id}', 且顶层 config.value = FormData.{明细表}[] (明细表整体).
    parentName/newParentName/multTypeObj 用**明细表名**(detail_label), 不是子字段名.
    """
    fid = gen_id()
    src = str(source_id) if source_id else "0"
    # 旧逻辑 rsplit("[]",1)[-1] — param_key='...8504[].<子字段id>[]' 按最后
    # 一个 [] 拆 → '' (空) → value='' → 设计器"请选择" ( 负责人).
    # 正确: 取最后一段 ('.' 之后), 再去尾部 [] (人员多值). 适用于:
    #   '{wfId}.{明细表id}[].{子字段id}'      → '{子字段id}'
    #   '{wfId}.{明细表id}[].{子字段id}[]'   → '{子字段id}'  (人员多值去尾部 [])
    _tail = str(param_key).rsplit(".", 1)[-1]
    sub_id = _tail.rstrip("[]")
    # detail_param_key 如 '{wfId}.{明细表id}[]' (明细表整体引用, config.value 用)
    detail_pk = str(detail_param_key or (str(param_key).rsplit("[]", 1)[0] + "[]"))
    detail_val = f"FormData.{detail_pk}"
    # 平台保存时被清空. multTypeObj.allName 才用明细表名.
    parent_name = f"{workflow_name}.{str(field_label)}[]" if workflow_name else f"{str(field_label)}[]"
    _sub_name = f"{workflow_name}.{str(field_label)}" if workflow_name else str(field_label)
    _all_name = f"{workflow_name}.{str(detail_label)}[]" if workflow_name and detail_label else parent_name
    return {
        "id": fid,
        "name": str(field_label),
        "value": sub_id,
        "type": "10",
        "fieldType": field_type,
        "formulaType": field_type,
        "applicationId": str(app_id) if app_id else "",
        "config": {
            "paramKey": str(param_key),
            "basisType": "formSetting",
            "switchType": "sub",
            "level": 1,
            "id": sub_id,
            "source": src,
            "formulaVersion": "V1",
            "value": detail_val,
            "config": {
                "paramKey": detail_pk,
                "isMultCom": False,
                "comType": "ApproveTrigger",
                "switchType": "assign",
                "parentComId": 0,
                "fieldInfo": {"paramKey": detail_pk, "tablePrimaryKey": "FormData"},
                "tableName": "表单数据",
                # 该内层引用是明细子字段，不应把日期/数字/人员等统一降为文本。
                "paramType": field_type,
                "parentName": parent_name,
                "multName": "", "multKey": "",
                "multTypeObj": {
                    # 都带流程名前缀 ('采购合同报备.付款条件明细[]' / '采购合同报备.付款条件').
                    "allName": _all_name,
                    "currentName": _sub_name,
                    "currentParamKey": f"FormData.{param_key}" if not str(param_key).startswith("FormData.") else str(param_key),
                    "allParamKey": detail_val,
                },
                "comId": src, "newParentName": parent_name,
            },
            "originValue": sub_id,
            "content": str(field_label),
        },
        "childs": [],
        "parentId": "0",
    }

def _assign_flat_system_var(var_name: str = "{userid}", app_id: str = "",
                             field_type: str = "string") -> dict:
    fid = gen_id()
    return {
        "id": str(fid),
        "name": var_name,
        "value": var_name,
        "type": "9",
        "fieldType": field_type,
        "formulaType": field_type,
        "applicationId": str(app_id) if app_id else "",
        "config": {
            "switchType": "assign",
            "paramType": field_type,
        },
    }

def build_setting_entry(field_id: str, assignment, field_type: str = "Text", meta: dict = {},
                        app_id: str = "", default_source_id: str = "",
                        operate: str = "OPERATE_EQUAL", component_type: str = "",
                        detail_mode: bool = False) -> dict:
    """生成 ActionEbAdd/Update 字段映射结构(精简 assign,兼容六类赋值).

    六类 kind 与产出 type 的映射:
        fixed           -> type 1  (字面量)
        context         -> type 3  (上下文引用), Update + EQUAL 则用 type=10
        constant        -> type 5  (平台常量 id)
        transform       -> type 4  (平台转换规则 id)
        formula         -> type 6  (函数/公式树)
        system_variable -> type 9
    """
    if not isinstance(meta, dict):
        meta = {}

    # 归一化:取出承载 kind/id/arguments 的"引用层"
    if isinstance(assignment, dict):
        raw_value = assignment.get("value", assignment)
    else:
        raw_value = assignment
    if isinstance(assignment, dict) and ("kind" in assignment or "assignmentKind" in assignment):
        ref = assignment
    elif isinstance(raw_value, dict):
        ref = raw_value
    else:
        ref = assignment

    kind = (ref.get("kind") or ref.get("assignmentKind") or ref.get("type")) if isinstance(ref, dict) else None
    if kind is None:
        kind = "fixed"
    assign_id = gen_id()

    # ── 构建 assign 公式(前端精简格式) ──
    ft = _ft_norm(field_type)
    is_update = component_type == "ActionEbUpdate"
    is_add = component_type == "ActionEbAdd"

    if kind in ("context",):
        key = ""
        if isinstance(ref, dict):
            key = ref.get("paramKey") or ref.get("key") or ref.get("fieldKey") or ""
        label = ref.get("label", ref.get("name", key)) if isinstance(ref, dict) else key
        src = ref.get("source", ref.get("comId", "")) if isinstance(ref, dict) else ""
        if str(src) in {"", "event", "event_1", "trigger"}:
            src = default_source_id

        #  依据值下级 (key 含 '[].', 如 '{明细表id}[].{子字段id}')
        # 是 batchInsert/明细映射专用格式, 走 type=10 直连 (assign 在 value.assign 下,
        # 平台 saveFormData 处理 detail 时 type=10 直连会导致整个 action.data 被丢弃
        # (验证 data=null). detail 里明细子字段引用必须用 type=8 容器包 type=3
        # (成功案例 <成功案例appId>: child.value='FormData.{明细表id}[].{子字段id}').
        #  依据值下级 (key 含 '[].') **不限 detail_mode** —
        # ActionEbAdd batchInsert main (not detail_mode) + ActionEbAdd/Update 的
        # 走 type=8 容器 → 渲染"动态赋值". 去掉 `not detail_mode` 让 detail 也走 type=10.
        if "[]. " in str(key) or "[]." in str(key):
            workflow_id = str(meta.get("_workflow_id", "")) if isinstance(meta, dict) else ""
            if not str(key).startswith(str(workflow_id) + "."):
                pkey_full = f"{workflow_id}.{str(key)}" if workflow_id else str(key)
            else:
                pkey_full = str(key)
            # 子字段名/明细表名: ref 可带 label(子字段名)/detailLabel(明细表名);
            # 缺省从 paramKey 提取子字段 id 作显示名, 明细表名取 paramKey 中段.
            sub_label = str(label or key)
            detail_label = str((ref.get("detailLabel") or ref.get("parentName") or "") if isinstance(ref, dict) else "")
            if not detail_label:
                detail_label = pkey_full.rsplit("[]", 1)[0].rsplit(".", 1)[-1]  # 明细表 id
            #  明细表真实名称优先从 preflight 缓存取 (plan detailLabel
            # 可能写错名 "付款条件明细"≠真实"付款条件" → main 字段 allName 名错).
            _pk_head = str(pkey_full).split(".", 1)[0]
            _pk_subf = str(pkey_full).rsplit("[]", 1)[0].rsplit(".", 1)[-1]
            _real_dtl = _WORKFLOW_DETAIL_NAMES.get(_pk_head, {}).get(_pk_subf, "")
            if _real_dtl:
                detail_label = _real_dtl
            #  传 workflow_name 让 parentName 带流程名前缀
            _workflow_name = str((meta or {}).get("_upstream_workflow_name", "") or "")
            flat = _assign_flat_esb_child(pkey_full, sub_label, str(src), app_id, ft,
                                          detail_label=detail_label, workflow_name=_workflow_name)
            switch_t = "sub"
            # (不设 deleteType) → 记录入库后 getDetail(delete_type=0) 查不到 →
            # batchInsert 的 main 回读恒 None → 设计器字段映射空.
            # 后端逻辑 (FormDataUtil.saveFormData): formFieldKey 空 → actionDetail.init()
            # (deleteType=0) → insert; 非空 → initUpdate() → 存不进 getDetail 可见区.
            # 验证: insert 模式 formFieldKey="" 回读正常 (平台回填真实 id 三值同);
            # value 内不放假的 id/primaryId/fieldSet (后端不解析, 对齐 insert 形态).
            entry_value = {
                "original": False,
                "operate": operate,
                "switchType": "sub",
                "fieldKey": field_id,
                "assignType": "",
                "fieldType": field_type,
                "assignId": str(flat.get("id", "")),
                "assign": flat,
                "multiSelect": False,
            }
            return {
                "formFieldKey": "",
                "value": entry_value,
            }
        elif is_update and operate == "OPERATE_EQUAL":
            # Update + 普通映射 → 改 type=3 直连 (用户 v1-v12 钉死:
            # 主表/流程数据字段动态赋值 = type=3 直连, 带 ApprovalData 前缀/tableName/
            # frontId 分支; 旧 type=10 esbAssignSelf 设计器渲染"依据值本身"且 requestId
            # 类字段无 ApprovalData 支持 → 标"已删除").
            workflow_id = str(meta.get("_workflow_id", "")) if isinstance(meta, dict) else ""
            param_key_full = _resolve_param_key(workflow_id, str(key))
            flat = _assign_flat_context_direct(
                param_key_full, str(label or key), str(src), app_id,
                parent_name=str(meta.get("_upstream_workflow_name", "")) if isinstance(meta, dict) else "",
                meta=meta,
            )
            switch_t = "assign"
        elif is_add and operate == "OPERATE_EQUAL":
            # Add + 普通映射 → type=8 容器包裹 type=3 (e10-cli makeFieldMappingFormula)
            # tempFormulaId = type=8 容器的 id(指向自己),parentName 用 "表单数据.字段名"(非"流程触发.X")
            # value/paramKey 格式 = "{workflowId}.{fieldId}" 数字层级(e10-cli 标准),不能用中文,
            # 否则设计器找不到字段标"已删除".key 是 plan 里的源字段名,通过 workflow_field_id
            # 映射为真实字段 id(未查询到则保留原名).
            form_name = ""
            table_id = ""
            workflow_id = ""
            if isinstance(meta, dict):
                form_name = str(meta.get("_upstream_form_name", ""))
                table_id = str(meta.get("_upstream_table_id", ""))
                workflow_id = str(meta.get("_workflow_id", ""))
            src_field_id = workflow_field_id(workflow_id, str(key))
            #  parent_name 前缀按字段类型分派 — FormData 主表数字字段
            # 用目标表单名 (前端归类到「流程触发[表单数据]」组); ApprovalData 系统字段
            # (paramKey 末段非数字, 如 requestId) 用流程名 (前端归类到「流程触发[流程数据]」组).
            wf_name = str(meta.get("_upstream_workflow_name", "")) if isinstance(meta, dict) else ""
            #  人员多值字段 paramKey 末段 '...3825[]' — 去 [] 判断
            pk_tail = str(key).rsplit(".", 1)[-1].rstrip("[]")
            if not pk_tail.isdigit() and wf_name:
                parent_name = f"{wf_name}.{label or key}"
            elif form_name:
                parent_name = f"{form_name}.{label or key}"
            else:
                parent_name = str(label or key)
            #  明细表子字段引用 '{明细表id}[].{子字段id}' — main 的
            # 用 type=8 容器包 type=3, paramKey 拼 wfId 前缀 ({wfId}.{明细表id}[].{子字段id},
            if "[]. " in str(key) or "[]." in str(key):
                # 前端同事反馈的**正确格式** (依据值下级):
                #   type=10 直连 + value=子字段 id (paramName) + config={switchType:"sub",
                #   level:1, basisType:"formSetting"}.
                # 是**错误格式** — 前端 getDftType 读 assign.config.switchType, 容器顶层
                # 是 assign → 渲染"动态赋值"; 且 value 不是 paramName, 前端识别不出"依据值下级".
                # 正确: assign 本身 type=10, value=子字段 id, config.switchType='sub'.
                # 子字段选择器过滤: 可选子字段的 parentId == 依据值(上下文对象)的 id
                _sub_id = str(key).rsplit("[].", 1)[-1].rsplit(".", 1)[-1]
                flat = {
                    "id": str(gen_id()),
                    "name": str(label or key),
                    "value": _sub_id,
                    "type": "10",
                    "fieldType": "string",
                    "formulaType": "string",
                    "applicationId": str(app_id) if app_id else "",
                    "config": {
                        #  originValue = 子字段 id — 前端
                        # AssignSwitch getCom (L228) 渲染"依据值下级"已选值时读
                        # `assigns[0].config.originValue`, 缺则 selectVal='' → "请选择".
                        "originValue": _sub_id,
                        "switchType": "sub",
                        "level": 1,
                        "basisType": "formSetting",
                    },
                }
                switch_t = "sub"
            else:
                # 普通字段引用 (无 '[].')
                #  主表字段 (非 detail_mode) → type=3 直连 (config 为对象).
                # 不包 type=8 容器, 不用 textarea# 占位 (约束 "textarea#..." 视觉错误).
                # detail 走 type=10 直连会导致平台丢弃整个 action.data).
                pkey = _resolve_param_key(workflow_id, str(key))
                pval = f"FormData.{pkey}"
                if not detail_mode:
                    #  parent_name 前缀按字段类型分派 —
                    # - FormData 主表数字字段 (如 关联合同 <fieldId>): 用
                    #   目标表单名 "付款计划.{pkey}" (前端归类到"流程触发[表单数据]"组, 该组含此字段)
                    # - ApprovalData 系统字段 (如 requestId/dataId/formId, paramKey 末段非数字):
                    #   用流程名 "采购合同报备.{pkey}" (前端归类到"流程触发[流程数据]"组, 该组含 requestId)
                    # 用目标表单名前缀会归到表单数据组, 而该组无 requestId → 标"已删除".
                    pk_tail = str(pkey).rsplit(".", 1)[-1]
                    wf_name = str(meta.get("_upstream_workflow_name", "")) if isinstance(meta, dict) else ""
                    if not pk_tail.isdigit() and wf_name:
                        # 用户明确要求: parentName = "{流程名}.{中文label}"
                        # (如 "采购合同报备.流程ID"), **不是** "{流程名}.{paramKey}" —
                        # 前端「参数路径」按 parentName 显示, paramKey 数字会显示成
                        # "采购合同报备.<workflowId>.requestId" 而非 "采购合同报备.流程ID".
                        # label 是 plan mapping 值对象的 label (源字段中文名).
                        direct_parent = f"{wf_name}.{label or key}"
                    elif form_name:
                        #  优先用 label (源字段中文名, 如"报名人员"),
                        # 而不是裸 pkey (数字 paramKey) — 让"参数路径"显示"会议信息.报名人员"
                        # 而不是 "会议信息.<源paramKey>".
                        direct_parent = f"{form_name}.{label or pkey}"
                    else:
                        direct_parent = f"表单数据.{label or key}"
                    flat = _assign_flat_context_direct(
                        pkey, str(label or key), str(src), app_id, ft,
                        parent_name=direct_parent, meta=meta,
                    )
                    switch_t = "assign"
                else:
                    child = _assign_flat_context(
                        str(key), str(label or key), str(src), app_id, ft,
                        parent_name=parent_name, table_id=table_id,
                        component_key="Text",
                        param_key_full=pkey,
                        value_full=pval,
                    )
                    container = formula_container_string([child], app_id=app_id)
                    child_id = str(child.get("id", ""))
                    if child_id and isinstance(child.get("config"), str):
                        import json as _json
                        _cfg = _json.loads(child["config"])
                        _cfg["tempFormulaId"] = container["id"]
                        child["config"] = _json.dumps(_cfg, ensure_ascii=False)
                    child["tempFormulaId"] = container["id"]
                    _container_switch = "sub" if (detail_mode and "[]." in str(pval)) else "assign"
                    flat = {
                        "id": container["id"],
                        "name": "",
                        "value": container["value"],
                        "type": "8",
                        "fieldType": ft,
                        "formulaType": ft,
                        "applicationId": str(app_id) if app_id else "",
                        "childs": container["childs"],
                        "config": {
                            "paramType": ft, "switchType": _container_switch, "formulaVersion": "V1",
                        },
                    }
                    switch_t = _container_switch
        else:
            # 普通上下文引用兜底 (ActionEbAdd/Update 之外的组件, 如 ApproveCreate 的
            # mapping 字段).  必须做中文→数字 paramKey 映射 —
            # 否则 value='FormData.{中文}' 前端 cacheContext 找不到 → 字段标红
            # ("Object"/"文本" 类型不匹配). 统一走 _resolve_param_key 映射.
            # parentName 带实体名前缀 "{流程名}.{label}" 或 "{表单名}.{label}"
            # (如 "采购合同申请.合同名称" / "会议信息.开始时间") — 旧 _assign_flat_context
            # 的 parentName 是裸字段名 ( 显示"合同名称"缺前缀, 设计器"参数路径"不对).
            # 与 Add/Update 分支 (1357/1455) 同形态. 流程名优先, 表单名兜底.
            wf_id = str(meta.get("_workflow_id", "")) if isinstance(meta, dict) else ""
            pkey = _resolve_param_key(wf_id, str(key))
            _src_name = ""
            if isinstance(meta, dict):
                _src_name = str(meta.get("_upstream_workflow_name", "") or "")
                if not _src_name:
                    _src_name = str(meta.get("_upstream_form_name", "") or "")
            direct_parent = f"{_src_name}.{label or key}" if _src_name else f"表单数据.{label or key}"
            flat = _assign_flat_context_direct(
                pkey, str(label or key), str(src), app_id, ft,
                parent_name=direct_parent, meta=meta,
            )
            switch_t = "assign"
    elif kind == "system_variable":
        key = ref.get("key", "{userid}") if isinstance(ref, dict) else "{userid}"
        flat = _assign_flat_system_var(str(key), app_id, ft)
        switch_t = "assign"
    elif kind == "fixed" or kind is None:
        val = ""
        if isinstance(ref, dict):
            val = ref.get("value", "")
            if isinstance(val, dict):
                val = val.get("value", "")
        else:
            val = ref
        if not isinstance(val, (str, int, float, bool)):
            val = str(val) if val is not None else ""
        flat = _assign_flat_fixed(str(val), app_id, ft)
        #  Select 固定值 assign.name 用 label (显示名 "草稿"),
        # value 仍是 option valueKey ("0"). 前端下拉按 valueKey 命中 option 显示 name.
        if isinstance(ref, dict) and ref.get("label") is not None:
            flat["name"] = str(ref["label"])
        switch_t = "fixvalue"
    elif kind in ("constant", "transform", "formula"):
        # 复杂赋值类型回退到完整 formula bean(由 _build_assign_bean 生成)
        bean = _build_assign_bean(assignment, field_id, field_type, meta, app_id, default_source_id)
        # 整合完整的 bean 作为 assign
        flat_id = bean.get("id") or str(assign_id)
        flat = {
            k: v for k, v in bean.items()
            if k not in ("configObject", "childs", "parentId", "sortWeight", "position")
        }
        # 确保子公式不丢失
        if bean.get("childs"):
            flat["childs"] = bean["childs"]
        flat.setdefault("applicationId", str(app_id))
        flat.setdefault("id", str(flat_id))
        switch_t = "assign" if bean.get("type") != "1" else "fixvalue"
    else:
        val = ""
        if isinstance(ref, dict):
            val = ref.get("value", "")
        elif isinstance(ref, (str, int, float, bool)):
            val = ref
        flat = _assign_flat_fixed(str(val), app_id, ft)
        switch_t = "fixvalue"

    #  entry id 平台生成 (insert 模式发送时不能带 id/primaryId,
    # 对齐用户回读结构 (formFieldKey==id==primaryId).
    return {
        "formFieldKey": "",
        "value": {
            "original": False,
            "operate": operate,
            "switchType": switch_t,
            "fieldKey": str(field_id),
            "assignType": "",
            "multiSelect": False,
            "fieldType": field_type,
            "assign": flat,
            "assignId": str(assign_id),
        },
    }

# ── 核心映射 ────────────────────────────────────────────────────────────────
