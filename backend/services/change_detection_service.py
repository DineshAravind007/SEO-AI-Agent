from typing import Dict, Any, List
from backend.database.models import Audit, Page, SEOIssue

def detect_changes(old_audit: Audit, new_audit: Audit, old_pages: List[Page], new_pages: List[Page], old_issues: List[SEOIssue], new_issues: List[SEOIssue]) -> Dict[str, Any]:
    score_old = old_audit.score if old_audit else None
    score_new = new_audit.score if new_audit else None
    score_change = (score_new - score_old) if (score_new is not None and score_old is not None) else 0

    critical_old = sum(1 for i in old_issues if i.severity.lower() == "critical")
    critical_new = sum(1 for i in new_issues if i.severity.lower() == "critical")
    high_old = sum(1 for i in old_issues if i.severity.lower() == "high")
    high_new = sum(1 for i in new_issues if i.severity.lower() == "high")
    medium_old = sum(1 for i in old_issues if i.severity.lower() == "medium")
    medium_new = sum(1 for i in new_issues if i.severity.lower() == "medium")
    low_old = sum(1 for i in old_issues if i.severity.lower() == "low")
    low_new = sum(1 for i in new_issues if i.severity.lower() == "low")

    # Detect new and resolved issues by (issue_code, page_url) pair
    old_keys = {f"{i.issue_code}:{i.page_url}": i for i in old_issues}
    new_keys = {f"{i.issue_code}:{i.page_url}": i for i in new_issues}

    resolved_keys = set(old_keys.keys()) - set(new_keys.keys())
    added_keys = set(new_keys.keys()) - set(old_keys.keys())

    # De-duplicate by issue_code for summary display (take first occurrence)
    seen_resolved = set()
    resolved_list = []
    for k in resolved_keys:
        i = old_keys[k]
        if i.issue_code not in seen_resolved:
            seen_resolved.add(i.issue_code)
            resolved_list.append({"code": i.issue_code, "title": i.title or i.issue_code, "url": i.page_url, "severity": i.severity})

    seen_added = set()
    added_list = []
    for k in added_keys:
        i = new_keys[k]
        if i.issue_code not in seen_added:
            seen_added.add(i.issue_code)
            added_list.append({"code": i.issue_code, "title": i.title or i.issue_code, "url": i.page_url, "severity": i.severity})

    # Determine overall severity of changes
    severity = "NO_CHANGE"
    
    if old_audit and new_audit:
        if score_change <= -10 or any(i.severity.lower() == "critical" for k in added_keys for i in [new_keys[k]]):
            severity = "CRITICAL"
        elif score_change <= -5 or any(i.severity.lower() == "high" for k in added_keys for i in [new_keys[k]]):
            severity = "HIGH"
        elif score_change <= -2 or any(i.severity.lower() == "medium" for k in added_keys for i in [new_keys[k]]):
            severity = "MEDIUM"
        elif score_change != 0 or added_keys or resolved_keys:
            severity = "LOW"
    
    return {
        "score_old": score_old,
        "score_new": score_new,
        "score_change": score_change,
        "critical_old": critical_old,
        "critical_new": critical_new,
        "high_old": high_old,
        "high_new": high_new,
        "medium_old": medium_old,
        "medium_new": medium_new,
        "low_old": low_old,
        "low_new": low_new,
        "pages_old": len(old_pages) if old_pages else 0,
        "pages_new": len(new_pages) if new_pages else 0,
        "resolved_issues": resolved_list,
        "new_issues": added_list,
        "change_severity": severity,
        "has_changes": bool(score_change != 0 or added_keys or resolved_keys)
    }
