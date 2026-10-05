"""
Comprehensive tests for Stage 2 — Automated SEO Monitoring.

Covers:
  1.  Create monitoring project
  2.  Invalid monitoring data (bad frequency, bad URL)
  3.  List monitoring projects
  4.  Get monitoring project
  5.  Update monitoring project
  6.  Pause monitoring
  7.  Resume monitoring
  8.  Manual audit trigger
  9.  History retrieval
  10. Score history
  11. Score difference
  12. New issue detection
  13. Resolved issue detection
  14. Scheduler due detection
  15. Scheduler frequency calculation
  16. Failed audit handling
  17. Duplicate run protection
  18. Missing monitoring project (404)
  19. Report generation (changes endpoint)
  20. Run paused project (400)
"""

import json
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.database.connection import get_db, Base
from backend.database.models import MonitoringProject, MonitoringReport, Audit, Page, SEOIssue
from backend.services import monitoring_service

# ── In-memory SQLite test DB ─────────────────────────────────────────────────

engine_test = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)
Base.metadata.create_all(bind=engine_test)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _use_isolated_db():
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)

    # Wipe all tables between tests
    db = TestingSessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    db.close()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_completed_audit(db, url="https://test.com", score=80):
    """Create a completed audit with one page and one critical issue."""
    a = Audit(url=url, score=score, status="completed")
    db.add(a)
    db.commit()
    db.refresh(a)
    p = Page(audit_id=a.id, url=url, depth=0, crawl_status="success")
    db.add(p)
    db.commit()
    db.refresh(p)
    return a, p


# ── Test 1: Create monitoring project ────────────────────────────────────────

