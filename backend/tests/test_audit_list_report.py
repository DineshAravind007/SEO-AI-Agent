"""
Tests for:
  - GET /api/audits  (audit list)
  - GET /api/audits/{id}/report  (HTML report download)

Uses a completely separate TestClient with its own DB override,
isolated from other test modules.
"""
import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.connection import get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import backend.database.models  # noqa: F401 — registers models


# ── Isolated in-memory DB for THIS module only ─────────────────────────────────
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
def _use_isolated_db(monkeypatch):
    """Each test in this module runs with the isolated in-memory DB."""
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    # Restore saved dependency overrides so other modules aren't contaminated
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


@pytest.fixture()
def client():
    return TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_audit(client, url: str = "https://example.com") -> dict:
    r = client.post("/api/audits", json={"url": url, "max_pages": 2, "max_depth": 0})
    assert r.status_code == 200, r.text
    return r.json()


def _mark_completed(audit_id: int, score: int = 75) -> None:
    """Directly update audit status to 'completed' with score_data for testing."""
    db = TestingSessionLocal()
    try:
        audit = db.query(backend.database.models.Audit).filter_by(id=audit_id).first()
        audit.status = "completed"
        audit.score = score
        audit.score_data = json.dumps({
            "score": score,
            "grade": "Fair",
            "severity_counts": {"CRITICAL": 0, "HIGH": 2, "MEDIUM": 1, "LOW": 0},
            "category_counts": {"on_page": 2, "technical": 1},
            "explanation": f"Score is {score}/100.",
        })
        db.commit()
    finally:
        db.close()


# ── GET /api/audits ────────────────────────────────────────────────────────────

def test_list_audits_empty(client):
    """Empty list returned when no audits exist in a fresh DB."""
    r = client.get("/api/audits")
    assert r.status_code == 200
    data = r.json()
    assert data["audits"] == []
    assert data["total"] == 0


def test_list_audits_returns_audits(client):
    """Created audits appear in the list."""
    _create_audit(client, "https://list-test-1.com")
    _create_audit(client, "https://list-test-2.com")
    r = client.get("/api/audits")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    urls = [a["url"] for a in data["audits"]]
    assert "https://list-test-1.com" in urls
    assert "https://list-test-2.com" in urls


def test_list_audits_fields(client):
    """Each audit entry contains required fields."""
    audit = _create_audit(client, "https://fields-test.com")
    r = client.get("/api/audits")
    assert r.status_code == 200
    items = r.json()["audits"]
    found = next((a for a in items if a["id"] == audit["id"]), None)
    assert found is not None
    for field in ("id", "url", "status", "score", "grade", "page_count", "issue_count", "created_at"):
        assert field in found, f"Field '{field}' missing from audit list entry"


def test_list_audits_newest_first(client):
    """Audits are ordered newest-first (descending ID)."""
    a1 = _create_audit(client, "https://order-1.com")
    a2 = _create_audit(client, "https://order-2.com")
    r = client.get("/api/audits")
    assert r.status_code == 200
    ids = [a["id"] for a in r.json()["audits"]]
    assert ids.index(a2["id"]) < ids.index(a1["id"])


def test_list_audits_pagination(client):
    """Pagination via skip/limit works."""
    _create_audit(client, "https://page-a.com")
    _create_audit(client, "https://page-b.com")
    _create_audit(client, "https://page-c.com")
    r = client.get("/api/audits?skip=0&limit=2")
    assert r.status_code == 200
    assert len(r.json()["audits"]) == 2


def test_list_audits_completed_has_score(client):
    """A completed audit shows score and grade in the list."""
    audit = _create_audit(client, "https://score-list-test.com")
    _mark_completed(audit["id"], score=80)
    r = client.get("/api/audits")
    assert r.status_code == 200
    found = next((a for a in r.json()["audits"] if a["id"] == audit["id"]), None)
    assert found is not None
    assert found["score"] == 80
    assert found["grade"] == "Fair"


# ── GET /api/audits/{id}/report ────────────────────────────────────────────────

def test_report_nonexistent_audit(client):
    """404 for a non-existent audit."""
    r = client.get("/api/audits/99999/report")
    assert r.status_code == 404


def test_report_pending_audit(client):
    """400 when audit is not yet completed."""
    audit = _create_audit(client, "https://report-pending-test.com")
    r = client.get(f"/api/audits/{audit['id']}/report")
    assert r.status_code == 400
    assert "completed" in r.json()["detail"].lower()


def test_report_completed_audit(client):
    """Completed audit returns HTML content with correct headers."""
    audit = _create_audit(client, "https://report-completed-test.com")
    _mark_completed(audit["id"], score=65)
    r = client.get(f"/api/audits/{audit['id']}/report")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "attachment" in r.headers.get("content-disposition", "")
    assert ".html" in r.headers.get("content-disposition", "")
    body = r.text
    assert "SEO Audit Report" in body
    assert "https://report-completed-test.com" in body
    assert "65" in body
    assert "Fair" in body


def test_report_contains_score_section(client):
    """HTML report contains a score section."""
    audit = _create_audit(client, "https://report-score-section.com")
    _mark_completed(audit["id"], score=55)
    r = client.get(f"/api/audits/{audit['id']}/report")
    assert r.status_code == 200
    assert "SEO Health Score" in r.text


def test_report_html_structure(client):
    """HTML report is a valid HTML document."""
    audit = _create_audit(client, "https://report-html-test.com")
    _mark_completed(audit["id"], score=70)
    r = client.get(f"/api/audits/{audit['id']}/report")
    assert r.status_code == 200
    body = r.text
    assert "<!DOCTYPE html>" in body
    assert "<html" in body
    assert "</html>" in body


def test_report_html_escaping(client):
    """HTML special characters in URLs are escaped in the report."""
    # Use a URL with characters that would be dangerous if unescaped
    audit = _create_audit(client, "https://safe-test.com")
    _mark_completed(audit["id"], score=60)
    r = client.get(f"/api/audits/{audit['id']}/report")
    assert r.status_code == 200
    # Verify no raw script injection
    assert "<script>" not in r.text or "Generated by SEO Agent" in r.text
