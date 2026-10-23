#!/usr/bin/env python3
"""WorkflowDraft 到平台设计 JSON 的节点与拓扑编排。"""

import json
import sys
import time
from copy import deepcopy
from typing import Any, Optional

from components import get as get_component  # 从注册中心读取组件元数据
from components import get_converter  # 组件专用转换器查表

# ── 组件元数据从 scripts/components/ 注册中心读取,不在此维护 ──

# ── 元数据加载 ──────────────────────────────────────

_metadata_cache: Optional[dict] = None

def load_metadata(path: str | None = None) -> dict:
    global _metadata_cache
    if path is None:
        # 否则可能为当前账号填入不可见的表单或流程.
        return {}
    if _metadata_cache is not None:
        return _metadata_cache
    with open(path, "r", encoding="utf-8") as f:
        _metadata_cache = json.load(f)
    return _metadata_cache

from core.id_generator import gen_id
from core.update_field_mapper import build_formula_reference, build_update_field_condition
from core.calendar_mapper import _map_meeting_create, _map_schedule_create
from core.trigger_mapper import _map_date_trigger
from core.time_batch_mapper import _map_time_batch_trigger
from core.formula_service import (
    _assign_flat_context,
    _assign_flat_context_direct,
    _build_person_object,
    _build_share_list,
    _lookup_target_field_meta,
    _normalize_constant_assignment,
    _resolve_enum_constant,
    _resolve_param_key,
    _resolve_source_field_label,
    _resolve_source_field_type,
    build_person_formula,
    build_setting_entry,
    formula_context,
    formula_fixed,
    formula_fixed_for_assign_switch,
    formula_function,
)
# 平台数据 paramKey 用 "{workflowId}.{fieldId}" 数字格式,设计器据此解析字段.
from core.runtime_metadata import (
    _TARGET_DETAIL_FIELDS,
    _TARGET_FORM_FIELDS,
    _WORKFLOW_CONTEXT_FIELDS,
    find_in_metadata,
    _WORKFLOW_DETAIL_FIELDS,
    _WORKFLOW_DETAIL_NAMES,
    _WORKFLOW_FIELD_IDS,
    workflow_field_id,
)
# 不能按表单 componentKey 硬编码成 object → 前端显示 "json" 错误。
# 正确顺序:
#   1. 优先用 component-context 缓存的 paramType (_WORKFLOW_CONTEXT_FIELDS[formId][field].paramType)
#   2. 缓存缺失才 fallback componentKey → paramType 映射 (仅基础类型, 对象类字段

def map_draft_data(draft_params: dict, component_type: str,
                   meta: Optional[dict] = None, app_id: str = "",
                   action_index: int = 0, event_node_id: str = "",
                   event_name: str = "",
                   lenient: bool = False) -> dict:
    """将 Draft params 映射到真实 data 字段

    lenient=True (保底模式): 单个字段转换失败只跳过该字段, 不中断整个 action —
    用于正式链路失败后的保底保存, 保证"框架正确"的版本能落库给用户预览.
    """
    # 组件专用转换器优先。非标准 DTO 的组件在自身包内暴露 CONVERTER；未暴露的
    # 标准表单组件才进入下面的通用平铺映射。这样新增特殊组件无需修改本文件。
    converter = get_converter(component_type)
    if converter is not None:
        return converter(
            draft_params, meta=meta, app_id=app_id, action_index=action_index,
            event_node_id=event_node_id, event_name=event_name, lenient=lenient,
        )

    # 这四个内置转换与 FormulaBean/ConditionSet 的通用构造高度耦合，仍由 core
    # 持有；不再为它们保留只有一行转发的 component converter.py。新组件若有
    # 真正独立 DTO 逻辑应在组件包实现 CONVERTER。
    builtin_converter = {
        "TimeBatchTrigger": lambda: _map_time_batch_trigger(
            draft_params, meta, app_id, filter_builder=_build_filter_input
        ),
        "MeetingCreate": lambda: _map_meeting_create(draft_params, meta, app_id),
        "ScheduleCreate": lambda: _map_schedule_create(draft_params, meta, app_id),
        "DateTrigger": lambda: _map_date_trigger(
            draft_params, meta, app_id, filter_builder=_build_filter_input
        ),
    }.get(component_type)
    if builtin_converter is not None:
        return builtin_converter()

    # 兼容直接调用 prepare-context/to-real 的旧 plan；正式 generate 会在
    # normalize_node 中完成同样的别名归一，但这里不能依赖调用方一定走过编译。
    if component_type == "ApproveCreate" and isinstance(draft_params, dict) \
            and "operator" not in draft_params and "operateUser" in draft_params:
        draft_params = {**draft_params, "operator": draft_params["operateUser"]}

    comp = get_component(component_type) or {}
    mapping = comp.get("dataMapping", {})
    result = deepcopy(comp.get("defaultData", {}))

    for draft_key, real_keys in mapping.items():
        val = draft_params.get(draft_key)
        if val is None or val in ({}, [], ""):
            continue
        targets = [k.strip() for k in real_keys.split(",")]
        for t in targets:
            if t.startswith("_"):  # 特殊处理
                if lenient:
                    try:
                        _handle_special(draft_key, t, val, result, meta, app_id, action_index, event_node_id, component_type, event_name)
                    except Exception:
                        # 保底模式: 单个字段失败跳过, 不中断 action (框架保留)
                        continue
                else:
                    _handle_special(draft_key, t, val, result, meta, app_id, action_index, event_node_id, component_type, event_name)
            else:
                result[t] = val

    # _setting_main 可能在 _updateFieldCondition 之后执行；最终必须把字段匹配条件
    # 同步到 setting，后端 EbUpdateComponent.save() 会从这里持久化它。
    if component_type == "ActionEbUpdate" and isinstance(result.get("updateFieldCondition"), dict):
        result.setdefault("setting", {})["updateFieldCondition"] = deepcopy(result["updateFieldCondition"])

    if meta:
        if "_targetForm" not in mapping.values():
            _auto_target_form(result, draft_params, meta, app_id)
    if "ebActionId" not in result and component_type.startswith("ActionEb"):
            result["ebActionId"] = "-1"

    if component_type == "SendMessage":
        # McSendMsgDTO 将标题、正文反序列化为 FormulaBean
        for formula_key in ("msgContent", "msgTitle", "pcLink", "mobileLink"):
            value = result.get(formula_key)
            if isinstance(value, str):
                result[formula_key] = formula_fixed_for_assign_switch(value)
        if "msgTitle" not in result:
            result["msgTitle"] = formula_fixed_for_assign_switch("通知")
        result.setdefault("senderType", "system")
        result.setdefault("customParams", [])

    # 所有 ActionEb* 数据节点: 写入 type 字段 (平台要求)
    if component_type.startswith("ActionEb"):
        result["type"] = component_type

    # CustomTrigger: 将扁平 params 打包为嵌套 customData
    if component_type == "CustomTrigger":
        result["customData"] = {
            "formType": draft_params.get("formType", "input"),
            "appId": draft_params.get("appId", app_id or ""),
            "tableList": draft_params.get("tableList", []),
            "businessModule": draft_params.get("businessModule", ""),
            "customId": draft_params.get("customId", ""),
        }

    if component_type == "ActionEbAdd":
        # 新建节点尚未落库时,前端固定使用 -1;保存服务会分配真实动作 ID.
        result["ebActionId"] = str(result.get("ebActionId", "-1"))
        result["id"] = result["ebActionId"]
        result.setdefault("workflowFields", "")
        result["type"] = component_type
        if app_id:
            result["currentApplication"] = app_id
            result["applicationId"] = app_id

    # ActionEbDelete: 补充 nullOpflag 字段(platform 必需)
    if component_type == "ActionEbDelete":
        result["nullOpflag"] = False
        if not result.get("id"):
            result["id"] = str(result.get("ebActionId", "-1"))

    # workflowPath 在真实 JSON 中是数组,不是单个对象
    if component_type == "ApproveTrigger" and "workflowPath" in result:
        wp = result["workflowPath"]
        if isinstance(wp, dict):
            wp["workflowtype"] = wp.get("workflowtype", app_id or "")
            result["workflowPath"] = [wp]
        trigger_config = _build_approve_trigger_config(draft_params)
        if trigger_config:
            # (Map: workflowId → 配置数组), 不是 singleApproveConfig!
            # 前端 ApproveTrigger/index.tsx componentDidMount:
            #   if (!isEmpty(singleApproveConfigs)) { tempCustomData = isEmpty(singleApproveConfig)
            #     ? new Map(entries): singleApproveConfig; showIcon=true }
            #   else tempCustomData = singleApproveConfig
            # 平台结构 (采购动作流配置详情数据.json): singleApproveConfig={}, singleApproveConfigs={wfId:[config]}.
            #   singleApproveConfigs: {"<workflowId>": [{"id":"...", "objType":"pre",
            #     "executeTime":["1"], "nodeOrLinkName":[{...}], "open":true, "async":false,
            #     "readOnly":false, "hasRule":false}]}
            result["singleApproveConfig"] = {}
            wf_id = ""
            if isinstance(result.get("workflowPath"), list) and result["workflowPath"]:
                wf_id = str(result["workflowPath"][0].get("id", ""))
            result["singleApproveConfigs"] = {wf_id: trigger_config} if wf_id else {}

    # ActionEbUpdate with opType=id: 平台要求 updateId 必填
    if component_type == "ActionEbUpdate" and result.get("opType") == "id" and "updateId" not in result:
        result["updateId"] = {
            "frontId": draft_params.get("targetForm", {}).get("id", app_id or ""),
            "configObject": {"paramKey": app_id or "", "formulaVersion": "V1"},
            "formulaType": "string",
            "name": draft_params.get("targetForm", {}).get("name", ""),
            "id": draft_params.get("targetForm", {}).get("id", app_id or ""),
        }

    return result

from core.approve_trigger_config import _build_approve_trigger_config
from core.filter_rules import (
    _build_filter_context_formula,
    _condition_field_family,
    _condition_operator_override,
    _filter_field_type,
    _formula_config_object,
    _normalize_filter_operator,
    _resolve_form_ctx,
)

