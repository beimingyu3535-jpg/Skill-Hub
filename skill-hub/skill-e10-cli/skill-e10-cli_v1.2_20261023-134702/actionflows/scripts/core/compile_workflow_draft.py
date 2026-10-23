from __future__ import annotations

from typing import Any

from core.build_workflow_draft import build_workflow_draft, normalize_semantic_plan
from core.validate import validate_semantic_plan, validate_workflow_draft

def compile_workflow_draft(plan: dict[str, Any]) -> dict[str, Any]:
    # 先归一 AI 友好/旧版别名，再做语义校验，避免 formField/type:context
    # 这类可兼容输入在校验阶段被过早拒绝。
    normalized_plan = normalize_semantic_plan(plan)
    semantic_result = validate_semantic_plan(normalized_plan)
    if not semantic_result["valid"]:
        return {
            "draft": None,
            "valid": False,
            "errors": semantic_result["errors"],
            "warnings": semantic_result["warnings"],
        }

    draft = build_workflow_draft(normalized_plan)
    draft_result = validate_workflow_draft(draft)
    return {
        "draft": draft,
        "valid": draft_result["valid"],
        "errors": draft_result["errors"],
        "warnings": [*semantic_result["warnings"], *draft_result["warnings"]],
    }
