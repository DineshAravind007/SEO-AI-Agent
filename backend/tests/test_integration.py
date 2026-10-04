"""
Integration test: full audit flow using mocked HTTP responses.

Key technique: we patch `backend.services.audit_service.SessionLocal` so the
background task writes into the *same* in-memory SQLite that the API uses.
We also patch `requests.Session.get` so no live HTTP calls are made.
"""
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import backend.database.models  # ensure models are registered on Base
from backend.database.connection import get_db, Base
from backend.main import app

# ── Shared in-memory DB for both the API layer and the background task ────────

SQLITE_URL = "sqlite:///:memory:"
engine_test = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)
Base.metadata.create_all(bind=engine_test)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# ── HTML fixture ──────────────────────────────────────────────────────────────

FIXTURE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <title>Example Domain</title>
  <meta name="description" content="Example domain for illustrative examples.">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="canonical" href="https://example.com/">
</head>
<body>
  <h1>Example Domain</h1>
  <p>This domain is for use in illustrative examples in documents.</p>
  <p>You may use this domain in literature without prior coordination or asking for permission.</p>
  <a href="https://www.iana.org/domains/reserved">More information...</a>
</body>
</html>"""


def _mock_get(url, **kwargs):
    """Return canned responses — no live network calls."""
    class Resp:
        def __init__(self, text, status_code, url, headers):
            self.text = text
            self.status_code = status_code
            self.url = url
            self.headers = headers

    if url.endswith("robots.txt"):
        return Resp("User-agent: *\nDisallow:", 200, url, {"Content-Type": "text/plain; charset=utf-8"})
    if "example.com" in url:
        return Resp(FIXTURE_HTML, 200, url, {"Content-Type": "text/html; charset=UTF-8"})
    return Resp("", 404, url, {"Content-Type": "text/html"})


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_full_audit_flow(mocker):
    """
    1. POST /api/audits → returns audit with status 'pending'
    2. Background task runs synchronously (TestClient) with mocked HTTP
    3. GET /api/audits/{id} → status 'completed'
    4. GET /api/audits/{id}/pages → at least one page stored
    5. GET /api/audits/{id}/issues → expected SEO issues stored
    """
    # Patch the HTTP session so no real requests are made
    mocker.patch("requests.Session.get", side_effect=_mock_get)
    mocker.patch("time.sleep")  # skip politeness delay

    # Redirect the background task's own SessionLocal to the test DB
    mocker.patch(
        "backend.services.audit_service.SessionLocal",
        side_effect=TestingSessionLocal,
    )

    # 1. Create audit
    create_resp = client.post(
        "/api/audits",
        json={"url": "https://example.com", "max_pages": 3, "max_depth": 1},
    )
    assert create_resp.status_code == 200, create_resp.text
    audit = create_resp.json()
    audit_id = audit["id"]
    assert audit["status"] == "pending"

    # 2. Poll status (TestClient runs background tasks before returning, so it
    #    should already be terminal by now)
    status_resp = client.get(f"/api/audits/{audit_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == "completed", (
        f"Expected 'completed', got '{status_data['status']}'. "
        f"error_message={status_data.get('error_message')}"
    )

    # 3. Pages must be non-empty
    pages_resp = client.get(f"/api/audits/{audit_id}/pages")
    assert pages_resp.status_code == 200
    pages = pages_resp.json()["pages"]
    assert len(pages) >= 1, f"Expected at least 1 page, got {pages}"

    # The crawled page should carry title extracted from fixture HTML
    first_page = pages[0]
    assert first_page["title"] == "Example Domain", f"Got title: {first_page.get('title')}"

    # 4. Issues must be non-empty (fixture HTML is missing H2 and external links
    #    are only to iana.org — no internal links → NO_INTERNAL_LINKS expected)
    issues_resp = client.get(f"/api/audits/{audit_id}/issues")
    assert issues_resp.status_code == 200
    issues = issues_resp.json()["issues"]
    assert len(issues) >= 1, f"Expected at least 1 SEO issue, got {issues}"

    issue_codes = [i["issue_code"] for i in issues]
    # The fixture HTML has one external link and no internal links
    assert "NO_INTERNAL_LINKS" in issue_codes, f"Issue codes found: {issue_codes}"
    # Technical issues should be present
    assert "MISSING_SITEMAP" in issue_codes, f"Issue codes found: {issue_codes}"
    assert "MISSING_CANONICAL" not in issue_codes # The fixture has a canonical URL
    
    # 5. Check Score
    score_resp = client.get(f"/api/audits/{audit_id}/score")
    assert score_resp.status_code == 200
    score_data = score_resp.json()
    assert "score" in score_data
    assert "grade" in score_data
    assert "severity_counts" in score_data
    assert "category_counts" in score_data
    assert "explanation" in score_data
    assert isinstance(score_data["score"], int)


def test_audit_failed_when_nothing_crawled(mocker):
    """If the base URL is blocked by robots.txt, status must be 'failed'."""
    mocker.patch("time.sleep")
    mocker.patch(
        "backend.services.audit_service.SessionLocal",
        side_effect=TestingSessionLocal,
    )

    def block_all(url, **kwargs):
        class Resp:
            text = "User-agent: *\nDisallow: /"
            status_code = 200
            url = url
            headers = {"Content-Type": "text/plain; charset=utf-8"}
        return Resp()

    mocker.patch("requests.Session.get", side_effect=block_all)

    create_resp = client.post(
        "/api/audits",
        json={"url": "https://example.com", "max_pages": 3, "max_depth": 1},
    )
    assert create_resp.status_code == 200
    audit_id = create_resp.json()["id"]

    status_resp = client.get(f"/api/audits/{audit_id}")
    data = status_resp.json()
    assert data["status"] == "failed", f"Expected 'failed', got '{data['status']}'"
    assert data["error_message"], "error_message should be set when audit fails"


def test_pages_endpoint_returns_page_fields(mocker):
    """Verify /pages returns expected SEO field data from the fixture."""
    mocker.patch("requests.Session.get", side_effect=_mock_get)
    mocker.patch("time.sleep")
    mocker.patch(
        "backend.services.audit_service.SessionLocal",
        side_effect=TestingSessionLocal,
    )

    create_resp = client.post(
        "/api/audits",
        json={"url": "https://example.com", "max_pages": 1, "max_depth": 0},
    )
    audit_id = create_resp.json()["id"]

    pages_resp = client.get(f"/api/audits/{audit_id}/pages")
    pages = pages_resp.json()["pages"]
    assert len(pages) >= 1

    p = pages[0]
    assert p["status_code"] == 200
    assert p["crawl_status"] == "success"
    assert p["title"] == "Example Domain"
    assert p["h1_count"] == 1
    assert p["h1_list"] == ["Example Domain"]
