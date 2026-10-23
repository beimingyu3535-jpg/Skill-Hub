"""查询与批量触发器共用的默认字段选择。"""
from __future__ import annotations

from core.runtime_metadata import _TARGET_DETAIL_FIELDS, _TARGET_FORM_FIELDS


#      Employee/Ebuilder 等在上下文里本来就是 string, 不要映射成 object)
def _default_query_fields_all(ds_id: str) -> list[dict]:
    """queryFields 缺省时默认**全选**目标表单主表字段 .

    实现: 调 showDataSourceFields 拿完整可选字段 (业务+系统变量), 用**真实 id**
    (业务=数字字段id, 系统变量=英文字符串 'id'/'name'/'creator'/'create_time'/'update_time'/
    'updater'/'data_status'/'batchmytags'/'batchpubtags'). 平台拒绝 id=formId 之类的伪造
    (回读会被过滤). 失败 fallback 到 _TARGET_FORM_FIELDS 业务字段缓存.
    """
    if not ds_id:
        return []
    try:
        from core.platform_client import make_client
        _client = make_client()
        _dsf_resp = _client.get_data_source_fields(ds_id, "")
        _dsf_data = (_dsf_resp.get("data") if isinstance(_dsf_resp, dict) else _dsf_resp) or []
        items: list[dict] = []
        for _grp in _dsf_data if isinstance(_dsf_data, list) else []:
            if not isinstance(_grp, dict):
                continue
            _grp_id = str(_grp.get("formId", ""))
            for _f in _grp.get("fields") or []:
                if not isinstance(_f, dict) or not _f.get("id"):
                    continue
                items.append({
                    "formId": _grp_id,
                    "parseMark": bool(_f.get("parseMark", False)),
                    "id": str(_f["id"]),
                    "content": str(_f.get("content") or _f.get("id")),
                })
        if items:
            return items
    except Exception:
        pass
    # fallback: 业务字段缓存 (缓存缺失回退 [数据ID])
    fields = _TARGET_FORM_FIELDS.get(str(ds_id), {})
    detail_ids: set[str] = set()
    for _dt_fields in _TARGET_DETAIL_FIELDS.get(str(ds_id), {}).values():
        detail_ids.update(str(fid) for fid in (_dt_fields or {}))
    items = []
    for fid, f in fields.items():
        if str(fid) in detail_ids:
            continue
        items.append({
            "formId": str(ds_id),
            "parseMark": True,
            "id": str(fid),
            "content": str(f.get("showName") or f.get("name") or fid),
        })
    if items:
        return items
