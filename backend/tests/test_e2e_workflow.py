"""
End-to-end verification test exercising all 11 user workflows (Phase 2):
1. Register and log in
2. Create a website audit
3. View SEO score, issues, and crawled pages
4. Generate AI recommendations
5. Download an audit report
6. Compare competitor websites
7. Run keyword analysis
8. Open Google Search Console (configured vs unconfigured states)
9. Create a monitoring project and manually trigger a monitoring run
10. Review monitoring history, detected changes, and notification settings
11. Open the performance dashboard and verify available metrics
"""

import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.database.models  # ensure models registered
from backend.main import app
from backend.database.connection import get_db, Base

# ── Isolated Test Database ───────────────────────────────────────────────────

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
    db = TestingSessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    db.close()


@pytest.fixture()
def client():
    return TestClient(app)


SAMPLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <title>Acme Widgets - Premium Online Widget Store</title>
  <meta name="description" content="Discover premium handcrafted widgets at Acme Widgets. Fast shipping, great deals, and quality guaranteed.">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="canonical" href="https://acmewidgets.com/">
</head>
<body>
  <h1>Acme Widgets - The Leading Widget Provider</h1>
  <p>Welcome to Acme Widgets. We provide the finest widgets with top-tier durability and performance.</p>
  <p>Our widgets are engineered for modern applications and maximum reliability.</p>
  <img src="https://acmewidgets.com/widget.jpg" alt="Acme Widget Model X" width="400" height="300">
  <a href="https://acmewidgets.com/about">About Us</a>
  <a href="https://acmewidgets.com/contact">Contact Us</a>
