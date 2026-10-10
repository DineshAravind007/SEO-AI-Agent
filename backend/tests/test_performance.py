"""
Tests for the Performance Analysis feature.

Uses the same in-memory SQLite test fixtures as other test modules.
The global conftest.py auto-overrides get_current_user for all tests
in this file (since 'test_performance' is not in the excluded list).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.database.connection import get_db, Base
from backend.database.models import (
    User, Audit, Page, SEOIssue, AuditPerformance, PagePerformance
)
from backend.services.performance_analyzer import analyze_performance, PERF_RULES
from backend.security.auth import get_current_user, hash_password
from backend.tests.conftest import _DEFAULT_TEST_USER

# ── Test DB ─────────────────────────────────────────────────────────────────

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base.metadata.create_all(bind=_engine)


def _get_test_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _setup_db():
    """Fresh DB for every test, override get_db."""
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)
    db = _Session()
    for tbl in reversed(Base.metadata.sorted_tables):
        db.execute(tbl.delete())
    db.commit()
    db.close()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def db():
    session = _Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_user(db):
    user = User(
        id=1,
        email="test@example.com",
        name="Test User",
        is_active=True,
        password_hash=hash_password("password123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def completed_audit(db, test_user):
    """An audit in 'completed' status with one page and performance data."""
    audit = Audit(
        user_id=test_user.id,
        url="https://example.com",
        max_pages=5,
        max_depth=2,
        status="completed",
        score=75,
    )
    db.add(audit)
    db.flush()

    page = Page(
        audit_id=audit.id,
        url="https://example.com/",
        depth=0,
        status_code=200,
        content_type="text/html",
        crawl_status="success",
    )
    db.add(page)
    db.flush()

    page_perf = PagePerformance(
        page_id=page.id,
        response_time_ms=350,
        html_size_bytes=52000,
        is_compressed=True,
        has_cache_control=True,
        image_count=5,
        missing_dimensions_count=2,
        lcp_status="UNAVAILABLE",
        inp_status="UNAVAILABLE",
        cls_status="UNAVAILABLE",
        ttfb_ms=350,
        performance_score=76,
    )
    db.add(page_perf)

    audit_perf = AuditPerformance(
        audit_id=audit.id,
        avg_response_time_ms=350,
        total_page_size_bytes=52000,
        performance_score=76,
    )
    db.add(audit_perf)

    # A performance issue
    issue = SEOIssue(
        page_id=page.id,
        page_url="https://example.com/",
        category="Performance",
        severity="MEDIUM",
        issue_code="MISSING_IMAGE_DIMENSIONS",
        title="Images Missing Dimensions",
        description="2 images lack explicit dimensions.",
        recommendation_summary="Add width/height attributes.",
        impact="Score reduced by 4 points.",
    )
    db.add(issue)
    db.commit()
    db.refresh(audit)
    return audit, page, page_perf


@pytest.fixture()
def other_user(db):
    other = User(
        id=200,
        email="other@test.com",
        name="Other User",
        is_active=True,
        password_hash=hash_password("password456"),
    )
    db.add(other)
    db.commit()
    db.refresh(other)
    return other


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS — performance_analyzer.py
# ═══════════════════════════════════════════════════════════════════════════════

class TestPerformanceAnalyzer:
    """Unit tests for the pure analysis function."""

    def _make_page_data(
        self, duration=0.1, html="<html><head></head><body>Hello</body></html>",
        headers=None, status_code=200, url="https://example.com/"
    ):
        return {
            "url": url,
            "final_url": url,
            "duration": duration,
            "html": html,
            "headers": headers or {"content-encoding": "gzip", "cache-control": "max-age=3600"},
            "status_code": status_code,
        }

    def test_good_page_scores_100(self):
        data = self._make_page_data(
            duration=0.1,
            html='<html><head><meta name="viewport" content="width=device-width"><img src="x.jpg" width="100" height="100"></head></html>',
            headers={"content-encoding": "gzip", "cache-control": "max-age=3600"},
        )
        result = analyze_performance(data)
        assert result["metrics"]["performance_score"] == 100
        assert result["issues"] == []

    def test_slow_response_generates_issue(self):
        data = self._make_page_data(duration=1.5)
        result = analyze_performance(data)
        codes = [i["issue_code"] for i in result["issues"]]
        assert "SLOW_SERVER_RESPONSE" in codes
        assert result["metrics"]["performance_score"] < 100

    def test_missing_compression_generates_issue(self):
        html = '<html><head><meta name="viewport" content="width=device-width"></head><body>' + ('Hello world! ' * 100) + '</body></html>'
        data = self._make_page_data(
            html=html,
            headers={"cache-control": "max-age=3600"},
        )
        result = analyze_performance(data)
        codes = [i["issue_code"] for i in result["issues"]]
        assert "MISSING_COMPRESSION" in codes
        penalty = PERF_RULES["compression_penalty"]
        assert result["metrics"]["performance_score"] <= 100 - penalty

    def test_missing_cache_control_generates_issue(self):
        data = self._make_page_data(headers={"content-encoding": "gzip"})
        result = analyze_performance(data)
        codes = [i["issue_code"] for i in result["issues"]]
        assert "MISSING_CACHE_CONTROL" in codes
        penalty = PERF_RULES["cache_penalty"]
        assert result["metrics"]["performance_score"] <= 100 - penalty

    def test_http_url_generates_https_issue(self):
        data = self._make_page_data(
            url="http://example.com/",
            headers={"content-encoding": "gzip", "cache-control": "max-age=3600"},
        )
        # final_url is http
        data["final_url"] = "http://example.com/"
        result = analyze_performance(data)
        codes = [i["issue_code"] for i in result["issues"]]
        assert "NOT_HTTPS" in codes

    def test_missing_image_dimensions_generates_issue(self):
        html = '<html><head></head><body><img src="a.jpg"><img src="b.jpg"></body></html>'
        data = self._make_page_data(
            html=html,
            headers={"content-encoding": "gzip", "cache-control": "max-age=3600"},
        )
        result = analyze_performance(data)
        codes = [i["issue_code"] for i in result["issues"]]
        assert "MISSING_IMAGE_DIMENSIONS" in codes
        assert result["metrics"]["missing_dimensions_count"] == 2

    def test_missing_viewport_generates_issue(self):
        html = "<html><head><title>Test</title></head><body>Text</body></html>"
        data = self._make_page_data(
            html=html,
            headers={"content-encoding": "gzip", "cache-control": "max-age=3600"},
        )
        result = analyze_performance(data)
        codes = [i["issue_code"] for i in result["issues"]]
        assert "MISSING_VIEWPORT_META" in codes

    def test_cwv_always_unavailable(self):
        data = self._make_page_data()
        result = analyze_performance(data)
        m = result["metrics"]
        assert m["lcp_status"] == "UNAVAILABLE"
        assert m["inp_status"] == "UNAVAILABLE"
        assert m["cls_status"] == "UNAVAILABLE"
        assert m["fcp_ms"] is None

    def test_cwv_note_present(self):
        data = self._make_page_data()
        result = analyze_performance(data)
        assert "cwv_note" in result
        assert "browser" in result["cwv_note"].lower()

    def test_score_never_below_zero(self):
        """Even with all issues, score should be >= 0."""
        data = self._make_page_data(
            duration=5.0,
            html="<html>" + "x" * 600000 + "</html>",
            headers={},
            url="http://example.com/",
        )
        data["final_url"] = "http://example.com/"
        result = analyze_performance(data)
        assert result["metrics"]["performance_score"] >= 0

    def test_empty_html_safe(self):
        """Empty HTML should not crash."""
        data = self._make_page_data(html="")
        result = analyze_performance(data)
        assert "metrics" in result
        assert result["metrics"]["html_size_bytes"] == 0

    def test_large_html_generates_issue(self):
        large_html = "x" * (350 * 1024)
        data = self._make_page_data(
            html=large_html,
            headers={"content-encoding": "gzip", "cache-control": "max-age=3600"},
        )
        result = analyze_performance(data)
        codes = [i["issue_code"] for i in result["issues"]]
        assert "LARGE_HTML_DOCUMENT" in codes

    def test_response_time_rating_good(self):
        data = self._make_page_data(duration=0.1)
        result = analyze_performance(data)
        assert result["metrics"]["response_time_rating"] == "GOOD"

    def test_response_time_rating_poor(self):
        data = self._make_page_data(duration=2.0)
        result = analyze_performance(data)
        assert result["metrics"]["response_time_rating"] == "POOR"

    def test_ttfb_is_approximation(self):
        data = self._make_page_data(duration=0.3)
        result = analyze_performance(data)
        # ttfb_approx should equal response_time_ms (both are 300)
        assert result["metrics"]["ttfb_ms_approx"] == 300
        assert result["metrics"]["response_time_ms"] == 300


# ═══════════════════════════════════════════════════════════════════════════════
# API TESTS — /api/audits/{id}/performance
# ═══════════════════════════════════════════════════════════════════════════════

class TestPerformanceAPI:
    """Integration tests for performance endpoints."""

    def test_get_performance_completed_audit(self, client, completed_audit):
        audit, _, _ = completed_audit
        res = client.get(f"/api/audits/{audit.id}/performance")
        assert res.status_code == 200
        data = res.json()
        assert data["audit_status"] == "completed"
        assert data["performance_score"] is not None
        assert data["performance_score"] >= 0
        assert data["lcp_status"] == "UNAVAILABLE"
        assert data["cwv_note"] != ""
        assert isinstance(data["performance_issues"], list)
        assert data["opportunities_count"] >= 0

    def test_performance_issues_in_response(self, client, completed_audit):
        audit, _, _ = completed_audit
        res = client.get(f"/api/audits/{audit.id}/performance")
        assert res.status_code == 200
        data = res.json()
        assert len(data["performance_issues"]) >= 1
        issue = data["performance_issues"][0]
        assert "issue_code" in issue
        assert "severity" in issue
        assert "title" in issue
        assert "recommendation_summary" in issue

    def test_score_categories_in_response(self, client, completed_audit):
        audit, _, _ = completed_audit
        res = client.get(f"/api/audits/{audit.id}/performance")
        assert res.status_code == 200
        data = res.json()
        assert "score_categories" in data
        cats = data["score_categories"]
        assert "server_response" in cats
        assert "compression" in cats
        assert "caching" in cats

    def test_get_performance_incomplete_audit(self, client, db, test_user):
        audit = Audit(
            user_id=test_user.id,
            url="https://example.com",
            max_pages=5,
            max_depth=2,
            status="crawling",
        )
        db.add(audit)
        db.commit()
        res = client.get(f"/api/audits/{audit.id}/performance")
        assert res.status_code == 200
        data = res.json()
        assert data["audit_status"] == "crawling"
        assert data["performance_score"] is None

    def test_get_performance_nonexistent_audit(self, client):
        res = client.get("/api/audits/99999/performance")
        assert res.status_code == 404

    def test_get_pages_performance(self, client, completed_audit):
        audit, _, _ = completed_audit
        res = client.get(f"/api/audits/{audit.id}/pages-performance")
        assert res.status_code == 200
        pages = res.json()
        assert isinstance(pages, list)
        assert len(pages) >= 1
        page = pages[0]
        assert "url" in page
        assert "performance_score" in page
        assert "response_time_ms" in page
        assert "lcp_status" in page
        assert page["lcp_status"] == "UNAVAILABLE"

    def test_cross_user_access_blocked(self, client, completed_audit, other_user):
        """User A should not be able to access User B's audit."""
        audit, _, _ = completed_audit
        # Override auth to return other_user
        app.dependency_overrides[get_current_user] = lambda: other_user
        try:
            res = client.get(f"/api/audits/{audit.id}/performance")
            assert res.status_code == 403
        finally:
            # Restore original override (conftest sets test user)
            app.dependency_overrides[get_current_user] = lambda: _DEFAULT_TEST_USER

    def test_unauthenticated_access_blocked(self, client, completed_audit):
        """Remove auth override to test real JWT enforcement."""
        audit, _, _ = completed_audit
        saved = app.dependency_overrides.pop(get_current_user, None)
        try:
            res = client.get(f"/api/audits/{audit.id}/performance")
            assert res.status_code == 401
        finally:
            if saved:
                app.dependency_overrides[get_current_user] = saved
            else:
                app.dependency_overrides[get_current_user] = lambda: _DEFAULT_TEST_USER