def _build_setting_detail(node_data: dict, detail_items: list, meta: dict,
                          app_id: str, event_id: str, node_type: str) -> None:
    """明细表字段赋值 → setting.detail (真实结构实证 300 个含 detail 的动作).

    真实 detail 结构:
      [{
        "detailTableId": "<明细表id>",
        "data": { "<明细字段id>": build_setting_entry(...) },   # 与 main 同构
        "deleteFields": [...],           # 可选
        "operateType": "insert|updateData|delete",  # 可选
        "updateFieldCondition": {...},   # 可选
        "basisValue": [...],             # 可选
      }]
    """
    if not isinstance(detail_items, list):
        return
    detail_out: list[dict[str, Any]] = []
    for item in detail_items:
        if not isinstance(item, dict) or not item.get("detailTableId"):
            continue
        ele: dict[str, Any] = {"detailTableId": str(item["detailTableId"])}
        # (真实结构 {"updateField": []}) — 后端 formDataUtil.saveFormData 处理
        # detail 时无 null 保护，缺失会导致平台 500 "保存动作流异常"。
        #  detail 更新 (operateType=updateData) 支持 plan 传
        # updateFieldCondition 定位明细行 (如"来源流程明细ID=流程明细rowId"),
        if isinstance(item.get("updateFieldCondition"), dict):
            ele["updateFieldCondition"] = build_update_field_condition(
                item["updateFieldCondition"], meta=meta, app_id=app_id,
                event_id=str(event_id), component_type=node_type,
            )
        else:
            ele["updateFieldCondition"] = {"updateField": []}
        # data: 与 setting.main 相同的赋值结构
        ele_data: dict[str, Any] = {}
        # source=event 节点 id, parentName='<上游表单名>.<明细表名>[]'). UI 采购明细 tab 的
        # 「依据值」控件 + 依据值下级菜单都依赖此字段; 缺失则设计器打开后明细表依据值为空.
        if isinstance(item.get("basisValue"), dict):
            bv_val = item["basisValue"]
            bv_key = str(bv_val.get("paramKey") or bv_val.get("key") or "").strip()
            bv_label = str(bv_val.get("label") or bv_val.get("name") or bv_key)
            if bv_key:
                # 明细项的依据值同样引用整个明细表，必须使用实时 context 的
                bv_type = _resolve_source_field_type(bv_key, meta)
                #  父名前缀 — 流程名优先 (ApproveTrigger),
                # 表单名兜底 (DateTrigger/EventFormData), 全空则用标签.
                _prefix = ""
                if isinstance(meta, dict):
                    _prefix = str(meta.get("_upstream_workflow_name", "") or "")
                    if not _prefix:
                        _prefix = str(meta.get("_upstream_form_name", "") or "")
                parent_name = f"{_prefix}.{bv_label}[]" if _prefix else f"{bv_label}[]"
                #  frontId 必须 = 明细表 id (paramKey 提取, 如
                # '{workflowId}.{明细表id}[]' → <明细表id>)!
                # 前端 getSubBaseData 用 getAllChild(tableData, frontId) 找
                # 「依据值下级」下拉只有 esbAssignSelf (对照: main basisValueFormula.frontId
                # 展开不了的真根因, comType/fieldInfo 是辅助, frontId 才是决定性的).
                bv_subform_id = str(bv_key).rsplit("[]", 1)[0].rsplit(".", 1)[-1] if "[]" in str(bv_key) else str(bv_key)
                ele["basisValue"] = {
                    "frontId": bv_subform_id,
                    "formulaType": bv_type,
                    "name": bv_label,
                    "id": str(gen_id()),
                    "source": str(event_id),
                    "type": "3",
                    "value": f"FormData.{bv_key}",
                    "childs": [],
                    "config": {
                        "paramKey": bv_key,
                        "paramType": bv_type,
                        "isMultCom": False,
                        "switchType": "assign",
                        "parentName": parent_name,
                        "multName": "",
                        "multKey": "",
                        #  补 multTypeObj — 前端「依据值下级」展开
                        # 弹窗依据 (与子字段同构: allName=明细表名, currentName=明细表名,
                        # → 设计器弹窗只显示"全部", 找不到明细表子字段.
                        "multTypeObj": {
                            "allName": parent_name,
                            "currentName": parent_name,
                            "currentParamKey": f"FormData.{bv_key}",
                            "allParamKey": f"FormData.{bv_key}",
                        },
                        "comId": str(event_id),
                        #  补 comType='ApproveTrigger' — 前端
                        # getDetailChildData/cacheContext 靠 comType 识别上下文类型去取流程表单 FormData
                        # (缺则「依据值下级」下拉只剩 esbAssignSelf, 取不到明细表子字段;
                        # 验证: main.basisValueFormula.config 有 comType='ApproveTrigger', detail 没有).
                        "comType": "ApproveTrigger",
                        "newParentName": parent_name,
                        #  补 fieldInfo — 前端 getDetailChildData
                        # 展开明细表子字段靠 fieldInfo.tablePrimaryKey='FormData' 识别上下文
                        # (缺则「依据值下级」下拉只有 esbAssignSelf, 没有明细表子字段;
                        # 验证: 补上后 detail 弹窗可展开"收货明细[]"的下级如"物料名称").
                        "fieldInfo": {
                            "paramKey": bv_key,
                            "tablePrimaryKey": "FormData",
                        },
                    },
                    "parentId": "0",
                }
        mapping = item.get("mapping") or {}
        constants = item.get("constants") or {}
        if isinstance(mapping, dict):
            for source_key, target_field_id in mapping.items():
                operate = "OPERATE_EQUAL"
                #: 明细映射值支持对象 {target,paramKey,label,detailLabel}
                if isinstance(target_field_id, dict):
                    raw = str(target_field_id.get("target") or target_field_id.get("fieldId") or "")
                    if not raw:
                        raise ValueError(
                            f"detail.mapping 依据值下级值缺少目标字段 id: "
                            f"应传 {{'target':'<目标明细字段id>', 'paramKey':'<源paramKey>', ...}}"
                        )
                    if raw.startswith("+"):
                        operate = "OPERATE_PLUS"; raw = raw[1:]
                    elif raw.startswith("-"):
                        operate = "OPERATE_MINUS"; raw = raw[1:]
                    ref_key = str(target_field_id.get("paramKey") or source_key)
                    ref_label = str(target_field_id.get("label") or source_key)
                    ref_detail = str(target_field_id.get("detailLabel") or "")
                    assignment = {"kind": "context", "paramKey": ref_key, "label": ref_label}
                    if ref_detail:
                        assignment["detailLabel"] = ref_detail
                else:
                    raw = str(target_field_id)
                    if raw.startswith("+"):
                        operate = "OPERATE_PLUS"; raw = raw[1:]
                    elif raw.startswith("-"):
                        operate = "OPERATE_MINUS"; raw = raw[1:]
                    assignment = {
                        "kind": "context", "paramKey": str(source_key),
                        "label": _resolve_source_field_label(str(source_key), meta, str(source_key)),
                    }
                ele_data[raw] = build_setting_entry(
                    raw, assignment,
                    meta=meta, app_id=app_id, default_source_id=event_id,
                    operate=operate, component_type=node_type,
                    #  detail 字段映射**一律 type=8 容器包 type=3**
                    # data 字段映射仍是 switchType=assign + assign.type=8 容器 (child.type=3,
                    # value='FormData.{wfId}.{明细表id}[].{子字段id}').
                    # 20:04 曾改 "有 basisValue 走 type=10 直连" → 平台保存 detail 时
                    detail_mode=True,
                )
        if isinstance(constants, dict):
            for target_field_id, value in constants.items():
                tfid = str(target_field_id)
                assignment, ft = _normalize_constant_assignment(value, default_field_type="Text")
                ele_data[tfid] = build_setting_entry(
                    tfid, assignment, field_type=ft, meta=meta, app_id=app_id,
                    default_source_id=event_id, component_type=node_type,
                    detail_mode=True,
                )
        #  detail 自动按名补全 (方案A) — plan 未显式配置的目标
        # 明细表字段, 按"目标字段名 = 源明细表字段名"自动补 mapping (type=8 容器包
        # type=3, detail_mode). 显式配置的字段优先, 不覆盖. 源明细表 = item.basisValue
        # 引用的流程明细表 (paramKey '{wfId}.{明细表id}[]'); 数据来自 preflight 缓存的
        # _WORKFLOW_DETAIL_FIELDS (流程明细表子字段) + _TARGET_DETAIL_FIELDS (目标明细表字段).
        _target_form_id = str((node_data.get("targetForm") or {}).get("id", "")) if isinstance(node_data, dict) else ""
        _auto_fill_detail_mapping(
            ele_data, item, _target_form_id, meta, app_id, event_id, node_type,
        )
        if ele_data:
            ele["data"] = ele_data
        else:
            ele["data"] = {}
        if item.get("deleteFields"):
            ele["deleteFields"] = item["deleteFields"]
        if item.get("operateType"):
            ele["operateType"] = item["operateType"]
        else:
            #  默认补 operateType='insert' — 前端 CustomMain useEffect
            # (CustomMain.tsx:82) 有 `if (!operateType && !isBasisValChange) return;`,
            # detail item 没有 operateType → useEffect 不跑 → type 永远默认 MenuType.Assign
            # ("动态赋值") → 控件标签错. 默认设 insert 让 useEffect 跑 → getDftType 看到
            # value.assign.config.switchType='sub' → Sub ("依据值下级").
            ele["operateType"] = "insert"
        if item.get("updateFieldCondition") and isinstance(item["updateFieldCondition"], dict):
            ele["updateFieldCondition"] = item["updateFieldCondition"]
        detail_out.append(ele)
    if detail_out:
        node_data["setting"]["detail"] = detail_out

def _auto_fill_detail_mapping(ele_data: dict, item: dict, target_form_id: str,
                              meta: dict, app_id: str, event_id: str,
                              node_type: str) -> None:
    """detail 映射自动按名补全 .

    目标明细表字段未在 plan mapping/constants 显式配置时, 按字段名匹配
    源明细表 (item.basisValue 引用的流程明细表) 的同名字段, 自动补 type=8
    容器包 type=3 映射. 显式配置的字段不覆盖.
    """
    if not isinstance(item, dict) or not item.get("detailTableId"):
        return
    bv_val = item.get("basisValue")
    if not isinstance(bv_val, dict):
        return
    bv_key = str(bv_val.get("paramKey") or bv_val.get("key") or "").strip()
    bv_label = str(bv_val.get("label") or bv_val.get("name") or "")
    if not bv_key or "[]" not in bv_key:
        return
    wf_id = str(meta.get("_workflow_id", "")) if isinstance(meta, dict) else ""
    subform_id = str(bv_key).rsplit("[]", 1)[0].rsplit(".", 1)[-1]
    # 目标明细表字段: _TARGET_DETAIL_FIELDS[formId][detailTableId]
    target_fields = (_TARGET_DETAIL_FIELDS.get(str(target_form_id), {}).get(str(item["detailTableId"]), {})
                     if target_form_id else {})
    # 源明细表字段: _WORKFLOW_DETAIL_FIELDS[workflowId][subFormId] {name: paramKey}
    source_fields = _WORKFLOW_DETAIL_FIELDS.get(wf_id, {}).get(subform_id, {})
    if not target_fields or not source_fields:
        return
    for tid, tmeta in target_fields.items():
        tid_s = str(tid)
        if tid_s in ele_data:
            continue  # 显式配置优先, 不覆盖
        tname = str(tmeta.get("name") or tmeta.get("showName") or "")
        if not tname or tname not in source_fields:
            continue
        src_pk = source_fields[tname]
        assignment = {"kind": "context", "paramKey": src_pk, "label": tname}
        if bv_label:
            assignment["detailLabel"] = bv_label
        ele_data[tid_s] = build_setting_entry(
            tid_s, assignment,
            field_type=str(tmeta.get("componentKey") or tmeta.get("type") or "Text"),
            meta=meta, app_id=app_id, default_source_id=event_id,
            component_type=node_type, detail_mode=True,
        )