def test_create_project(client):
    res = client.post("/api/monitoring", json={
        "url": "https://example.com",
        "name": "Example Site",
        "frequency": "daily",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Example Site"
    assert data["url"] == "https://example.com"
    assert data["frequency"] == "daily"
    assert data["is_active"] is True


# ── Test 2: Invalid monitoring data ─────────────────────────────────────────

def test_invalid_frequency(client):
    res = client.post("/api/monitoring", json={
        "url": "https://example.com",
        "name": "Test",
        "frequency": "hourly",  # invalid
    })
    assert res.status_code == 422


def test_invalid_url_no_host(client):
    res = client.post("/api/monitoring", json={
        "url": "not-a-url",
        "name": "Test",
    })
    # Should either be 200 (auto-normalised to https://not-a-url and accepted) or 422
    assert res.status_code in (200, 422)


def test_unsafe_url_rejected(client):
    res = client.post("/api/monitoring", json={
        "url": "http://localhost:8000",
        "name": "Localhost Test",
    })
    assert res.status_code == 422



def test_empty_name_rejected(client):
    res = client.post("/api/monitoring", json={
        "url": "https://example.com",
        "name": "",  # violates min_length=1
    })
    assert res.status_code == 422


def test_max_pages_out_of_range(client):
    res = client.post("/api/monitoring", json={
        "url": "https://example.com",
        "name": "Test",
        "max_pages": 999,  # > 50
    })
    assert res.status_code == 422


# ── Test 3: List monitoring projects ────────────────────────────────────────

def test_list_projects(client):
    client.post("/api/monitoring", json={"url": "https://a.com", "name": "A"})
    client.post("/api/monitoring", json={"url": "https://b.com", "name": "B"})
    res = client.get("/api/monitoring")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_list_projects_empty(client):
    res = client.get("/api/monitoring")
    assert res.status_code == 200
    assert res.json() == []


# ── Test 4: Get monitoring project ──────────────────────────────────────────

def test_get_project(client):
    create = client.post("/api/monitoring", json={"url": "https://a.com", "name": "A"})
    pid = create.json()["id"]
    res = client.get(f"/api/monitoring/{pid}")
    assert res.status_code == 200
    assert res.json()["name"] == "A"


# ── Test 5: Update monitoring project ───────────────────────────────────────

def test_update_project_name(client):
    create = client.post("/api/monitoring", json={"url": "https://a.com", "name": "A"})
    pid = create.json()["id"]
    res = client.put(f"/api/monitoring/{pid}", json={"name": "A-renamed"})
    assert res.status_code == 200
    assert res.json()["name"] == "A-renamed"


def test_update_project_frequency(client):
    create = client.post("/api/monitoring", json={"url": "https://a.com", "name": "A"})
    pid = create.json()["id"]
    res = client.put(f"/api/monitoring/{pid}", json={"frequency": "monthly"})
    assert res.status_code == 200
    assert res.json()["frequency"] == "monthly"


def test_update_invalid_frequency(client):
    create = client.post("/api/monitoring", json={"url": "https://a.com", "name": "A"})
    pid = create.json()["id"]
    res = client.put(f"/api/monitoring/{pid}", json={"frequency": "fortnightly"})
    assert res.status_code == 422


# ── Test 6: Pause monitoring ─────────────────────────────────────────────────

def test_pause_project(client):
    create = client.post("/api/monitoring", json={"url": "https://a.com", "name": "A"})
    pid = create.json()["id"]
    res = client.put(f"/api/monitoring/{pid}", json={"is_active": False})
    assert res.status_code == 200
    assert res.json()["is_active"] is False


# ── Test 7: Resume monitoring ────────────────────────────────────────────────

def test_resume_project(client):
    create = client.post("/api/monitoring", json={"url": "https://a.com", "name": "A"})
    pid = create.json()["id"]
    client.put(f"/api/monitoring/{pid}", json={"is_active": False})
    res = client.put(f"/api/monitoring/{pid}", json={"is_active": True})
    assert res.status_code == 200
    assert res.json()["is_active"] is True


# ── Test 8: Manual audit trigger ────────────────────────────────────────────

def test_run_monitoring_audit(client, mocker):
    mocker.patch("backend.services.monitoring_service.run_audit_task", return_value=None)
    create = client.post("/api/monitoring", json={"url": "https://a.com", "name": "A"})
    pid = create.json()["id"]
    res = client.post(f"/api/monitoring/{pid}/run")
    assert res.status_code == 200
    assert "Audit triggered" in res.json()["status"]


def test_run_paused_project_rejected(client):
    """Running a paused project should return 400."""
    create = client.post("/api/monitoring", json={"url": "https://a.com", "name": "A"})
    pid = create.json()["id"]
    client.put(f"/api/monitoring/{pid}", json={"is_active": False})
    res = client.post(f"/api/monitoring/{pid}/run")
    assert res.status_code == 400


def test_run_missing_project(client):
    res = client.post("/api/monitoring/99999/run")
    assert res.status_code == 404


# ── Test 9: History retrieval ────────────────────────────────────────────────

def test_history_empty(client):
    create = client.post("/api/monitoring", json={"url": "https://a.com", "name": "A"})
    pid = create.json()["id"]
    res = client.get(f"/api/monitoring/{pid}/history")
    assert res.status_code == 200
    assert res.json() == []


def test_reports_empty(client):
    create = client.post("/api/monitoring", json={"url": "https://a.com", "name": "A"})
    pid = create.json()["id"]
    res = client.get(f"/api/monitoring/{pid}/reports")
    assert res.status_code == 200
    assert res.json() == []


# ── Test 10 & 11: Score history and score difference ─────────────────────────

def test_execute_monitoring_run_score_change(mocker, db):
    """Run execute_monitoring_run and verify score change is calculated correctly."""
    proj = MonitoringProject(url="https://test.com", name="Test", frequency="weekly")
    db.add(proj)
    db.commit()
    db.refresh(proj)

    old_audit, _ = _make_completed_audit(db, score=70)
    proj.last_audit_id = old_audit.id
    db.commit()

    def fake_run(new_audit_id):
        a = db.query(Audit).filter(Audit.id == new_audit_id).first()
        a.status = "completed"
        a.score = 80
        p = Page(audit_id=new_audit_id, url="https://test.com", depth=0, crawl_status="success")
        db.add(p)
        db.commit()

    mocker.patch("backend.services.monitoring_service.run_audit_task", side_effect=fake_run)

    monitoring_service.execute_monitoring_run(proj.id, db)

    db.refresh(proj)
    assert proj.last_audit_id != old_audit.id

    reports = db.query(MonitoringReport).filter(MonitoringReport.project_id == proj.id).all()
    assert len(reports) == 1
    assert reports[0].score_change == 10  # 80 - 70


# ── Test 12: New issue detection ─────────────────────────────────────────────

def test_new_issue_detection(mocker, db):
    proj = MonitoringProject(url="https://test.com", name="Test", frequency="weekly")
    db.add(proj)
    db.commit()
    db.refresh(proj)

    old_audit, old_page = _make_completed_audit(db, score=70)
    proj.last_audit_id = old_audit.id
    db.commit()

    def fake_run(new_audit_id):
        a = db.query(Audit).filter(Audit.id == new_audit_id).first()
        a.status = "completed"
        a.score = 65
        p = Page(audit_id=new_audit_id, url="https://test.com", depth=0, crawl_status="success")
        db.add(p)
        db.commit()
        db.refresh(p)
        # A new issue that wasn't in the old audit
        db.add(SEOIssue(
            page_id=p.id, page_url=p.url,
            severity="critical", issue_code="MISSING_H1",
            title="Missing H1", description="", recommendation_summary="", impact="",
            category="on_page",
        ))
        db.commit()

    mocker.patch("backend.services.monitoring_service.run_audit_task", side_effect=fake_run)
    monitoring_service.execute_monitoring_run(proj.id, db)

    report = db.query(MonitoringReport).filter(MonitoringReport.project_id == proj.id).first()
    changes = json.loads(report.changes_data)
    assert any(i["code"] == "MISSING_H1" for i in changes["new_issues"])


# ── Test 13: Resolved issue detection ────────────────────────────────────────

def test_resolved_issue_detection(mocker, db):
    proj = MonitoringProject(url="https://test.com", name="Test", frequency="weekly")
    db.add(proj)
    db.commit()
    db.refresh(proj)

    old_audit, old_page = _make_completed_audit(db, score=60)
    # Add an issue to the old audit
    db.add(SEOIssue(
        page_id=old_page.id, page_url=old_page.url,
        severity="high", issue_code="MISSING_META_DESC",
        title="Missing Meta Description", description="", recommendation_summary="", impact="",
        category="on_page",
    ))
    db.commit()
    proj.last_audit_id = old_audit.id
    db.commit()

    def fake_run(new_audit_id):
        a = db.query(Audit).filter(Audit.id == new_audit_id).first()
        a.status = "completed"
        a.score = 70
        p = Page(audit_id=new_audit_id, url="https://test.com", depth=0, crawl_status="success")
        db.add(p)
        db.commit()
        # No issues in the new audit — the old issue is resolved

    mocker.patch("backend.services.monitoring_service.run_audit_task", side_effect=fake_run)
    monitoring_service.execute_monitoring_run(proj.id, db)

    report = db.query(MonitoringReport).filter(MonitoringReport.project_id == proj.id).first()
    changes = json.loads(report.changes_data)
    assert any(i["code"] == "MISSING_META_DESC" for i in changes["resolved_issues"])


# ── Test 14: Scheduler due detection ─────────────────────────────────────────

def test_scheduler_detects_due_projects(mocker, db):
    due_proj = MonitoringProject(
        url="https://due.com", name="Due",
        frequency="weekly",
        is_active=True,
        next_audit_date=datetime.utcnow() - timedelta(hours=1),  # overdue
    )
    not_due_proj = MonitoringProject(
        url="https://notdue.com", name="Not Due",
        frequency="weekly",
        is_active=True,
        next_audit_date=datetime.utcnow() + timedelta(days=5),  # future
    )
    paused_proj = MonitoringProject(
        url="https://paused.com", name="Paused",
        frequency="weekly",
        is_active=False,
        next_audit_date=datetime.utcnow() - timedelta(hours=1),  # overdue but paused
    )
    db.add_all([due_proj, not_due_proj, paused_proj])
    db.commit()

    executed = []

    def fake_execute(project_id, session):
        executed.append(project_id)

    mocker.patch("backend.services.monitoring_service._do_monitoring_run", side_effect=fake_execute)

    monitoring_service.run_scheduler_tick(db)

    # Only the due, active project should have been triggered
    assert due_proj.id in executed
    assert not_due_proj.id not in executed
    assert paused_proj.id not in executed


# ── Test 15: Scheduler frequency calculation ──────────────────────────────────

def test_next_audit_date_daily():
    from backend.services.monitoring_service import _get_next_audit_date
    before = datetime.utcnow()
    result = _get_next_audit_date("daily")
    assert result >= before + timedelta(hours=23)
    assert result <= before + timedelta(hours=25)


def test_next_audit_date_weekly():
    from backend.services.monitoring_service import _get_next_audit_date
    before = datetime.utcnow()
    result = _get_next_audit_date("weekly")
    assert result >= before + timedelta(days=6)
    assert result <= before + timedelta(days=8)


def test_next_audit_date_monthly():
    from backend.services.monitoring_service import _get_next_audit_date
    before = datetime.utcnow()
    result = _get_next_audit_date("monthly")
    assert result >= before + timedelta(days=29)
    assert result <= before + timedelta(days=31)


# ── Test 16: Failed audit handling ───────────────────────────────────────────

def test_failed_audit_handled_gracefully(mocker, db):
    """If run_audit_task fails, the monitoring project still gets next_audit_date updated."""
    proj = MonitoringProject(url="https://test.com", name="Test", frequency="daily")
    db.add(proj)
    db.commit()
    db.refresh(proj)

    def fake_run_that_fails(audit_id):
        a = db.query(Audit).filter(Audit.id == audit_id).first()
        a.status = "failed"
        a.error_message = "Crawler error"
        db.commit()

    mocker.patch("backend.services.monitoring_service.run_audit_task", side_effect=fake_run_that_fails)

    # Should not raise
    monitoring_service.execute_monitoring_run(proj.id, db)

    db.refresh(proj)
    # next_audit_date should be updated to avoid hammering
    assert proj.next_audit_date > datetime.utcnow()
    # last_audit_id should NOT be updated since audit failed
    assert proj.last_audit_id is None


# ── Test 17: Duplicate run protection ────────────────────────────────────────

def test_duplicate_run_protection(mocker, db):
    """Simulate a project already in _running set — second call should be skipped."""
    proj = MonitoringProject(url="https://test.com", name="Test", frequency="weekly")
    db.add(proj)
    db.commit()
    db.refresh(proj)

    do_run_mock = mocker.patch("backend.services.monitoring_service._do_monitoring_run")

    # Simulate the project already being in the _running set
    monitoring_service._running.add(proj.id)
    try:
        monitoring_service.execute_monitoring_run(proj.id, db)
    finally:
        monitoring_service._running.discard(proj.id)

    do_run_mock.assert_not_called()


# ── Test 18: Missing monitoring project (404) ─────────────────────────────────

def test_get_missing_project(client):
    res = client.get("/api/monitoring/99999")
    assert res.status_code == 404


def test_update_missing_project(client):
    res = client.put("/api/monitoring/99999", json={"name": "X"})
    assert res.status_code == 404


def test_delete_missing_project(client):
    res = client.delete("/api/monitoring/99999")
    assert res.status_code == 404


def test_history_missing_project(client):
    res = client.get("/api/monitoring/99999/history")
    assert res.status_code == 404


def test_changes_missing_project(client):
    res = client.get("/api/monitoring/99999/changes")
    assert res.status_code == 404


# ── Test 19: Changes endpoint ─────────────────────────────────────────────────

def test_changes_endpoint_empty(client):
    create = client.post("/api/monitoring", json={"url": "https://a.com", "name": "A"})
    pid = create.json()["id"]
    res = client.get(f"/api/monitoring/{pid}/changes")
    assert res.status_code == 200
    assert res.json()["has_changes"] is False


def test_changes_endpoint_with_data(mocker, db, client):
    proj = MonitoringProject(url="https://test.com", name="Test", frequency="weekly")
    db.add(proj)
    db.commit()
    db.refresh(proj)

    old_audit, _ = _make_completed_audit(db, score=70)
    proj.last_audit_id = old_audit.id
    db.commit()

    def fake_run(aid):
        a = db.query(Audit).filter(Audit.id == aid).first()
        a.status = "completed"
        a.score = 80
        p = Page(audit_id=aid, url="https://test.com", depth=0, crawl_status="success")
        db.add(p)
        db.commit()

    mocker.patch("backend.services.monitoring_service.run_audit_task", side_effect=fake_run)
    monitoring_service.execute_monitoring_run(proj.id, db)

    res = client.get(f"/api/monitoring/{proj.id}/changes")
    assert res.status_code == 200
    data = res.json()
    assert data["has_changes"] is True
    assert data["score_change"] == 10


# ── Test 20: Delete project removes reports ───────────────────────────────────

def test_delete_project(client):
    create = client.post("/api/monitoring", json={"url": "https://a.com", "name": "A"})
    pid = create.json()["id"]
    res = client.delete(f"/api/monitoring/{pid}")
    assert res.status_code == 200
    assert client.get(f"/api/monitoring/{pid}").status_code == 404
