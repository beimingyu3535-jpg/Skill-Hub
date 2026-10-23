"""字段自动映射的类型兼容与匹配规则。"""
from __future__ import annotations

_COMPONENT_GROUPS: dict[str, set[str]] = {
    "single_text": {"Text", "Email", "Phone", "Mobile", "IDCard"},
    "multi_text": {"TextArea"},
    "number": {"NumberComponent", "Money", "Monitor", "Raty", "ProgressBar"},
    "date": {"DateComponent", "TimeComponent"},
    "select": {"Select", "RadioBox", "CheckBox", "ImageRadioBox", "ImageCheckBox"},
    "other": {"RelateBrowser", "TreeSelect", "FileComponent", "ImageComponent",
              "Location", "PositionComponent", "SignatureComponent", "Attachment", "File", "Image"},
}

RELATE_FIELDS = {
    "Department", "Subcompany", "Employee", "Mainline", "Task", "Document", "Workflow",
    "CustomerComponent", "ContactComponent", "ChanceComponent", "ProductionComponent",
    "ContractComponent", "ActivityComponent", "AgendaComponent", "FormComponent",
    "ClueComponent", "OrderComponent", "WorkreportComponent", "CompetitorComponent",
    "KpiFlowComponent", "Ebuilder", "QuoteComponent", "AttendComponent",
    "ODocReceiveComponent", "HrmGrade", "HrmPosition", "CashBook", "RelateODoc",
    "EinvoiceComponent", "Invoice", "DataSource", "TreeSelect", "RelateBrowser",
    "EmployeeOrganization",
}

def component_group(component_key: str) -> str:
    for group, keys in _COMPONENT_GROUPS.items():
        if component_key in keys:
            return group
    return f"relation:{component_key}" if component_key in RELATE_FIELDS else ""

def lcs_len(left: str, right: str) -> int:
    rows, columns = len(left), len(right)
    dp = [[0] * (columns + 1) for _ in range(rows + 1)]
    longest = 0
    for row in range(1, rows + 1):
        for column in range(1, columns + 1):
            if left[row - 1] == right[column - 1]:
                dp[row][column] = 1 + dp[row - 1][column - 1]
                longest = max(longest, dp[row][column])
    return longest

def auto_map_fields(target_fields: list[dict], source_fields: list[dict]) -> dict[str, str]:
    """按名称相似度和字段类型一对一匹配未显式指定的字段。"""
    result: dict[str, str] = {}
    used: set[str] = set()
    for target in target_fields:
        target_id = str(target.get("id") or "")
        target_name = str(target.get("showName") or "")
        target_key = str(target.get("componentKey") or "")
        if not target_id or not target_name:
            continue
        best: dict | None = None
        best_like = 0
        for source in source_fields:
            source_name = str(source.get("showName") or "")
            source_key = str(source.get("componentKey") or "")
            if not source_name or source_name in used:
                continue
            if target_key in RELATE_FIELDS:
                if source_key != target_key:
                    continue
            elif not component_group(target_key) or component_group(source_key) != component_group(target_key):
                continue
            if source_name == target_name:
                best = source
                break
            like = lcs_len(source_name, target_name)
            if like > 1 and like > best_like:
                best_like, best = like, source
        if best:
            result[str(best["showName"])] = target_id
            used.add(str(best["showName"]))
    return result