def _handle_special(draft_key: str, special: str, val, result: dict,
                    meta, app_id: str, idx: int, event_id: str,
                    component_type: str = "", event_name: str = "") -> None:
    """处理 _person / _targetForm / _setting_main 等特殊映射"""
    if special == "_person" and isinstance(val, dict):
        if component_type == "SendMessage":
            # SendMessage 接收人走 shareList, 不设 person
            return
        #  数据动作 (Add/Update/Delete/EnquiryForm) person 直连无容器;
        # MeetingCreate/ApproveCreate 不走 _person (有独立 special)
        result["person"] = build_person_formula(val, meta, app_id, direct_person=True)
    elif special == "_targetForm" and isinstance(val, dict):
        _fill_target_form(result, val, meta, app_id)
    elif special in ("_updateId", "_basisValueFormula"):
        #  updateId (按数据ID更新) 用 type=3 直连 — ApprovalData
        # 字段 (requestId 等) 需要 ApprovalData 前缀/tableName=流程数据/frontId=真实id,
        # 通用公式引用没有该直连分支，避免落为错误的 FormData.requestId。
        # 错前缀 → 设计器标"已删除"/运行时找不到. basisValueFormula (batchInsert 依据值)
        # 仍是 FormData.{wfId}.{明细表id}[] 语义, 保持 formula_context.
        if special == "_updateId":
            wf_id = str((meta or {}).get("_workflow_id", "")) if isinstance(meta, dict) else ""
            if isinstance(val, dict) and (val.get("kind") == "context" or val.get("key") or val.get("paramKey")):
                key = str(val.get("paramKey") or val.get("key") or val.get("fieldKey") or "")
                resolved = _resolve_param_key(wf_id, key)
                label = str(val.get("label") or val.get("name") or key)
                #  parentName 必须拼中文 label (如 "合同信息审核.数据ID"),
                # 仅流程名会缺后缀 — 前端「参数路径」按 parentName 显示.
                #  表单类事件 (EventFormData/DateTrigger/TimeBatchTrigger)
                # 无流程名 → 必须兜底 _upstream_form_name (如 "会议报名.会议名称"), 与
                # mapping/operator 的 direct_parent 规则一致, 否则参数路径缺前缀.
                _wf_name = str(meta.get("_upstream_workflow_name", "")) if isinstance(meta, dict) else ""
                if not _wf_name:
                    _wf_name = str(meta.get("_upstream_form_name", "")) if isinstance(meta, dict) else ""
                _pn = f"{_wf_name}.{label}" if _wf_name else label
                result["updateId"] = _assign_flat_context_direct(
                    resolved, label, str(event_id or val.get("source") or "0"), app_id,
                    parent_name=_pn,
                    meta=meta,
                )
            else:
                result["updateId"] = build_formula_reference(
                    val, meta=meta, app_id=app_id, event_id=event_id,
                    component_type=component_type,
                )
        else:
            result[special[1:]] = build_formula_reference(
                val, meta=meta, app_id=app_id, event_id=event_id,
                component_type=component_type,
            )
    elif special == "_updateFieldCondition":
        condition = build_update_field_condition(
            val, meta=meta, app_id=app_id, event_id=event_id,
            component_type=component_type,
        )
        result["updateFieldCondition"] = condition
        # 后端保存表单数据时从 setting 读取这份条件；不能只放在顶层。
        result.setdefault("setting", {})["updateFieldCondition"] = deepcopy(condition)
        result["updateCondition"] = [
            str(item.get("fieldKey")) for item in condition.get("updateField", [])
            if isinstance(item, dict) and item.get("fieldKey")
        ]
    elif special == "_setting_main":
        _fill_setting(result, updates=val, meta=meta, app_id=app_id, event_id=event_id,
                      component_type=component_type)
    elif special == "_setting_mapping":
        result.setdefault("_pending_mapping", {})
        if isinstance(val, dict):
            result["_pending_mapping"].update(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    result["_pending_mapping"].update(item)
    elif special in ("_setting_constants", "_setting_formula"):
        pending_key = "_pending_constants" if special == "_setting_constants" else "_pending_formula"
        result.setdefault(pending_key, {})
        if isinstance(val, dict):
            result[pending_key].update(val)
    elif special == "_basisValue":
        # 批量新增(对多)的依据值 → data.basisValue(明细表id) + basisValueFormula(引用明细字段公式).
        # 真实契约:
        #   basisValue=<明细表id>
        #   basisValueFormula={type:3, value:'FormData.{wfId}.{明细表id}[]',
        #     config:{paramKey:'{wfId}.{明细表id}[]', isMultCom, comType, switchType, fieldInfo,
        #             multTypeObj, comId, parentName, newParentName...}}
        #   setting 必须同步带 bassisValueId + bassisValue (注意拼写 bassis 非 basis,
        if isinstance(val, dict):
            bv_key = str(val.get("paramKey") or val.get("key") or val.get("value") or "").strip()
            bv_label = str(val.get("label") or val.get("name") or "")
            #  明细表真实名称优先从 preflight 缓存取 (组件上下文
            # FormData 组 '{wfId}.{subFormId}[]' 条目的 showName, 如 "付款条件").
            # plan 手写 label 可能错名 ("付款条件明细"≠真实"付款条件") → parentName 名错
            # 且无前缀 → 设计器依据值弹窗显示"全部". plan label 仅兜底.
            if bv_key:
                _bk_head, _, _bk_tail = bv_key.rpartition(".")
                _real_name = _WORKFLOW_DETAIL_NAMES.get(_bk_head, {}).get(_bk_tail.rstrip("[]"), "")
                if _real_name:
                    bv_label = _real_name
            if not bv_label:
                bv_label = bv_key
            if bv_key:
                # basisValue: 明细表 id — 从 paramKey 尾部取 (去掉 {wfId}. 前缀和 [] 后缀)
                tail = bv_key.rsplit(".", 1)[-1].rstrip("[]")
                bv_id = tail if tail.isdigit() else bv_key
                result["basisValue"] = bv_id
                # basisValueFormula: type=3 上下文引用 + 完整 config (对照真实保存回读)
                # source/config.comId 必须是上游 event 节点 id (如 "196298609848562"),
                # 前端 AssignSwitch 靠它定位 ApproveTrigger 拿明细表字段定义展开"依据值下级".
                # 空值 → 前端找不到上游 → 映射里选不了下级 .
                f_id = str(gen_id())
                f_biz = str(gen_id())
                src_id = str(event_id) if event_id else str(meta.get("_upstream_node_id", "")) if isinstance(meta, dict) else ""
                #  依据值引用明细表整体, parentName 系列 = '{流程名}.{明细表名}[]'
                # 设计器依据值弹窗显示"全部"/无法定位.
                _wn_bv = str(meta.get("_upstream_workflow_name", "")) if isinstance(meta, dict) else ""
                _bv_parent = f"{_wn_bv}.{bv_label}[]" if _wn_bv else f"{bv_label}[]"
                # `basisValueFormula` 引用的是明细表整体，真实 context 的
                # paramType 为 json。不得沿用过去写死的 string，否则前端和
                # assignment audit 都会把它判为类型不一致。
                bvf_type = _resolve_source_field_type(bv_key, meta)
                bvf_config = {
                    "paramKey": bv_key,
                    "isMultCom": False,
                    "comType": "ApproveTrigger",
                    "switchType": "assign",
                    "parentComId": 0,
                    "formulaVersion": "V1",
                    "fieldInfo": {"paramKey": bv_key, "tablePrimaryKey": "FormData"},
                    "tableName": "表单数据",
                    "paramType": bvf_type,
                    "parentName": _bv_parent,
                    "multName": "", "multKey": "",
                    "multTypeObj": {
                        "allName": _bv_parent, "currentName": _bv_parent,
                        "currentParamKey": f"FormData.{bv_key}",
                        "allParamKey": f"FormData.{bv_key}",
                    },
                    "comId": src_id,
                    "newParentName": _bv_parent,
                }
                bvf = {
                    "frontId": bv_id,
                    "formulaType": bvf_type,
                    "name": bv_label,
                    "businessId": f_biz,
                    "id": f_id,
                    "source": src_id,
                    "type": "3",
                    "value": f"FormData.{bv_key}",
                    "childs": [],
                    "config": bvf_config,
                    "parentId": "0",
                }
                result["basisValueFormula"] = bvf
                # setting 同步 bassisValueId/bassisValue .
                # 用 _pending_basis 延迟合并 — 不能提前创建 setting, 否则 3236 行
                # "setting not in node_data" 为 False → _fill_setting 跳过 → main 缺失.
                result["_pending_basis"] = {"bassisValueId": bv_id, "bassisValue": deepcopy(bvf)}
    elif special == "_setting_detail":
        # 明细表字段赋值: detail 数组 → _pending_detail
        # 每个元素 {detailTableId, mapping, constants, deleteFields, operateType}
        result.setdefault("_pending_detail", [])
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and item.get("detailTableId"):
                    result["_pending_detail"].append(item)
    elif special == "_customData":
        # 将 Draft 的扁平 params 打包为 real JSON 的嵌套 customData
        result["customData"] = {
            "formType": val.get("formType", val.get("customData", {}).get("formType", "input") if isinstance(val.get("customData"), dict) else "input"),
            "appId": val.get("appId", app_id or ""),
            "tableList": val.get("tableList", []),
            "businessModule": val.get("businessModule", ""),
            "customId": val.get("customId", val.get("id", "")),
        }
    elif special == "_filterInput":
        # 筛选条件对应按条件更新。
        if component_type == "ActionEbUpdate" and isinstance(val, dict) and val:
            result["opType"] = "updateData"
        result["filterInput"] = _build_filter_input(
            result, val, meta, app_id, component_type=component_type)
    elif special == "_bizWorkflowPath" and isinstance(val, dict):
        # ApproveCreate 新建流程: workflowPath 是数组, 元素对齐真实结构
        # (平台数据 14 条: bridgeService='ebuilder'/relateFormTypes=['WEA_EBUILDER']/
        #  name/formIds=[表单id]/id/workflowtype=流程类型id)
        wf_id = str(val.get("id", ""))
        form_ids = val.get("formIds")
        if not isinstance(form_ids, list):
            form_ids = [str(val.get("formId", val.get("objId", "")))] if val.get("formId", val.get("objId")) else []
        result["workflowPath"] = [{
            "bridgeService": "ebuilder",
            "relateFormTypes": ["WEA_EBUILDER"],
            "name": str(val.get("name") or val.get("text") or ""),
            "formIds": [str(x) for x in form_ids if x],
            "id": wf_id,
            "createFlowId": str(val.get("createFlowId") or wf_id),
            "workflowtype": str(val.get("workflowtype", val.get("workflowType", app_id or ""))),
        }]
    elif special == "_bizRequestName":
        # 请求名称: 支持字符串或 context 引用; 平台用 formula bean
        if isinstance(val, str) and val.strip():
            result["requestName"] = formula_fixed_for_assign_switch(val)
        elif isinstance(val, dict):
            wf_id = str((meta or {}).get("_workflow_id", ""))
            rq_key = _resolve_param_key(wf_id, str(val.get("key", val.get("value", ""))))
            result["requestName"] = formula_context("", rq_key,
                                                    name=str(val.get("label", "")))
    elif special == "_bizOperateUser" and isinstance(val, dict):
        # ApproveCreate 新建流程的发起人: operator 公式 bean (真实字段名是 operator)
        result["operator"] = build_person_formula(val, meta, app_id)
    elif special == "_meetingOperators" and isinstance(val, dict):
        # MeetingCreate 新建会议的创建人: operators 公式 bean
        result["operators"] = build_person_formula(val, meta, app_id)
    elif special == "_dateDataSource" and isinstance(val, dict):
        # DateTrigger 数据源 (真实结构: isPhysical/groupId/id/text/type/physical)
        ds_id = str(val.get("id") or val.get("tableId") or val.get("sourceId", ""))
        result["dataSource"] = {
            "isPhysical": True,
            "physical": True,
            "groupId": str(val.get("groupId", val.get("appId", "-98"))),
            "id": ds_id,
            "text": str(val.get("text") or val.get("name") or ""),
            "type": str(val.get("type", "FORM")),
        }

def _auto_target_form(result: dict, params: dict, meta: dict, app_id: str) -> None:
    """自动补全 targetForm/tableType/appType"""
    tf = params.get("targetForm")
    if not tf or not isinstance(tf, dict): return
    _fill_target_form(result, tf, meta, app_id)

def _fill_target_form(result: dict, tf: dict, meta: dict, app_id: str) -> None:
    form = find_in_metadata(meta, "forms", tf)
    # Semantic plan may use API-native aliases (appId/tableId), while the
    # designer DTO requires groupId/id/text. Normalize at the converter
    # boundary as well, so direct compile/to-real calls cannot produce an
    # empty targetForm/tableType shell when preflight is skipped.
    fid = form["id"] if form else tf.get("id") or tf.get("tableId", "")
    # e-builder 前端对象使用 text;目录接口的 name 只在这里转换一次.
    # 最终 targetForm 不写入 name.
    form_ref = form or tf
    form_text = form_ref.get("text") or form_ref.get("name", "")
    form_app_id = (form or tf).get("groupId", (form or tf).get("appId", ""))
    # targetForm/appType 属于 e-builder 应用;app_id 则是当前动作流应用,
    # 两者不能混用,否则会把表单挂到错误的 e-builder 应用下.
    # 注意: 不能用动作流 app_id 兜底 —— 平台会把不匹配的 groupId 存成 -1,
    # 设计器显示"表单都没选". 缺 groupId 时宁可保留空, 由 preflight 回填.
    resolved_app_id = form_app_id or fid
    group_name = form_ref.get("groupName", form_text)
    # API save 格式需要 targetForm (DB 导出版没有)
    result["targetForm"] = {
        "groupName": group_name, "groupId": resolved_app_id,
        "id": fid, "text": form_text, "type": "FORM",
    }
    result["tableType"] = [{"name": form_text, "id": fid}]
    result["appType"] = [{"pcUrl": f"/ebdapp/view/{resolved_app_id}", "name": group_name, "id": resolved_app_id}]
    result["dataSource"] = {"groupId": resolved_app_id, "id": fid, "text": form_text, "type": "FORM"}
    result["appId"] = resolved_app_id
    result["objId"] = fid
    if app_id:
        result["currentApplication"] = app_id
        result["applicationId"] = app_id

def _fill_setting(result: dict, updates=None, mapping=None, constants=None, formula=None,
                  meta: dict = None, app_id: str = "", event_id: str = "",
                  event_name: str = "",
                  component_type: str = "") -> None:
    """将 Draft updates/setting 数组转为 setting.main 结构.

    支持四种赋值来源(按优先级):
      1. mapping:  {"源字段Key":"目标字段ID"} → 上下文引用 assign
      2. constants:{"目标字段ID":"固定值"}     → 固定值 assign
      3. formula:  {"目标ID":{"op":"add/sub/mul/div","fields":["src1","src2"]}} → type=6
      4. updates:  [{"field":..., "assign":...}] → 兼容旧格式

    mapping 的目标字段 ID 支持 +/- 前缀:
      "目标ID"   → OPERATE_EQUAL
      "+目标ID"  → OPERATE_PLUS  (累加,仅 update)
      "-目标ID"  → OPERATE_MINUS (扣减,仅 update)
    """
    if meta is None:
        meta = {}
    main = {}
    # 1) updates 数组
    if isinstance(updates, list):
        for u in updates:
            if not isinstance(u, dict): continue
            field = u.get("field", u.get("formField", u.get("fieldId", gen_id())))
            fid, field_type = field, "Text"
            if isinstance(field, dict):
                fid = field.get("id", field.get("key", gen_id()))
                source_type = field.get("type", "")
                field_type = {"String":"Text","string":"Text","Number":"NumberComponent","number":"NumberComponent"}.get(source_type, source_type or "Text")
            main[str(fid)] = build_setting_entry(
                str(fid), u, field_type=field_type, meta=meta, app_id=app_id,
                default_source_id=str(event_id), component_type=component_type,
            )
    # 2) mapping
    if isinstance(mapping, dict):
        for source_key, target_field_id in mapping.items():
            operate = "OPERATE_EQUAL"
            #  mapping 值可传对象 (依据值下级):
            #   {"target":"<目标字段id>", "paramKey":"<源paramKey>", "label":"<子字段名>", "detailLabel":"<明细表名>"}
            # 或 {"paramKey","label","detailLabel"} + 目标 id 作为外层 key.
            if isinstance(target_field_id, dict):
                #  mapping 值对象支持系统变量
                # {"target":"<目标字段id>", "systemValue":"currentUser"} → type=9 {userid}
                # (ApproveCreate 无 constants 参数, 系统变量赋值走 mapping 值).
                if target_field_id.get("systemValue"):
                    _sv_key = str(target_field_id["systemValue"])
                    _sys_var = _SYSTEM_VALUE_ALIASES.get(_sv_key, _sv_key)
                    tfid = str(target_field_id.get("target") or "")
                    if not tfid:
                        raise ValueError(
                            f"mapping 系统变量值缺少目标字段 id: "
                            f"应传 {{'target':'<目标字段id>', 'systemValue':'currentUser'}}"
                        )
                    main[tfid] = build_setting_entry(
                        tfid, {"kind": "system_variable", "key": _sys_var},
                        field_type="Text", meta=meta, app_id=app_id,
                        default_source_id=str(event_id), component_type=component_type,
                    )
                    continue
                raw = str(target_field_id.get("target") or target_field_id.get("fieldId") or "")
                if not raw:
                    # 外层 key 是目标字段 id (source_key 是 dict 时取外层 key 需在 items 处处理;
                    # 此处 source_key 若是 '{明细表}[].{子字段}' 则 target 缺失 → 报错)
                    raise ValueError(
                        f"ActionEbAdd.mapping 依据值下级值缺少目标字段 id: "
                        f"应传 {{'target':'<目标字段id>', 'paramKey':'<源paramKey>', ...}}"
                    )
                if raw.startswith("+"): operate = "OPERATE_PLUS"; raw = raw[1:]
                elif raw.startswith("-"): operate = "OPERATE_MINUS"; raw = raw[1:]
                ref_key = str(target_field_id.get("paramKey") or source_key)
                ref_label = str(target_field_id.get("label") or _resolve_source_field_label(ref_key, meta, str(source_key)))
                ref_detail = str(target_field_id.get("detailLabel") or "")
                assignment = {"kind": "context", "paramKey": ref_key, "label": ref_label}
                if ref_detail:
                    assignment["detailLabel"] = ref_detail
            else:
                raw = str(target_field_id)
                if raw.startswith("+"): operate = "OPERATE_PLUS"; raw = raw[1:]
                elif raw.startswith("-"): operate = "OPERATE_MINUS"; raw = raw[1:]
                ref_key = str(source_key)
                assignment = {
                    "kind": "context",
                    "paramKey": ref_key,
                    "label": _resolve_source_field_label(ref_key, meta, ref_key),
                }
            # (约束设计器右侧"字段类型"列是真实分类, 硬编码 Text 导致日期/人员
            # 字段渲染错). _resolve_source_field_type 从 _TARGET_FORM_FIELDS 缓存查.
            _src_param_key = (assignment.get("paramKey") or str(source_key)
                              if isinstance(assignment, dict) else str(source_key))
            _src_ft = _resolve_source_field_type(_src_param_key, meta)
            main[raw] = build_setting_entry(
                raw, assignment,
                field_type=_src_ft, meta=meta, app_id=app_id,
                default_source_id=str(event_id), operate=operate, component_type=component_type,
            )
    # 3) constants
    # 多种值形态都支持(向后兼容, 默认走 fixed):
    #   - 简单字符串:  47659...: "5"                  → 固定值, fieldType=Text
    #   - 带类型:      47659...: {"value":"5", "valueType":"integer"}
    #                                                       → 固定值, fieldType=integer
    #   - 系统变量:    47659...: {"systemValue":"currentUser"}
    #                                                       → type=9 {userid} 上下文
    if isinstance(constants, dict):
        for target_field_id, value in constants.items():
            tfid = str(target_field_id)
            #  constants 支持 +/- 前缀做累加/扣减 (如 "+1" → 报名人数累加1).
            operate_c = "OPERATE_EQUAL"
            raw_v = value
            if isinstance(value, str) and len(value) > 1 and value[0] in "+-":
                operate_c = "OPERATE_PLUS" if value[0] == "+" else "OPERATE_MINUS"
                raw_v = value[1:]
            field_meta = _lookup_target_field_meta(tfid, result)
            raw_v = _resolve_enum_constant(raw_v, field_meta)
            assignment, ft = _normalize_constant_assignment(
                raw_v, default_field_type="Text",
            )
            main[tfid] = build_setting_entry(
                tfid, assignment,
                field_type=ft, meta=meta, app_id=app_id,
                default_source_id=str(event_id), operate=operate_c,
                component_type=component_type,
            )
    # 4) formula: type=6 数学运算
    if isinstance(formula, dict):
        for target_field_id, fspec in formula.items():
            if not isinstance(fspec, dict): continue
            op = fspec.get("op", "add")
            fields = fspec.get("fields", [])
            if not fields: continue
            fn_info = _get_formula_fn(op)
            childs = []
            for fld in fields:
                child = _assign_flat_context(
                    str(fld), str(fld), str(event_id), app_id, "double"
                )
                child["position"] = str(gen_id())
                child["paramType"] = "double"
                child["componentKey"] = "Number"
                child["fieldType"] = "number"
                childs.append(child)
            bean = formula_function(
                fn_info["fnId"], name=fn_info["name"], childs=childs,
                field_type="double", excel_func=op,
                function_type=fn_info.get("functionType","operation"),
                detail=fn_info.get("detail",[]), app_id=app_id,
            )
            flat_id = bean.get("id") or str(gen_id())
            assign = {k:v for k,v in bean.items() if k not in ("configObject","childs","parentId","sortWeight","position")}
            if bean.get("childs"): assign["childs"] = bean["childs"]
            assign.setdefault("applicationId", str(app_id))
            assign.setdefault("id", str(flat_id))
            main[str(target_field_id)] = {
                "formFieldKey": "",
                "value": {
                    "original": False,
                    "operate": "OPERATE_EQUAL",
                    "switchType": "assign",
                    "fieldKey": str(target_field_id),
                    "assignType": "",
                    "multiSelect": False,
                    "fieldType": "NumberComponent",
                    "assign": assign,
                    "assignId": str(flat_id),
                },
            }
    #  batchInsert 批量新增的 main 必须覆盖目标表单全部字段
    # 用 _TARGET_FORM_FIELDS 补全未赋值的字段为空 entry.
    #  空 entry 的 formFieldKey 也必须为 "" (与映射 entry 一致,
    # 否则后端走 initUpdate() 分支 main 不入库, 见 build_setting_entry type=10 分支注释).
    if component_type == "ActionEbAdd" and result.get("opType") == "batchInsert":
        tf_id = str((result.get("targetForm") or {}).get("id", ""))
        tff = _TARGET_FORM_FIELDS.get(tf_id, {}) if tf_id else {}
        for fid, fmeta in tff.items():
            fid_s = str(fid)
            if fid_s in main:
                continue
            ftype = str(fmeta.get("fieldType") or fmeta.get("type") or "Text")
            main[fid_s] = {
                "formFieldKey": "",
                "value": {
                    "original": False,
                    "operate": "OPERATE_EQUAL",
                    "fieldKey": fid_s,
                    "multiSelect": False,
                },
            }
    result["setting"] = {
        "opType": result.get("opType", "insert"),
        "updatePolicy": result.get("updatePolicy", "ALL"),
        "dataDrWithCalc": False,
        "main": main,
        "detail": [],
        "updateFieldCondition": {"updateField": []},
    }

# 语义运算符 -> 平台 ConditionSet func(后端算子名)
def _build_filter_input(result: dict, val, meta: dict, app_id: str,
                        component_type: str = "") -> dict:
    """生成 ConditionSet 真实 filterInput 结构.

    平台 ActionEbUpdate/ActionEbDelete 的"更新/删除条件"由 @weapp/components 的
    ConditionSet 跨端组件渲染,其 value 结构为:
      { isNewFilter, isParent, datas:[{ isParent, fieldName(=fieldId), formInfo,
        type:"condition", id(=fieldId), text, conditions:{func,value}, fieldType,
        compType, config, sformId, key, ... }], parentNode, relationship }
    早期实现用了错误 shape(fieldKey/operator/value + 扁平 datas),导致设计器
    无法解析、渲染空白"请选择目标字段".此处改为真实结构.
    """
    component_type = str(component_type or "")
    # EventFormData 的设计器没有传 supportEsbAssign/esbAssign；它的条件右侧
    # 只能是表单自身控件支持的固定值，不能复用 Update/Delete 的上下文公式。
    # 这是一项组件差异，不是 ConditionSet 的全局规则。
    event_local_filter = component_type == "EventFormData"

    if isinstance(val, dict):
        # 兼容三种格式:
        # 1. {condition: {field, operator, value}}  (semantic plan)
        # 2. {conditions: [{left, operator, right}, ...]}
        # 3. {left, operator, right} (单条件)
        if "condition" in val and isinstance(val["condition"], dict):
            conditions = [val["condition"]]
        elif "conditions" in val:
            conditions = val["conditions"]
        else:
            conditions = [val]
    elif isinstance(val, list):
        conditions = val
    else:
        conditions = []

    form_id = (
        result.get("objId", "")
        or (result.get("targetForm", {}) or {}).get("id", "")
        or (result.get("dataSource", {}) or {}).get("id", "")
        or (result.get("dataSource", {}) or {}).get("sourceId", "")
    )
    fctx = _resolve_form_ctx(result, meta, form_id)
    form = find_in_metadata(meta, "forms", {"id": form_id}) or {}
    field_index = {str(f.get("id", "")): f for f in form.get("fields", [])}
    field_index.update(_TARGET_FORM_FIELDS.get(str(form_id), {}))

    datas = []
    time_stamp = str(int(time.time() * 1000))
    for idx, c in enumerate(conditions):
        if not isinstance(c, dict):
            continue
        left = c.get("left") if isinstance(c.get("left"), dict) else c
        # 兼容 semantic plan 格式: {field:{id:...}, operator:..., value:...}
        if isinstance(left.get("field"), dict) and left.get("field", {}).get("id"):
            field_id = str(left["field"]["id"])
            label = left["field"].get("label") or left["field"].get("name") or field_id
            if isinstance(c.get("right"), dict):
                right = c["right"]
            elif isinstance(c.get("value"), dict):
                # semantic plan 常用 value:{type:"context",key:"字段"}; 不能再包
                # 一层 {value:...}，否则前端会把整个对象显示成 “{Key: ...}”。
                right = c["value"]
            else:
                right = {"value": c.get("value", "")}
        elif left.get("key") or left.get("id"):
            field_id = str(left.get("key", left.get("id", "")))
            label = left.get("label", left.get("name", ""))
            right = c.get("right", c.get("value", ""))
        else:
            field_id = ""
            label = ""
            right = ""
        fmeta = field_index.get(field_id, {})
        if not fmeta:
            raise ValueError(
                f"filterCondition 左侧字段 id='{field_id}' 不在目标表单 '{form_id}' 的实时字段列表中"
            )
        schema = fmeta.get("schema", {}) if isinstance(fmeta.get("schema"), dict) else {}
        raw_field_type = str(fmeta.get("type") or fmeta.get("fieldType") or schema.get("fieldType") or "String")
        comp_type = str(fmeta.get("componentKey") or schema.get("componentKey") or schema.get("compType") or "Text")
        family = _condition_field_family(comp_type, raw_field_type)
        field_type = _filter_field_type(raw_field_type, comp_type)
        label = str(label or fmeta.get("showName") or fmeta.get("name") or field_id)
        raw_config = fmeta.get("config")
        if isinstance(raw_config, str):
            try:
                raw_config = json.loads(raw_config)
            except json.JSONDecodeError:
                raw_config = {}
        multi_select = fmeta.get("multiSelect")
        if multi_select is None and isinstance(raw_config, dict) and "isSingle" in raw_config:
            multi_select = not bool(raw_config.get("isSingle"))
        is_multi_select = multi_select is True or str(multi_select).casefold() == "true"
        # ConditionSet 右值只接受 type；`kind` 属于 mapping/assignment 语义，
        # 不能借用到条件右值，否则容易静默落成空固定值。
        if isinstance(right, dict) and right.get("kind") == "context" and not right.get("type"):
            raise ValueError(
                "filterCondition 不支持 value.kind:'context'；"
                "请使用 right:{type:'context',paramKey:'<真实paramKey>',label:'<显示名>'}"
            )
        right_type = (str(right.get("type") or "fixed").strip().casefold()
                      if isinstance(right, dict) else "fixed")
        if isinstance(right, dict) and right.get("paramKey") and not right.get("type"):
            raise ValueError(
                "filterCondition 动态右值缺少 type:'context'；"
                "请使用 right:{type:'context',paramKey:'<真实paramKey>',label:'<显示名>'}"
            )
        if right_type in {"manual", "constant", "const"}:
            right_type = "fixed"
        elif right_type in {"dynamic", "assign", "workflowfield", "workflow_field"}:
            right_type = "context"
        elif right_type in {"formfield", "form_field"}:
            right_type = "formfield"
        elif right_type in {"custom", "custombyhandler"}:
            right_type = "custombyhander"
        elif right_type in {"platform", "condition"}:
            right_type = "native"
        if right_type not in {
                "fixed", "context", "formfield", "selectdata", "custombyhander",
                "native", "varfield", "filterval"}:
            raise ValueError(
                f"filterCondition 右值 type='{right_type}' 不支持; "
                "支持 fixed/manual/context/formField/selectData/customByHander/native/varField/filterVal"
            )
        # 日期 ConditionSet 的“系统选项”是原生占位值（{today}、{tomorrow} 等），
        # 不属于动态上下文字段，也绝不能在生成时展开为固定日期。调用方可写
        # type=system，或直接把这些值作为 fixed 值；统一保留原值供前端/运行时解析。
        if right_type == "fixed" and isinstance(right, dict) and str(right.get("value", "")) in {
                "{today}", "{yesterday}", "{tomorrow}", "{currweek}", "{lastweek}",
                "{nextweek}", "{currmonth}", "{lastmonth}", "{nextmonth}",
                "{currseason}", "{lastseason}", "{nextseason}", "{curryear}",
                "{lastyear}", "{nextyear}"}:
            right_type = "system"
        if right_type == "system" and family != "date":
            raise ValueError("filterCondition system 日期值仅适用于日期/日期时间字段")
        if event_local_filter and right_type in {"context", "formfield", "custombyhander"}:
            raise ValueError(
                "EventFormData 的 ConditionSet 不支持上下文右值；"
                "前端未启用 supportEsbAssign，请改用固定值或无值操作符"
            )
        is_context = right_type in {"context", "formfield", "custombyhander"}
        is_native = right_type in {"native", "varfield", "filterval"}
        filter_value_type = str(
            (right.get("filterValueType") if isinstance(right, dict) else "")
            or c.get("filterValueType") or ""
        )
        allowed_override = _condition_operator_override(
            fmeta, family, comp_type, field_id, filter_value_type)

        # 先构造右值，数组上下文会把 eq/neq 自动提升为属于/不属于。
        context_is_array = False
        if is_context:
            value, context_is_array = _build_filter_context_formula(
                right, meta, app_id, field_type, comp_type)
        else:
            raw_value = right.get("value", right.get("id", right.get("name", ""))) if isinstance(right, dict) else right
            # 浏览/组织/文件类原生控件保存精简后的对象数组，不能压成 id；
            # 普通输入和选项控件则保存标量/标量数组。
            preserve_browser_payload = is_native or family in {
                "reference", "file", "doc_folder", "app_tag",
            }
            if isinstance(raw_value, dict) and not preserve_browser_payload:
                raw_value = raw_value.get("value", raw_value.get("id", raw_value.get("name", "")))
            elif isinstance(raw_value, list) and not preserve_browser_payload:
                raw_value = [
                    v.get("value", v.get("id", v.get("name", "")))
                    if isinstance(v, dict) else v
                    for v in raw_value
                ]
            # ConditionSet 的原生手动控件直接保存 raw value。固定值绝不能包装为
            # FormulaBean；否则必须把 isEsb 设为 true，而前端会无条件切到
            # ComEsbComp（截图中的赋值标签），不会渲染“手动输入 + 输入框”。
            value = raw_value

        func = _normalize_filter_operator(
            c.get("operator", "eq"), family,
            context_is_array=context_is_array, multi_select=is_multi_select,
            allowed_override=allowed_override)
        is_nullary = func in {"empty", "nempty"}
        if is_nullary:
            value = ""
        elif func == "range":
            if is_context:
                raise ValueError("filterCondition range 动态右值必须提供两个原生端点，不能使用单个 context")
            if not isinstance(value, list) or len(value) != 2:
                raise ValueError("filterCondition range 右值必须是长度为 2 的数组 [起始值, 结束值]")

        # conditions.text 是右值显示名，不是左侧字段名。
        value_text = ""
        if isinstance(right, dict) and (right.get("label") or right.get("name")):
            value_text = str(right.get("label") or right.get("name"))
        elif isinstance(value, dict):
            value_text = str(value.get("name") or value.get("value") or "")
        elif isinstance(value, list):
            def _display(v: Any) -> str:
                if isinstance(v, dict):
                    return str(v.get("content") or v.get("label") or v.get("name") or v.get("id") or "")
                return str(v)
            value_text = ",".join(_display(v) for v in value)
        elif isinstance(value, str):
            value_text = value

        condition_data = {
            "func": func,
            "text": "" if is_nullary else value_text,
            "value": value,
        }
        # 第三个选择框（取值方式）由字段族 + 右值来源共同决定。
        # - 手动输入：conditions.isEsb=false，value 保存字段原生 raw value；
        #   文本 conditions.type 留空时 ComText 默认选择 id="0"（手动输入）；
        # - 表单字段：原始流程表单字段上下文使用 formField；
        # - 关联/组织字段动态值：使用真实枚举 custombyhander；
        # - 选择/关联固定值：使用字段自身选择控件（""/selectData）。
        if not is_nullary:
            if is_context:
                _val = value.get("value", "") if isinstance(value, dict) else ""
                _val_tail = str(_val).rsplit(".", 1)[-1]
                #  ApprovalData 系统字段 (value 以 "ApprovalData." 开头
                # 且末段非数字, 如 dataId/requestId/formId) 走 formField 模式 ——
                # 的正确渲染 (前端 ComFormField 按 paramKey 匹配 cacheContext ApprovalData 组),
                # 而不是 esbAssign 标签 ("流程IDX" 等不直观).
                _is_approval_field = (
                    isinstance(_val, str) and _val.startswith("ApprovalData.")
                    and not _val_tail.isdigit()
                )
                # ApprovalData 系统字段优先于 family=="reference" 判断 (Workflow
                # 组件被 _condition_field_family 归为 reference, 但渲染应走 formField).
                if _is_approval_field or right_type == "formfield" or (
                        isinstance(value, dict) and str(value.get("value", "")).startswith("FormData.")):
                    condition_data["type"] = "formField"
                elif right_type == "custombyhander" or family == "reference":
                    condition_data["type"] = "custombyhander"
            elif is_native:
                native_mode = str(
                    right.get("mode") or right.get("conditionType") or right.get("nativeType")
                    or {"varfield": "varField", "filterval": "filterVal"}.get(right_type, "")
                )
                if not native_mode:
                    raise ValueError("filterCondition native 右值必须提供 mode/conditionType/nativeType")
                condition_data["type"] = native_mode
            elif right_type == "system":
                # 前端选择日期“系统选项”后保存 type=''；value 是 {today} 等原值。
                condition_data["type"] = ""
            elif family == "reference" or right_type == "selectdata":
                condition_data["type"] = "selectData"
            elif family in {"select", "boolean"}:
                condition_data["type"] = ""
        if not is_nullary and is_context:
            # - ApprovalData 系统字段 (value="ApprovalData.…non-digit"): isEsb=False +
            # - FormData 字段 (value="FormData.…"): 保留 FormBean + isEsb=True
            #   (前端 esbAssign 标签, 测试期望保留 config 等)
            # custombyhander (关联/组织字段) isEsb=True 走 ComEsbComp.
            _render_type = condition_data.get("type")
            if _render_type == "formField" and _is_approval_field:
                # 规则: isEsb 应为 true — ApprovalData 系统字段
                # 在 filterInput 里走 esbAssign 模式 (ComEsbComp 标签, isEsb=true + 完整
                # 清 FormulaBean 的形态前端渲染"选择数据/字符串字面量", 错误.
                _esb_wid = ""
                if isinstance(value, dict):
                    _esb_wid = str(value.get("source") or "")
                if not _esb_wid and isinstance(meta, dict):
                    _esb_wid = str(meta.get("_upstream_w_id", "") or "")
                if not _esb_wid:
                    _esb_wid = time_stamp[:13]
                condition_data.update({
                    "isEsb": True,
                    "esbAssign": {
                        "wId": _esb_wid,
                        "textarea": False,
                        "withoutDftNum": True,
                    },
                })
            else:
                #  esbAssign.wId 必须与 value.source 一致 — 前端
                # ComEsbComp 用 wId 查 cacheContext[comId], 不一致时降级显示"手动输入"+空输入框
                # ( 真机截图: 来源审核流程=手动输入). 优先 value.source (刚生成的
                # FormulaBean.source = event.id), 再 meta._upstream_w_id, 最后 time_stamp[:13].
                _esb_wid = ""
                if isinstance(value, dict):
                    _esb_wid = str(value.get("source") or "")
                if not _esb_wid and isinstance(meta, dict):
                    _esb_wid = str(meta.get("_upstream_w_id", "") or "")
                if not _esb_wid:
                    _esb_wid = time_stamp[:13]
                condition_data.update({
                    "isEsb": True,
                    "esbAssign": {
                        "wId": _esb_wid,
                        "textarea": False,
                        "withoutDftNum": True,
                    },
                })
        elif not is_nullary:
            condition_data["isEsb"] = False

        # 组件特有状态必须显式透传，不能假定所有 ConditionSet 行只有 type/value/text。
        if isinstance(right, dict):
            for native_key in ("customSelect", "filterValueType", "matchType", "changeTrigger"):
                if native_key in right:
                    condition_data[native_key] = right[native_key]

        origin_browser_type = str(
            fmeta.get("originBrowserType")
            or (raw_config.get("originBrowserType") if isinstance(raw_config, dict) else "")
            or ("browser" if family in {"select", "reference"} else "")
        )

        datas.append({
            "isParent": False,
            "fieldName": field_id,
            "mainField": True,
            "module": "",
            "subTableId": "",
            "parentNode": time_stamp + str(idx),
            "type": "condition",
            "optionType": "",
            # ConditionSet 的真实手工保存行不携带表单字段详情；字段详情来自
            # dataSet。额外写入 formInfo/opts/config/sformId 等会让右值被前端
            # 当成已选赋值摘要，而不是按 config.menuType=manual 渲染输入框。
            "compType": comp_type,
            "objId": str(fctx.get("objId", form_id)),
            "id": field_id,
            "text": label,
            "conditions": condition_data,
            "originBrowserType": origin_browser_type,
            "fieldType": field_type,
            "key": time_stamp + str(idx + 1),
            "multiSelect": str(bool(multi_select)).lower(),
        })
        if raw_field_type:
            # dbFieldType 出现在部分真实版本的手工条件行中；它是标量字段
            # 类型，不是表单 config，保留它不会改变 ConditionSet 的右值模式。
            datas[-1]["dbFieldType"] = raw_field_type
    return {
        "isNewFilter": True,
        "isParent": True,
        "datas": datas,
        "parentNode": "",
        "relationship": "1",
        "key": time_stamp,
    }

# ── 节点转换 ────────────────────────────────────────────────────────────────

def convert_node(draft_action: dict, is_event: bool = False,
                 meta: Optional[dict] = None, app_id: str = "",
                 action_index: int = 0, event_node_id: str = "",
                 event_name: str = "",
                 previous_node_id: int | str = "0",
                 lenient: bool = False) -> dict:
    node_type = draft_action["type"]
    comp = get_component(node_type) or {}
    display = comp.get("display", {})
    # ID: 平台以字符串形态保存节点标识(wId 恒为字符串;真实 capture 中 id 亦多为字符串).
    # 统一输出字符串,避免 int/str 混用导致设计器解析不一致.
    #  event 节点 id 必须雪花格式 (前端 SnowFlake), 否则 platform
    # 注册触发时 basisValueFormula.source 重写为注册 id → 与 event.id 失配标红.
    # ID: 平台以字符串形态保存节点标识(wId 恒为字符串;真实 capture 中 id 亦多为字符串).
    # 统一输出字符串,避免 int/str 混用导致设计器解析不一致.
    #  event 也用 gen_id (随机 15 位) — 验证雪花 18 位
    # detail.basisValue.source 不被平台 detail 保存接受 (data=NULL); source 匹配
    # 由"不绑定"保证 (save_add_action_list 绑定会把 source 重写为流程注册 id 标红,
    # 平台设计提交会自动注册触发，无需绑定）。
    raw_id = draft_action.get("id")
    try: nid = int(raw_id) if raw_id is not None else gen_id()
    except (ValueError, TypeError): nid = gen_id()
    nid_str = str(nid)

    node = {
        "id": nid_str, "wId": nid_str,
        "name": draft_action.get("name", display.get("componentName", node_type)),
        "type": node_type,
        "attr": {"icon": display.get("icon", "Icon-default")},
        "data": map_draft_data(draft_action.get("params", {}), node_type,
                           meta, app_id, action_index, event_node_id or nid_str,
                           event_name, lenient=lenient),
        "parentId": "0",
    }
    # 合并 pending mapping/constants/formula 到 setting
    node_data = node.get("data", {})
    pending_mapping = node_data.pop("_pending_mapping", None)
    pending_constants = node_data.pop("_pending_constants", None)
    pending_formula = node_data.pop("_pending_formula", None)
    pending_detail = node_data.pop("_pending_detail", None)
    if node_type == "ApproveCreate" and (pending_mapping or pending_constants or pending_formula or pending_detail):
        # 新建流程: 字段映射进 formData.main/detail (BPM 流程表单字段),
        # 结构与 setting.main 相同 (真实 e-builder 前端 SettingFormData 形态)
        _fill_setting(node_data, mapping=pending_mapping, constants=pending_constants,
                      formula=pending_formula,
                      meta=meta, app_id=app_id, event_id=event_node_id or nid_str,
                      component_type=node_type)
        # plan params.detail → formData.detail (与 ActionEbAdd 同构).
        if pending_detail and isinstance(node_data.get("setting"), dict):
            _build_setting_detail(node_data, pending_detail, meta, app_id,
                                  event_node_id or nid_str, node_type)
        _setting = node_data.pop("setting", {})
        main = _setting.get("main", {})
        detail_out = _setting.get("detail", [])
        node_data["formData"] = {"main": main, "detail": detail_out, "dataDrWithCalc": False}
        # fields: 目标流程表单字段 (preflight 注入 _bizFields); 无则空数组
        biz_fields = {}
        if isinstance(meta, dict):
            biz_fields = meta.get("_bizFields") or {}
        if not biz_fields:
            biz_fields = draft_action.get("params", {}).get("_bizFields", {})
        node_data["fields"] = {
            "main": biz_fields.get("main", []) if isinstance(biz_fields, dict) else [],
            "detail": biz_fields.get("detail", []) if isinstance(biz_fields, dict) else [],
        }
    elif pending_detail and not (pending_mapping or pending_constants or pending_formula):
        # 非 ApproveCreate（尤其 ActionEbAdd/ActionEbUpdate）也必须在下方统一
        # _build_setting_detail 消费明细。旧逻辑提前 pop 后未放回，导致 detail 永远
        # 为空，平台虽保存但设计器没有“依据值/赋值字段”。
        _fill_setting(node_data, meta=meta, app_id=app_id,
                      event_id=event_node_id or nid_str, component_type=node_type)
        node_data["_pending_detail"] = pending_detail
        node_data["formDataId"] = str(gen_id())
    elif node_type == "ApproveCreate":
        # 新建流程即使没有字段映射，也必须显式携带表单数据容器。
        # 后端/前端契约要求 formData.main/detail 与 fields.main/detail 存在。
        node_data.setdefault("formData", {"main": {}, "detail": [], "dataDrWithCalc": False})
        node_data.setdefault("fields", {"main": [], "detail": []})
        node_data.setdefault("formDataId", str(gen_id()))
    elif (pending_mapping or pending_constants or pending_formula) and "setting" not in node_data:
        # 注入上游信息(供 child 引用使用):
        #  - _upstream_form_name / _upstream_table_id: ActionEbAdd/Update 的目标表单名+id
        #    供 parentName 拼接 "表单数据.{field}" 和 value "FormData.{tableId}.{field}" 使用
        #  - _upstream_name: 流程触发名,占位未来扩展
        meta = dict(meta) if isinstance(meta, dict) else {}
        tf = node_data.get("targetForm", {}) if isinstance(node_data, dict) else {}
        if tf.get("text") or tf.get("name"):
            meta["_upstream_form_name"] = tf.get("text") or tf.get("name")
        if tf.get("id"):
            meta["_upstream_table_id"] = str(tf.get("id"))
        if event_name:
            meta["_upstream_name"] = event_name
        if node_data.get("workflowId"):
            meta["_workflow_id"] = str(node_data["workflowId"])
        if pending_detail:
            node_data["_pending_detail"] = pending_detail
        _fill_setting(node_data, mapping=pending_mapping, constants=pending_constants,
                      formula=pending_formula,
                      meta=meta, app_id=app_id, event_id=event_node_id or nid_str,
                      component_type=node_type)
    #  批量新增依据值 (batchInsert) 的 bassisValueId/bassisValue 合并进 setting.
    # _basisValue 存 _pending_basis, 必须在 _fill_setting 写 main 之后合并 (保持 main 存在).
    pending_basis = node_data.pop("_pending_basis", None)
    if pending_basis and isinstance(node_data.get("setting"), dict):
        node_data["setting"].update(pending_basis)
    # 若既有旧 updates(-setting_main)又有新 mapping/constants,合并到已有 main
    if (pending_mapping or pending_constants) and isinstance(node_data.get("setting"), dict):
        main = node_data["setting"].get("main", {})
        if pending_mapping and isinstance(pending_mapping, dict):
            for source_key, target_field_id in pending_mapping.items():
                #  dict 值 (依据值下级 {target,paramKey,...}) 已由 _fill_setting
                # 正确处理写入 main, 此处旧合并逻辑 str(dict) 会生成错误 key — 跳过.
                if isinstance(target_field_id, dict):
                    continue
                raw = str(target_field_id)
                operate = "OPERATE_EQUAL"
                if raw.startswith("+"):
                    operate = "OPERATE_PLUS"; raw = raw[1:]
                elif raw.startswith("-"):
                    operate = "OPERATE_MINUS"; raw = raw[1:]
                tfid = raw
                main[tfid] = build_setting_entry(
                    tfid,
                    {"kind": "context", "paramKey": str(source_key), "label": str(source_key)},
                    meta=meta, app_id=app_id, default_source_id=event_node_id or nid_str,
                    operate=operate, component_type=node_type,
                )
        if pending_constants and isinstance(pending_constants, dict):
            for target_field_id, value in pending_constants.items():
                tfid = str(target_field_id)
                #  与 _fill_setting 的 constants 分支一致 — 支持 +/- 累加.
                operate_c = "OPERATE_EQUAL"
                raw_v = value
                if isinstance(value, str) and len(value) > 1 and value[0] in "+-":
                    operate_c = "OPERATE_PLUS" if value[0] == "+" else "OPERATE_MINUS"
                    raw_v = value[1:]
                # 与 _fill_setting 的首轮 constants 路径保持一致：Select/Radio
                # 需要写真实 option valueKey，不能在二次合并时用展示文本覆盖。
                raw_v = _resolve_enum_constant(raw_v, _lookup_target_field_meta(tfid, node_data))
                assignment, ft = _normalize_constant_assignment(
                    raw_v, default_field_type="Text",
                )
                main[tfid] = build_setting_entry(
                    tfid, assignment,
                    field_type=ft, meta=meta, app_id=app_id,
                    default_source_id=event_node_id or nid_str,
                    operate=operate_c,
                    component_type=node_type,
                )
        if pending_formula and isinstance(pending_formula, dict):
            for target_field_id, fspec in pending_formula.items():
                main.update(_build_formula_setting_entry(
                    str(target_field_id), fspec, str(event_node_id or nid_str), app_id,
                ))
        node_data["setting"]["main"] = main
        node_data["setting"]["opType"] = node_data["setting"].get("opType", "insert")

    # 明细表字段赋值: _pending_detail → setting.detail (真实结构: 数组, 元素含 detailTableId/data)
    pending_detail = node_data.pop("_pending_detail", None)
    if pending_detail and isinstance(node_data.get("setting"), dict):
        _build_setting_detail(node_data, pending_detail, meta, app_id, event_node_id or nid_str, node_type)

    if is_event:
        node["triggerType"] = comp.get("triggerType", "WorkflowTrigger")
        node["triggerTypeName"] = comp.get("triggerTypeName",
                                          "流程事件触发" if node_type == "ApproveTrigger" else node_type)
        node["costTime"] = 0
        # 平台数据对齐: 流程触发节点带图标颜色 + data.type/fromCopy(见采购数据)
        if display.get("iconColor"):
            node["attr"]["iconColor"] = display["iconColor"]
        if node_type == "ApproveTrigger":
            node_data = node.get("data", {})
            node_data.setdefault("type", "ApproveTrigger")
            node_data.setdefault("fromCopy", False)
        elif node_type == "EventFormData":
            # 表单数据触发: data.type 必填 (前端 ActionEbFormData 提交 EventFormData)
            node_data = node.get("data", {})
            node_data.setdefault("type", "EventFormData")
            node_data.setdefault("ebActionId", "-1")
    else:
        # AI 导入入口要求 componentId 与节点 id 对应;保存后端会将其映射为真实组件记录.
        node["componentId"] = nid_str
        # 设计器加载时会自动把第一个无来源动作接到 event;后续节点必须显式
        # 指向前一个 wId,否则保存并重新加载后会被当作孤立节点而不显示.
        if str(previous_node_id) not in ("", "0", str(event_node_id)):
            node["sources"] = [{"wId": str(previous_node_id)}]

    # ── SendMessage 画布节点后处理 ──────────────────────────────
    # 设计 JSON 中 SendMessage 节点固定显示为「消息提醒」(label 221877),
    # attr.icon=Icon-Message-center-o、senderType="system"、receiver 走 person.
    # 后端组件库注册名是「发送消息」(label 95871),但那不是设计 JSON 节点名.
    # 平台数据字段:msgContent/msgTitle/person(非套件的 msgContentv/shareList).
    if node_type == "SendMessage" and not is_event:
        data = node.get("data", {})
        data.setdefault("senderType", "system")
        # receiver 参数 -> person(后端执行公式) + shareList(设计器表格数据源)
        params = draft_action.get("params", {})
        receiver = params.get("receiver") or params.get("receivers")
        if receiver and isinstance(receiver, dict):
            if "person" not in data:
                person_formula = build_person_formula(
                    receiver, meta or {}, app_id, for_send_message=True)
                rtype = receiver.get("type", "role")
                # 带具体值的对象类型(人员/部门/分部/角色/群组/岗位/外部联系人等)
                # 统一补 fixValue originValue 配置, 与 shareList 的 obj_id 一致.
                if rtype not in ("role", "context", "user_reference", "all",
                                 "allExternal") and receiver.get("id"):
                    pid = str(receiver["id"])
                    pname = str(receiver.get("name", pid))
                    person_obj = _build_person_object(pid, pname, app_id)
                    person_formula["configObject"] = {
                        "switchType": "fixValue", "originValue": [person_obj]}
                    person_formula["name"] = pid
                    person_formula["value"] = pid
                    person_formula["config"] = {
                        "switchType": "fixValue", "originValue": [person_obj],
                        "formulaVersion": "V1"}
                data["person"] = person_formula
            if "shareList" not in data:
                data["shareList"] = _build_share_list(
                    receiver, meta or {}, app_id, event_node_id)
            if "objectList" not in data:
                data["objectList"] = []
        # 补齐真实平台必有的上下文字段
        if app_id and "currentApplication" not in data:
            data["currentApplication"] = str(app_id)
        node["data"] = data

    # ── 数据动作后处理: 默认补创建人/操作人 person ──────────────────────
    # 真实 ActionEbAdd/Update/Delete 必有 person(数据更新人), 即使未显式配置
    # 也是「当前执行人」容器 (type=8 + {userid} type=9). plan 传了 person 时
    if node_type in ("ActionEbAdd", "ActionEbUpdate", "ActionEbDelete") and not is_event:
        data = node.get("data", {})
        if "person" not in data:
            #  数据动作 person 直连 (type=9 本体, 无容器)
            data["person"] = build_person_formula({"type": "role"}, meta or {}, app_id,
                                                  direct_person=True)
            node["data"] = data

    return node

def _build_condition_detail(condition: dict, source_id: str, meta: dict = None) -> dict:
    """序列化语义条件为 Condition.data.conditionDetail.

    ESB 真实 captures 实证: conditionDetail 只需 5 个字段,
    不需要 conditionDataJson (那是集成平台 GeneralEvent 的格式).
    sourceIds 应指向同一动作流中前一个 action 的 id.

    算子映射:
      eq=1, neq=2, gt=5, lt=6, gte=7, lte=8,
      contain=9, notcontain=10, in=11, notin=12, empty=13, nempty=14
    """
    if not isinstance(condition, dict):
        return {}
    left = condition.get("left") or {}
    field_key = str(left.get("key") or left.get("value") or "").strip()
    field_label = str(left.get("label") or left.get("name") or field_key or "").strip()
    operator = str(condition.get("operator", "")).strip().casefold()

    # 字段名校验:如果 meta._workflow_id 登记了 workflow fields,
    # 但 plan 给的字段名查不到 → 显式报错(避免静默生成无效引用)
    is_enquiry_count = field_key in {"count", "response.count", "Response.response.count"}
    if field_key and not is_enquiry_count and isinstance(meta, dict) and meta.get("_workflow_id"):
        wf_id = str(meta["_workflow_id"])
        wf_fields = _WORKFLOW_FIELD_IDS.get(wf_id, {})
        if wf_fields and field_key not in wf_fields:
            raise ValueError(
                f"Condition.left.key='{field_key}' 不是流程 '{wf_id}' 的字段. "
                f"已知字段: {sorted(wf_fields.keys())}. "
                f"Condition 的 left 只能引用流程触发 (ApproveTrigger) 上下文的字段."
            )

    opt_code_map = {
        "eq": 1, "==": 1, "=": 1, "等于": 1,
        "neq": 2, "!=": 2, "<>": 2, "不等于": 2, "ne": 2,
        "gt": 5, ">": 5, "大于": 5,
        "lt": 6, "<": 6, "小于": 6,
        "gte": 7, ">=": 7, "大于等于": 7,
        "lte": 8, "<=": 8, "小于等于": 8,
        "contains": 9, "contain": 9, "包含": 9,
        "notcontains": 10, "notcontain": 10, "不包含": 10,
        "in": 11, "属于": 11,
        "notin": 12, "not_in": 12, "不属于": 12,
        "empty": 13, "isnull": 13, "为空": 13,
        "nempty": 14, "isnotnull": 14, "不为空": 14,
    }
    opt = opt_code_map.get(operator, 1)
    opt_label_map = {
        1: "等于", 2: "不等于", 5: "大于", 6: "小于",
        7: "大于等于", 8: "小于等于", 9: "包含", 10: "不包含",
        11: "属于", 12: "不属于", 13: "为空", 14: "不为空",
    }
    opt_label = opt_label_map.get(opt, "等于")
    need_right = opt not in (13, 14)

    right = condition.get("right") or {}
    right_value = right.get("value", "")
    right_label = str(right.get("label") or right_value or "").strip()

    if need_right:
        condition_cn = f"({field_label} {opt_label} {right_label})"
    else:
        condition_cn = f"({field_label} {opt_label})"

    cid = str(gen_id())
    expr_id = str(gen_id())
    map_base = str(gen_id())
    map_id_val = str(gen_id())
    eb_id = str(gen_id())
    base_id = str(gen_id())
    dv_id = str(gen_id())
    ev1 = str(gen_id())
    ev2 = str(gen_id())
    child_expr = str(gen_id())

    # field_key 可能是流程字段中文名(plan 直接给),也可能是已 id 格式.
    # paramKey 契约: getComponentContext(ApproveTrigger)
    # 的 tableData[].paramKey = "{workflowId}.{fieldId}" (如
    # '<workflowId>.<fieldId>'). "已删除"判定 = assign.paramKey
    workflow_id = ""
    if isinstance(meta, dict):
        workflow_id = str(meta.get("_workflow_id", "") or "")
    field_id = workflow_field_id(workflow_id, field_key) if workflow_id else ""
    if is_enquiry_count:
        # count 是 EnquiryForm 的 Response.response.count 运行时输出，而非流程表单字段。
        # Condition 必须绑定紧邻查询节点，不能回退成 ApproveTrigger 上下文。
        param_key_id = "response.count"
        value_id = "response.count"
        com_type = "EnquiryForm"
    elif field_id and workflow_id and field_id != field_key:
        param_key_id = f"{workflow_id}.{field_id}"
        value_id = f"FormData.{workflow_id}.{field_id}"
        com_type = "ApproveTrigger"
    else:
        # 兜底: 用原中文/裸 key, 设计器会回退, 但 paramKey 形态尽量对齐契约
        param_key_id = field_key
        value_id = f"FormData.{field_key}" if field_key else ""
        com_type = "EbGetDataById"

    # source_id: Condition 节点的上一个兄弟节点的 wId (sources[].wId 约定).
    # upstream_w_id: 上游触发器节点的 wId (event_node.wId), 用于 customFieldType
    # .config.comId / selectType, 让前端 isLegalContextVar 在 cacheContext 里
    # 找到 contextData (cacheContext 用 actionFlow wId 索引, 不是工作流节点 id).
    upstream_w_id = ""
    if isinstance(meta, dict):
        upstream_w_id = str(meta.get("_upstream_w_id", "") or "")
    context_w_id = str(source_id) if is_enquiry_count else (upstream_w_id or str(source_id))
    left_operand = {
        "expressionBaseId": base_id,
        "StringCompareOptionLeft": opt,
        "dataValueId": dv_id,
        "elementValue2Id": ev2,
        "elementValue1Id": ev1,
        "selectType": 97,
        "customFieldType": {
            "paramType": "string", "formulaType": "string",
            "name": field_label,
            "selectType": "-1",
            "id": eb_id, "source": context_w_id,
            "type": "3", "value": value_id,
            "config": {
                "paramKey": param_key_id, "isMultCom": False,
                "comType": com_type, "parentComId": 0,
                "fieldInfo": {"paramKey": param_key_id, "tablePrimaryKey": "FormData"},
                "tableName": "表单数据", "paramType": "string",
                "parentName": field_label, "multName": "", "multKey": "",
                "multTypeObj": {"allName": field_label, "currentName": field_label,
                    "currentParamKey": value_id,
                    "allParamKey": value_id},
                "comId": context_w_id, "newParentName": field_label,
            },
            "fieldType": "string",
        },
    }
    if need_right:
        right_val = str(right_value)
        left_operand["StringTextValueLeft"] = {
            "formulaType": "string", "name": right_val,
            "selectType": "-1", "id": str(gen_id()),
            "type": "1", "value": right_val, "fieldType": "string",
        }

    data_json = json.dumps({
        "sourceId": str(source_id) if source_id else "-1",
        "expressionId": expr_id,
        "mapBaseId": map_base,
        "conditionId": cid,
        "childrens": [{"expressionId": child_expr, "childrens": [left_operand]}],
        "mapId": map_id_val, "source": 8, "relation": 1,
    }, ensure_ascii=False)

    return {
        "conditionId": cid,
        "conditionCn": condition_cn,
        "mapBaseId": map_base,
        "mapId": map_id_val,
        "sourceIds": [source_id] if source_id else [],
        "conditionDataJson": data_json,
    }

def convert_condition(draft_action: dict, meta=None, app_id="", action_index=0,
                      event_id="", previous_node_id="0", lenient: bool = False) -> dict:
    node = convert_node(draft_action, meta=meta, app_id=app_id,
                        action_index=action_index, event_node_id=event_id,
                        previous_node_id=previous_node_id, lenient=lenient)
    # 兼容 draft 在 params.branches 或顶层 branches 两种写法
    _src = draft_action.get("params", {}) if isinstance(draft_action.get("params"), dict) else {}
    branches = draft_action.get("branches") or _src.get("branches") or []
    if not branches:
        node["data"]["trueBranchActions"] = []
        node["data"]["falseBranchActions"] = []
        node["data"]["otherConditionBranch"] = []
        return node

    conditional_branches: list[tuple[dict[str, Any], list[dict[str, Any]], str]] = []
    else_branch_actions: Optional[list[dict[str, Any]]] = None

    for i, branch in enumerate(branches):
        cond = branch.get("condition") if isinstance(branch, dict) else None
        if not isinstance(cond, dict):
            cond = {}
        is_else = cond.get("type") == "else"
        has_real_cond = bool(cond) and not is_else and cond.get("left")

        # 分支内是独立线性子链。首节点由设计器回读时接到分支容器；
        # 后续节点必须显式引用同分支的前一个节点，否则保存后会散开。
        # 分支内只放真实操作; Output(终止) 是主链结束节点, 只能通过
        # finalOutput 表达, 不嵌入分支 (validate 已拦截, 这里兜底跳过).
        bacts = []
        branch_previous_id = "0"
        for a in branch.get("actions", []):
            if a.get("type") == "Output":
                continue
            branch_node = convert_node(
                a,
                meta=meta,
                app_id=app_id,
                action_index=i,
                event_node_id=event_id,
                previous_node_id=branch_previous_id,
            )
            bacts.append(branch_node)
            branch_previous_id = branch_node["wId"]

        if has_real_cond:
            conditional_branches.append((cond, bacts, str(branch.get("name") or "满足条件")))
        else:
            # 当前设计器的最后一个非条件分支是“否则”。重复的 else 保留首个，
            # 其余不会静默伪装成条件分支。
            if else_branch_actions is None:
                else_branch_actions = bacts

    true_branch_actions = conditional_branches[0][1] if conditional_branches else []
    false_branch_actions = else_branch_actions or []
    other_branch_actions: list[dict[str, Any]] = []
    for index, (cond, actions, name) in enumerate(conditional_branches[1:], start=2):
        branch_id = str(gen_id())
        detail = _build_condition_detail(cond, previous_node_id, meta=meta)
        other_branch_actions.append({
            "id": branch_id,
            "wId": branch_id,
            "branchName": name or f"条件{index}",
            "conditionId": detail.get("conditionId", ""),
            "conditionDetail": detail,
            "branchActions": actions,
        })

    node["data"]["trueBranchActions"] = true_branch_actions
    node["data"]["falseBranchActions"] = false_branch_actions
    node["data"]["otherConditionBranch"] = other_branch_actions

    # 序列化分支条件为真实 conditionDetail (取首个有效条件).
    # sourceIds + sources.wId 都指向该 action 的前一个兄弟节点.
    if conditional_branches:
        detail = _build_condition_detail(conditional_branches[0][0], previous_node_id, meta=meta)
        node["data"]["conditionDetail"] = detail
        node["data"]["conditionId"] = detail["conditionId"]

    # 设计器连线: sources[].wId 指向前一个节点 id.
    # 首节点(前一个节点是 event)不加 sources——设计器自动把第一个无来源
    # 动作接到 event,显式加 event 引用反而被识别成孤立分支导致
    # "没有起始执行组件". 平台数据格式仅 wId, 不带 id/status.
    if previous_node_id and str(previous_node_id) not in ("0", str(event_id)):
        node["sources"] = [{"wId": str(previous_node_id)}]

    return node

def build_assist_layer(event: dict, actions: list) -> dict:
    nodes = [{"id": event["id"], "type": event["type"],
              "layout": {"x": 100, "y": 100, "width": 200, "height": 80}}]
    y = 220
    for a in actions:
        nodes.append({"id": a["id"], "type": a["type"],
                       "layout": {"x": 100, "y": y, "width": 200, "height": 80}})
        y += 130
    return {"nodes": nodes, "edges": [], "layout": {"offsetX": 0, "offsetY": 0, "zoom": 1.0}}

def _register_real_node_ids(draft_node: dict, real_node: dict, node_ids: dict[str, str]) -> None:
    """建立编译期 action_1/event 等语义 ID 到真实节点 ID 的映射。"""
    draft_id = str(draft_node.get("id", "")) if isinstance(draft_node, dict) else ""
    real_id = str(real_node.get("id", "")) if isinstance(real_node, dict) else ""
    if draft_id and real_id:
        node_ids[draft_id] = real_id
    if not (isinstance(draft_node, dict) and isinstance(real_node, dict)):
        return
    draft_branches = draft_node.get("branches", [])
    real_data = real_node.get("data", {})
    if not isinstance(draft_branches, list) or not isinstance(real_data, dict):
        return
    real_branch_lists = [real_data.get("trueBranchActions", []), real_data.get("falseBranchActions", [])]
    for index, draft_branch in enumerate(draft_branches[:2]):
        if not isinstance(draft_branch, dict):
            continue
        real_branch = real_branch_lists[index] if index < len(real_branch_lists) else []
        for draft_child, real_child in zip(draft_branch.get("actions", []), real_branch):
            _register_real_node_ids(draft_child, real_child, node_ids)

def _replace_formula_source_aliases(value: Any, node_ids: dict[str, str]) -> None:
    """把 FormulaBean.type=3 的 event/action_1 语义别名改为真实节点 ID。

     修复: 同时替换 config JSON 字符串里的 comId — 设计器通过
    config.comId 在 cacheContext 里定位上游节点, 若保留 "event_1" 等语义别名
    或随机数, 匹配不到 → 动态赋值标"已删除". 平台数据契约: comId 必须指向
    event/action 节点的真实 wId.
    """
    if isinstance(value, dict):
        if str(value.get("type")) == "3" and "formulaType" in value:
            source = value.get("source")
            if isinstance(source, str) and source in node_ids:
                value["source"] = node_ids[source]
        # config 字符串里可能内嵌 comId (JSON), 同样替换语义别名
        cfg = value.get("config")
        if isinstance(cfg, str):
            try:
                cfg_obj = json.loads(cfg)
                if isinstance(cfg_obj, dict):
                    cid = cfg_obj.get("comId")
                    if isinstance(cid, str) and cid in node_ids:
                        cfg_obj["comId"] = node_ids[cid]
                        value["config"] = json.dumps(cfg_obj, ensure_ascii=False)
            except Exception:
                pass
        for child in value.values():
            _replace_formula_source_aliases(child, node_ids)
    elif isinstance(value, list):
        for child in value:
            _replace_formula_source_aliases(child, node_ids)

def _build_formula_setting_entry(target_field_id: str, fspec: dict,
                                  event_id: str, app_id: str) -> dict:
    """从 formula spec 构建单个 setting.main 条目 (type=6 数学运算)."""
    if not isinstance(fspec, dict): return {}
    op = fspec.get("op", "add")
    fields = fspec.get("fields", [])
    if not fields: return {}
    fn_info = _get_formula_fn(op)
    childs = []
    for fld in fields:
        child = _assign_flat_context(str(fld), str(fld), str(event_id), app_id, "double")
        child["position"] = str(gen_id())
        child["paramType"] = "double"
        child["componentKey"] = "Number"
        child["fieldType"] = "number"
        childs.append(child)
    bean = formula_function(
        fn_info["fnId"], name=fn_info["name"], childs=childs,
        field_type="double", excel_func=op,
        function_type=fn_info.get("functionType", "operation"),
        app_id=app_id,
    )
    flat_id = bean.get("id") or str(gen_id())
    assign = {k: v for k, v in bean.items()
              if k not in ("configObject", "childs", "parentId", "sortWeight", "position")}
    if bean.get("childs"): assign["childs"] = bean["childs"]
    assign.setdefault("applicationId", str(app_id))
    assign.setdefault("id", str(flat_id))
    return {str(target_field_id): {
        "formFieldKey": "",
        "value": {
            "original": False, "operate": "OPERATE_EQUAL", "switchType": "assign",
            "fieldKey": str(target_field_id), "assignType": "", "multiSelect": False,
            "fieldType": "NumberComponent", "assign": assign, "assignId": str(flat_id),
        },
    }}

def _build_reload_formula(real_actions: list, event_id: str, app_id: str) -> list:
    """从 action 的 setting.main 生成 reloadFormula 数组.

    reloadFormula 是设计顶层字段，每个映射条目提供 UI 元数据，
    平台前端用它在设计器中渲染上下文引用字段.
    格式参照 e10-cli: 完整 type=3 公式 bean + UI 字段.
    """
    entries: list[dict] = []
    for action in real_actions:
        setting = action.get("data", {}).get("setting", {})
        main = setting.get("main", {})
        if not isinstance(main, dict):
            continue
        action_id = action.get("id", "")
        for field_id, entry in main.items():
            if not isinstance(entry, dict):
                continue
            value_wrapper = entry.get("value", {})
            if not isinstance(value_wrapper, dict):
                continue
            assign = value_wrapper.get("assign", {})
            if not isinstance(assign, dict):
                continue
            # 数组空,设计器"动态赋值结果"列报"已删除".
            ref_leaf = None
            if str(assign.get("type")) == "3":
                ref_leaf = assign
            elif str(assign.get("type")) == "8" and isinstance(assign.get("childs"), list) and assign["childs"]:
                ch0 = assign["childs"][0]
                if str(ch0.get("type")) == "3":
                    ref_leaf = ch0
            if ref_leaf is None:
                continue
            # 字段优先用 leaf(完整),name 兼容 assign 顶层
            param_key = ref_leaf.get("paramKey") or ref_leaf.get("value", "").replace("FormData.", "")
            src_id = ref_leaf.get("source", event_id)
            name_display = (ref_leaf.get("showName") or ref_leaf.get("name")
                             or assign.get("name", param_key))
            field_type = ref_leaf.get("fieldType", "string")
            entries.append({
                "id": str(gen_id()),
                "paramKey": param_key,
                "paramName": ref_leaf.get("paramName", param_key),
                "showName": name_display,
                "paramType": field_type,
                "dataType": ref_leaf.get("dataType", "attribute"),
                "arrs": False,
                "required": False,
                "description": ref_leaf.get("description", f"{param_key}({field_id})"),
                "paramTypeString": ref_leaf.get("paramTypeString", "STRING"),
                "dataTypeSting": ref_leaf.get("dataTypeSting", "ATTRIBUTE"),
                "hideParamNameInSelect": True,
                "hideParam": False,
                "componentKey": ref_leaf.get("componentKey", "Text"),
                "readonlyParam": False,
                "sensitiveFlag": False,
                "newdata": False,
                "parentName": ref_leaf.get("parentName", name_display),
                "name": name_display,
                "source": src_id,
                "value": ref_leaf.get("value", f"FormData.{param_key}"),
                "type": "3",
                "formulaType": ref_leaf.get("formulaType", field_type),
                "frontId": str(field_id),
                "tableId": ref_leaf.get("tableId", ""),
                "paramId": ref_leaf.get("paramId", param_key),
                "position": ref_leaf.get("position", str(gen_id())),
                "formulaId": "0",
                "mappingId": "0",
                "config": {
                    "paramKey": param_key,
                    "paramType": field_type,
                    "parentName": ref_leaf.get("parentName", name_display),
                    "newParentName": ref_leaf.get("parentName", name_display),
                    "multKey": "", "multName": "",
                    "multTypeObj": {
                        "allName": name_display, "currentName": name_display,
                        "currentParamKey": f"FormData.{param_key}",
                        "allParamKey": f"FormData.{param_key}",
                    },
                    "comId": src_id, "isMultCom": False,
                    "comType": "ApproveTrigger", "parentComId": "0",
                    "tableName": "表单数据",
                    "fieldInfo": {
                        "tablePrimaryKey": "FormData", "paramKey": param_key,
                    },
                    "tempFormulaId": str(action_id) if action_id else "",
                    "formulaVersion": "V1",
                },
            })
    return entries

def _build_skeleton_node(action_type: str, previous_node_id: str,
                         action_index: int = 0) -> dict:
    """保底模式: convert 失败的 action 骨架节点 — 保留类型/连线/最小 data.

    框架正确（event + 节点 + 连线）但字段内容为空壳，供暂存预览。
    """
    comp = get_component(action_type) or {}
    disp = comp.get("display", {}) or {}
    node_id = str(gen_id())
    node = {
        "id": node_id,
        "wId": node_id,
        "name": disp.get("typeName", disp.get("componentName", action_type)),
        "nameMultilang": disp.get("typeName", disp.get("componentName", action_type)),
        "type": action_type,
        "typeName": disp.get("typeName", action_type),
        "attr": {"icon": disp.get("icon", "Icon-eb-mcolor")},
        "sources": [{"id": str(previous_node_id), "wId": str(previous_node_id), "status": []}],
        "data": deepcopy(comp.get("defaultData", {}) or {}),
        "parentId": "0",
    }
    if action_type.startswith("ActionEb"):
        node["data"].setdefault("ebActionId", "-1")
        node["data"]["type"] = action_type
    return node

def convert(draft: dict, app_id: str = "", scene_id: str = "", metadata_path: str = "",
            lenient: bool = False) -> dict:
    """draft → 真实设计 JSON.

    lenient=True (保底模式): 单个 action 转换失败时降级为骨架节点
    (_build_skeleton_node), 不中断整体转换 — 保证"框架正确"的版本能落库预览.
    返回 (design, lenient_warnings)。
    """
    meta = None
    if metadata_path:
        meta = load_metadata(metadata_path)
    else:
        try: meta = load_metadata()
        except (FileNotFoundError, json.JSONDecodeError): pass
    if not isinstance(meta, dict):
        meta = {}

    draft_event = draft.get("event", {})
    draft_actions = draft.get("actions", [])
    lenient_warnings: list[str] = []
    if "resolvedPlan" in draft:
        rp = draft["resolvedPlan"]
        draft_event = rp.get("event", {})
        draft_actions = rp.get("actions", [])

    event_node = convert_node(draft_event, is_event=True, meta=meta, app_id=app_id)
    event_id = event_node["id"]
    # event 节点的 attr.name / typeName 作为上游组件名,供 parentName 拼接
    event_name = str(event_node.get("attr", {}).get("componentName")
                      or event_node.get("data", {}).get("typeName")
                      or event_node.get("name", "") or "流程触发")
    event_data = event_node.get("data", {})
    workflow_path = event_data.get("workflowPath", [])
    workflow_id = ""
    if isinstance(workflow_path, list) and workflow_path and isinstance(workflow_path[0], dict):
        workflow_id = str(workflow_path[0].get("id", ""))
    if not workflow_id and isinstance(draft_event, dict):
        event_params = draft_event.get("params") or {}
        event_workflow_path = event_params.get("workflowPath") if isinstance(event_params, dict) else None
        if isinstance(event_workflow_path, dict):
            workflow_id = str(event_workflow_path.get("id", ""))
        if not workflow_id:
            workflow_id = str(draft_event.get("workflowId", ""))
    #  EventFormData 数据触发没有 workflowPath — 上下文是
    # form-context (FormData.{formId}.{fieldId}). 用事件 dataSource/targetForm.id
    # 作为 formId 标识, 让 _resolve_param_key 按 _WORKFLOW_FIELD_IDS[formId] 映射.
    if not workflow_id and isinstance(event_data, dict):
        _ds = event_data.get("dataSource") or {}
        _ds_id = str(_ds.get("id") or "") if isinstance(_ds, dict) else ""
        if not _ds_id:
            _tf = event_data.get("targetForm") or {}
            _ds_id = str(_tf.get("id") or event_data.get("objId") or "") if isinstance(_tf, dict) else str(event_data.get("objId") or "")
        if _ds_id:
            workflow_id = _ds_id
    workflow_module = str(event_data.get("module", "workflow"))

    real_actions = []
    previous_node = event_node
    # 预登记 workflow_id 到 meta,供 convert_node 内部 _fill_setting 生成 paramKey 用 id 格式
    if workflow_id and isinstance(meta, dict):
        meta["_workflow_id"] = workflow_id
        #  注入事件绑定表单 id (_event_form_id).
        # 区分 FormData 系统字段(paramKey 前缀=表单id, 如 '{formId}.id' 数据ID) vs
        # ApprovalData 字段(paramKey 前缀=流程id, 如 '{workflowId}.requestId') —
        # 两者末段都非数字, _assign_flat_context_direct 靠它判组, 否则数据ID引用
        # (TimeBatchTrigger 的 FormData.{formId}.id) 会被误判成 ApprovalData → 错组标红.
        # (paramKey 前缀=流程id) 误判成 FormData 组 (dataId 回读 FormData. 前缀错误).
        # DateTrigger/EnquiryForm) 无 workflowPath — workflow_id 即表单 id
        # (dataSource.id/targetForm.id), 数据ID 引用 '{formId}.id' 前缀=表单id →
        # 必须归 FormData 组, 否则 updateId 回读 ApprovalData.{formId}.id 错前缀.
        # 仅 ApproveTrigger (workflow_id=流程id) 不能 fallback, 取不到留空.
        _event_form_id = ""
        _wf_fids = []
        if isinstance(workflow_path, list) and workflow_path and isinstance(workflow_path[0], dict):
            _wf_fids = workflow_path[0].get("formIds") or []
        elif isinstance(workflow_path, dict) and workflow_path:
            _wf_fids = workflow_path.get("formIds") or []
        if _wf_fids:
            _event_form_id = str(_wf_fids[0])
        else:
            _ev_type = str((draft_event or {}).get("type", ""))
            if _ev_type in ("TimeBatchTrigger", "EventFormData", "DateTrigger", "EnquiryForm"):
                _event_form_id = workflow_id
        meta["_event_form_id"] = _event_form_id
        meta["_upstream_component_type"] = str(
            (draft_event or {}).get("type", "") or "ApproveTrigger"
        )
        #  同时注入流程名, 供主表 type=3 直连判断 ApprovalData 系统字段
        # (paramKey 末段非数字, 如 requestId) 时 parentName 用 "流程名.xxx" 前缀 —
        # 前端 cacheContext 按 parentName 归类到「流程触发[流程数据]」组; 用目标表单名前缀
        # 会被前端归类到「流程触发[表单数据]」组 → 该组无 requestId 字段 → 标"已删除".
        wf_name = ""
        # workflowPath 形态兼容: list (完整) / dict (enrich 自动补 {id})
        if isinstance(workflow_path, list) and workflow_path and isinstance(workflow_path[0], dict):
            wf_name = str(workflow_path[0].get("name") or workflow_path[0].get("text") or "")
        elif isinstance(workflow_path, dict) and workflow_path:
            wf_name = str(workflow_path.get("name") or workflow_path.get("text") or "")
        # 兜底1: plan/draft 顶层 workflowName 字段 (网络断/无 workflowPath.name 时手动提供)
        if not wf_name and isinstance(draft, dict):
            wf_name = str(draft.get("workflowName", ""))
        # 兜底2: approveNode.workflowName (compile 后 draft 只保留 event/actions,
        # workflowPath 被 enrich 精简为 {id} 无 name, 但 approveNode 带完整 workflowName)
        if not wf_name and isinstance(draft, dict):
            _ev_params = (draft.get("event") or {}).get("params") or {}
            _an = _ev_params.get("approveNode") if isinstance(_ev_params, dict) else None
            if isinstance(_an, dict):
                wf_name = str(_an.get("workflowName") or "")
        meta["_upstream_workflow_name"] = wf_name
        #  非流程触发 (DateTrigger/TimeBatchTrigger/EventFormData)
        # 的事件源是**表单** — 注入 _upstream_form_name (dataSource/targetForm 的表单名),
        # 供 ApproveCreate 兜底分支 parentName 前缀用 ("{表单名}.{字段名}", 如
        # "会议信息.开始时间"). 有流程名时 _upstream_workflow_name 优先, 表单名作兜底.
        if not meta.get("_upstream_form_name") and isinstance(event_data, dict):
            _src_name = ""
            _ds = event_data.get("dataSource") or {}
            if isinstance(_ds, dict):
                _src_name = str(_ds.get("text") or _ds.get("name") or "")
            if not _src_name:
                _tf = event_data.get("targetForm") or {}
                if isinstance(_tf, dict):
                    _src_name = str(_tf.get("text") or _tf.get("name") or "")
            if _src_name:
                meta["_upstream_form_name"] = _src_name
        # 注入上游触发器节点 wId (event_node.wId) 给 _build_condition_detail,
        # 让 customFieldType.config.comId/selectType 用上游 actionFlow wId,
        # 前端 isLegalContextVar 才能在 cacheContext[comId] 找到 contextData.
        meta["_upstream_w_id"] = str(event_node.get("id") or "")
        # 若 design 顶层注入了 _visible_form_ids (来自 _resolve_condition_ids 的
        # ESB conditionFieldBrowser 预取), 复制到 meta 让 convert_condition 阶段
        # 的 _build_condition_detail 用 "{formId}.{fieldId}" 格式.
        if isinstance(draft, dict):
            vf = draft.get("_visible_form_ids")
            if isinstance(vf, dict) and vf:
                meta["_visible_form_ids"] = vf
    for i, a in enumerate(draft_actions):
        _prev_id = previous_node["id"]
        try:
            if a.get("type") == "Condition":
                node = convert_condition(a, meta=meta, app_id=app_id,
                                         action_index=i, event_id=event_id,
                                         previous_node_id=_prev_id, lenient=lenient)
            else:
                node = convert_node(a, meta=meta, app_id=app_id,
                                    action_index=i, event_node_id=event_id,
                                    event_name=event_name,
                                    previous_node_id=_prev_id, lenient=lenient)
        except Exception as exc:
            if not lenient:
                raise
            node = _build_skeleton_node(str(a.get("type", "")), _prev_id, i)
            lenient_warnings.append(
                f"actions[{i}]({a.get('type')}) 转换失败已降级为骨架节点(字段未生成): {exc}")
        # e-builder 数据动作在前端会从 ApproveTrigger 继承流程绑定.
        # 这两个字段是 getWorkflowFields / getComponentContext 查询源流程上下文的前提,
        # 不应要求模型重复填写,也不能遗漏.
        # 只有 Add/Update 需要继承.
        if a.get("type") in {"ActionEbAdd", "ActionEbUpdate"} and workflow_id:
            node_data = node.setdefault("data", {})
            node_data.setdefault("workflowModule", workflow_module)
            node_data.setdefault("workflowId", workflow_id)
        real_actions.append(node)
        # 登记 meta 的 workflow_id,供后续 _fill_setting 生成 paramKey 用 id 格式
        if workflow_id and isinstance(meta, dict):
            meta["_workflow_id"] = workflow_id
        previous_node = node

    # 公式中的 source 不能保留 event/action_1 等语义别名。所有节点已生成后
    # 再替换，分支内和主链中的公式都可以引用前序真实节点。
    source_node_ids = {"event": str(event_node["id"]), "trigger": str(event_node["id"])}
    _register_real_node_ids(draft_event, event_node, source_node_ids)
    for draft_action, real_action in zip(draft_actions, real_actions):
        _register_real_node_ids(draft_action, real_action, source_node_ids)
    _replace_formula_source_aliases(real_actions, source_node_ids)

    # 构建 reloadFormula: 从 setting.main 的 context 赋值提取映射元数据
    reload_formula = _build_reload_formula(real_actions, event_id, app_id)

    assist = build_assist_layer(event_node, real_actions)
    design = {
        "appId": str(app_id) if app_id else str(gen_id()),
        "sceneId": str(scene_id) if scene_id else str(gen_id()),
        "event": event_node,
        "actions": real_actions,
        "assistLayer": json.dumps(assist, ensure_ascii=False),
        "reloadFormula": reload_formula,
        "version": 1,
    }
    # 平台契约:真实设计 JSON 中所有 id 标识(节点 id/wId/componentId,以及公式 bean、
    # person 公式、condition 详情等深层嵌套里的 id)必须为字符串.递归强转兜底层,
    # 防止任何分支漏改导致设计器解析不一致.
    design = _coerce_ids_to_str(design)
    if lenient:
        # 保底模式降级说明随 design 返回(隐藏 key), 调用方取用后移除, 不落库
        design["_lenient_warnings"] = lenient_warnings
    return design

def _coerce_ids_to_str(obj):
    """递归把树中所有 id 类字段(id/wId/componentId/parentId/parentNode/frontId)统一为字符串."""
    ID_KEYS = ("id", "wId", "componentId", "parentId", "parentNode", "frontId")
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ID_KEYS and isinstance(v, (int, float)) and not isinstance(v, bool):
                obj[k] = str(v)
            else:
                _coerce_ids_to_str(v)
    elif isinstance(obj, list):
        for item in obj:
            _coerce_ids_to_str(item)
    return obj

# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="WorkflowDraft -> ESB Real JSON 转换器 (v3)")
    p.add_argument("draft", help="WorkflowDraft JSON 路径")
    p.add_argument("--app-id", default="", help="应用 ID")
    p.add_argument("--scene-id", default="", help="场景 ID")
    p.add_argument("-o", "--output", default=None, help="输出路径 (默认 stdout)")
    p.add_argument("--metadata", default="", help="元数据路径 (默认 auto)")
    p.add_argument("--no-metadata", action="store_true", help="禁用元数据")

    args = p.parse_args()
    with open(args.draft, "r", encoding="utf-8") as f:
        draft = json.load(f)

    md = "" if args.no_metadata else args.metadata
    design = convert(draft, args.app_id, args.scene_id, md)

    out = json.dumps(design, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"✅ 转换完成 -> {args.output}")
    else:
        print(out)

    evt = design["event"]["type"]
    acts = len(design["actions"])
    total = acts + sum(len(a["data"].get("trueBranchActions", [])) + len(a["data"].get("falseBranchActions", []))
                       for a in design["actions"] if a["type"] == "Condition")
    print(f"\n📊 事件: {evt}  |  动作: {acts} (含分支 {total} 节点)", file=sys.stderr)
