from backend.services.change_detection_service import detect_changes
from backend.database.models import Audit, Page, SEOIssue

def test_detect_changes_score_decrease():
    old = Audit(score=90)
    new = Audit(score=80)
    res = detect_changes(old, new, [], [], [], [])
    assert res["score_change"] == -10
    assert res["change_severity"] == "CRITICAL"
    assert res["has_changes"] is True

def test_detect_changes_score_increase():
    old = Audit(score=80)
    new = Audit(score=90)
    res = detect_changes(old, new, [], [], [], [])
    assert res["score_change"] == 10
    assert res["change_severity"] == "LOW"
    assert res["has_changes"] is True

def test_detect_changes_new_issue():
    old = Audit(score=90)
    new = Audit(score=90)
    new_issue = SEOIssue(issue_code="MISSING_H1", page_url="http://test.com", severity="HIGH", title="Missing H1")
    res = detect_changes(old, new, [], [], [], [new_issue])
    assert len(res["new_issues"]) == 1
    assert res["new_issues"][0]["code"] == "MISSING_H1"
    assert res["change_severity"] == "HIGH"
    assert res["has_changes"] is True

def test_detect_changes_resolved_issue():
    old = Audit(score=90)
    new = Audit(score=90)
    old_issue = SEOIssue(issue_code="MISSING_H1", page_url="http://test.com", severity="HIGH", title="Missing H1")
    res = detect_changes(old, new, [], [], [old_issue], [])
    assert len(res["resolved_issues"]) == 1
    assert res["resolved_issues"][0]["code"] == "MISSING_H1"
    assert res["change_severity"] == "LOW"
    assert res["has_changes"] is True

def test_detect_changes_no_change():
    old = Audit(score=90)
    new = Audit(score=90)
    res = detect_changes(old, new, [], [], [], [])
    assert res["has_changes"] is False
    assert res["change_severity"] == "NO_CHANGE"
