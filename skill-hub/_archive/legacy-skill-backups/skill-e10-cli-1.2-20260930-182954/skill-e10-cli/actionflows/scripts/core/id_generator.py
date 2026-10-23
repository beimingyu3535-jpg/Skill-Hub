"""平台设计 JSON 使用的节点与公式 ID 生成器。"""
from __future__ import annotations

import time
import uuid

# ── ID 生成 ─────────────────────────────────────────────────────────────────

# ── ID 生成  ───────────────────────────────────────────────────
# gen_sf_id: 雪花 ID 字符串 (前端 SnowFlake.nextId: bigInt.toString(10)),
# 仅用于 event 节点 id — platform 保存时按真实注册 id 重写 basisValueFormula.source;
# event id 非雪花格式时注册 id ≠ event.id → 设计器 basisValue source 失配标红.
_SF_TWEPOCH = 1577836800000
_SF_WORKER = 1
_SF_DC = 1
_SF_SEQ: dict = {"s": 0, "last": 0}

def gen_id() -> int:
    """随机 15 位 ID (2^53 内, JSON number 安全)."""
    return 10**14 + uuid.uuid4().int % (9 * 10**14)

def gen_sf_id() -> str:
    """雪花 ID 字符串 (前端 SnowFlake 同参数, event 节点专用)."""
    ts = int(time.time() * 1000)
    if ts < _SF_SEQ["last"]:
        ts = _SF_SEQ["last"]
    if ts == _SF_SEQ["last"]:
        _SF_SEQ["s"] = (_SF_SEQ["s"] + 1) & 4095
        if _SF_SEQ["s"] == 0:
            ts += 1
    else:
        _SF_SEQ["s"] = 0
    _SF_SEQ["last"] = ts
    return str(((ts - _SF_TWEPOCH) << 22) | (_SF_DC << 17) | (_SF_WORKER << 12) | _SF_SEQ["s"])

def _next_id(prefix="", counter=[0]):
    counter[0] += 1
    return counter[0]

# ── 流程字段 id 映射 (workflowId → {字段名: 字段id}) ─────────────────────