</body>
</html>"""


def _mock_network_get(url, **kwargs):
    class MockResp:
        def __init__(self, text, status_code, url, headers):
            self.text = text
            self.status_code = status_code
            self.url = url
            self.headers = headers

    if url.endswith("robots.txt"):
        return MockResp("User-agent: *\nDisallow:", 200, url, {"Content-Type": "text/plain"})
    return MockResp(
        SAMPLE_HTML,
        200,
        url,
        {"Content-Type": "text/html; charset=utf-8", "Content-Encoding": "gzip", "Cache-Control": "max-age=3600"},
    )


def test_complete_e2e_workflows(client, mocker):
    """
    Executes the full 11-step application lifecycle using real endpoints
    and authenticated user context.
    """
    mocker.patch("requests.Session.get", side_effect=_mock_network_get)
    mocker.patch("time.sleep")
    mocker.patch("backend.services.audit_service.SessionLocal", side_effect=TestingSessionLocal)

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow 1: Register and log in
    # ─────────────────────────────────────────────────────────────────────────
    reg_res = client.post(
        "/api/auth/register",
        json={"email": "e2e_tester@example.com", "password": "secure_password_123", "name": "E2E Tester"},
    )
    assert reg_res.status_code == 201, reg_res.text
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    login_res = client.post(
        "/api/auth/login",
        json={"email": "e2e_tester@example.com", "password": "secure_password_123"},
    )
    assert login_res.status_code == 200
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "e2e_tester@example.com"

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow 2: Create a website audit
    # ─────────────────────────────────────────────────────────────────────────
    create_audit_res = client.post(
        "/api/audits",
        json={"url": "https://acmewidgets.com", "max_pages": 3, "max_depth": 1},
        headers=headers,
    )
    assert create_audit_res.status_code == 200, create_audit_res.text
    audit_id = create_audit_res.json()["id"]

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow 3: View SEO score, issues, and crawled pages
    # ─────────────────────────────────────────────────────────────────────────
    audit_res = client.get(f"/api/audits/{audit_id}", headers=headers)
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["status"] == "completed"
    assert audit_data["score"] is not None

    pages_res = client.get(f"/api/audits/{audit_id}/pages", headers=headers)
    assert pages_res.status_code == 200
    pages_list = pages_res.json()["pages"]
    assert len(pages_list) >= 1

    issues_res = client.get(f"/api/audits/{audit_id}/issues", headers=headers)
    assert issues_res.status_code == 200
    assert isinstance(issues_res.json()["issues"], list)

    score_res = client.get(f"/api/audits/{audit_id}/score", headers=headers)
    assert score_res.status_code == 200
    assert "score" in score_res.json()

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow 4: Generate AI recommendations
    # ─────────────────────────────────────────────────────────────────────────
    recs_post = client.post(f"/api/audits/{audit_id}/recommendations", headers=headers)
    assert recs_post.status_code == 200, recs_post.text
    recs_data = recs_post.json()
    assert "recommendations" in recs_data
    assert isinstance(recs_data["recommendations"], list)

    recs_get = client.get(f"/api/audits/{audit_id}/recommendations", headers=headers)
    assert recs_get.status_code == 200
    assert len(recs_get.json()["recommendations"]) == len(recs_data["recommendations"])

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow 5: Download an audit report
    # ─────────────────────────────────────────────────────────────────────────
    report_res = client.get(f"/api/audits/{audit_id}/report", headers=headers)
    assert report_res.status_code == 200
    assert "text/html" in report_res.headers.get("content-type", "")
    assert "<!DOCTYPE html>" in report_res.text
    assert "Acme Widgets" in report_res.text or "https://acmewidgets.com" in report_res.text

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow 6: Compare competitor websites
    # ─────────────────────────────────────────────────────────────────────────
    comp_post = client.post(
        f"/api/audits/{audit_id}/competitors",
        json={"urls": ["https://competitorwidgets.com"]},
        headers=headers,
    )
    assert comp_post.status_code == 200, comp_post.text
    comp_list = comp_post.json()
    assert len(comp_list) == 1

    comp_get = client.get(f"/api/audits/{audit_id}/competitors", headers=headers)
    assert comp_get.status_code == 200
    assert len(comp_get.json()) >= 1

    comparison_res = client.get(f"/api/audits/{audit_id}/competitors/comparison", headers=headers)
    assert comparison_res.status_code == 200
    comp_compare = comparison_res.json()
    assert "base_audit_id" in comp_compare
    assert "competitors" in comp_compare

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow 7: Run keyword analysis
    # ─────────────────────────────────────────────────────────────────────────
    kw_analyze = client.post(
        f"/api/audits/{audit_id}/keywords/analyze",
        json={"keywords": ["widget", "handcrafted"]},
        headers=headers,
    )
    assert kw_analyze.status_code == 200, kw_analyze.text
    kw_data = kw_analyze.json()
    assert isinstance(kw_data, list)
    assert len(kw_data) == 2
    assert kw_data[0]["keyword"] in ("widget", "handcrafted")

    kw_list = client.get(f"/api/audits/{audit_id}/keywords", headers=headers)
    assert kw_list.status_code == 200
    assert len(kw_list.json()) == 2

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow 8: Google Search Console (configured vs unconfigured states)
    # ─────────────────────────────────────────────────────────────────────────
    gsc_status = client.get("/api/gsc/status", headers=headers)
    assert gsc_status.status_code == 200
    # In test/unconfigured environment without GOOGLE_CLIENT_ID, connected must be False
    assert gsc_status.json()["connected"] is False

    gsc_sites = client.get("/api/gsc/sites", headers=headers)
    # Unauthenticated / unconfigured GSC returns 401 detail or appropriate unconfigured error
    assert gsc_sites.status_code in (401, 400)

    gsc_perf = client.post(
        "/api/gsc/performance",
        json={"site_url": "https://acmewidgets.com", "start_date": "2026-01-01", "end_date": "2026-01-31"},
        headers=headers,
    )
    assert gsc_perf.status_code in (401, 400)

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow 9: Create monitoring project & trigger a monitoring run
    # ─────────────────────────────────────────────────────────────────────────
    mon_post = client.post(
        "/api/monitoring",
        json={"name": "Acme Daily Health", "url": "https://acmewidgets.com", "frequency": "daily"},
        headers=headers,
    )
    assert mon_post.status_code == 200, mon_post.text
    project_id = mon_post.json()["id"]

    mon_list = client.get("/api/monitoring", headers=headers)
    assert mon_list.status_code == 200
    projects = mon_list.json()
    assert any(p["id"] == project_id for p in projects)

    run_trigger = client.post(f"/api/monitoring/{project_id}/run", headers=headers)
    assert run_trigger.status_code == 200, run_trigger.text

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow 10: Review monitoring history, detected changes, notification settings
    # ─────────────────────────────────────────────────────────────────────────
    proj_detail = client.get(f"/api/monitoring/{project_id}", headers=headers)
    assert proj_detail.status_code == 200
    assert proj_detail.json()["id"] == project_id

    proj_hist = client.get(f"/api/monitoring/{project_id}/history", headers=headers)
    assert proj_hist.status_code == 200
    assert isinstance(proj_hist.json(), list)

    proj_changes = client.get(f"/api/monitoring/{project_id}/changes", headers=headers)
    assert proj_changes.status_code == 200
    assert isinstance(proj_changes.json(), dict)

    notif_prefs = client.get("/api/notifications/preferences", headers=headers)
    assert notif_prefs.status_code == 200
    assert "email_enabled" in notif_prefs.json()

    update_prefs = client.put(
        "/api/notifications/preferences",
        json={"email_enabled": False, "score_drop_alert": False},
        headers=headers,
    )
    assert update_prefs.status_code == 200
    assert update_prefs.json()["email_enabled"] is False
    assert update_prefs.json()["score_drop_alert"] is False

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow 11: Open the performance dashboard & verify metrics
    # ─────────────────────────────────────────────────────────────────────────
    perf_res = client.get(f"/api/audits/{audit_id}/performance", headers=headers)
    assert perf_res.status_code == 200, perf_res.text
    perf_data = perf_res.json()
    assert perf_data["audit_status"] == "completed"
    assert perf_data["lcp_status"] == "UNAVAILABLE"
    assert "browser" in perf_data["cwv_note"].lower()
    assert "score_categories" in perf_data
    assert "performance_issues" in perf_data

    pages_perf_res = client.get(f"/api/audits/{audit_id}/pages-performance", headers=headers)
    assert pages_perf_res.status_code == 200
    pages_perf = pages_perf_res.json()
    assert isinstance(pages_perf, list)
    assert len(pages_perf) >= 1
    assert pages_perf[0]["lcp_status"] == "UNAVAILABLE"
    assert pages_perf[0]["response_time_ms"] is not None
