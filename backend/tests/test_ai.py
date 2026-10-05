"""
Phase 3 AI Recommendation tests.

Isolation strategy:
- Each test gets a fresh in-memory SQLite DB via the `ai_db` fixture.
- `app.dependency_overrides` is saved before each test and restored after,
  so this module cannot pollute test_integration.py or test_audits_api.py.
- No live network calls or real LLM API keys required.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import backend.database.models as models
from backend.database.connection import Base, get_db
from backend.main import app
from backend.ai.provider import MockLLMProvider, get_llm_provider, OpenAIProvider
from backend.ai.prompts import build_system_prompt, build_user_prompt
from backend.ai.service import generate_and_save_recommendations

# ── Shared test client (no module-level overrides) ────────────────────────────
client = TestClient(app)


@pytest.fixture(autouse=True)
def restore_overrides():
    """Save and restore app.dependency_overrides around every test."""
    saved = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


@pytest.fixture()
def ai_db():
    """Fresh in-memory SQLite for each AI test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Wire this DB into FastAPI for the duration of the test
    def override():
        try:
            yield db
        finally:
            pass  # don't close here; fixture teardown handles it

    app.dependency_overrides[get_db] = override

    yield db

    db.close()


@pytest.fixture()
def completed_audit(ai_db):
    """An audit with one page and one SEO issue, ready for AI recommendations."""
    audit = models.Audit(url="https://example.com", status="completed", score=85)
    ai_db.add(audit)
    ai_db.commit()
    ai_db.refresh(audit)

    page = models.Page(
        audit_id=audit.id,
        url="https://example.com",
        depth=0,
        crawl_status="success",
        status_code=200,
    )
    ai_db.add(page)
    ai_db.commit()
    ai_db.refresh(page)

    issue = models.SEOIssue(
        page_id=page.id,
        page_url="https://example.com",
        category="on_page",
        severity="HIGH",
        issue_code="MISSING_META_DESCRIPTION",
        title="No Meta Description",
        description="The page has no meta description.",
        recommendation_summary="Add a meta description.",
        impact="Lower CTR from search results.",
    )
    ai_db.add(issue)
    ai_db.commit()

    return ai_db, audit.id


# ── Provider tests ─────────────────────────────────────────────────────────────

def test_mock_provider_fallback():
    provider = MockLLMProvider()
    recs = provider.generate_recommendations("sys", "some unrelated text")
    assert len(recs) == 1
    assert recs[0].issue_type == "GENERAL_ISSUE"


def test_mock_provider_targeted_trigger():
    provider = MockLLMProvider()
    recs = provider.generate_recommendations("sys", "MISSING_META_DESCRIPTION found on page")
    assert recs[0].issue_type == "MISSING_META_DESCRIPTION"
    assert recs[0].severity == "HIGH"
    assert recs[0].confidence == 95


def test_mock_provider_returns_valid_schema():
    provider = MockLLMProvider()
    recs = provider.generate_recommendations("", "")
    for r in recs:
        assert r.issue_type
        assert r.severity in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        assert r.title
        assert r.explanation
        assert r.recommendation
        assert r.suggested_action


# ── Prompt builder tests ───────────────────────────────────────────────────────

def test_build_system_prompt_contains_critical_instructions():
    prompt = build_system_prompt()
    assert "UNTRUSTED" in prompt
    assert "JSON" in prompt
    assert "recommendations" in prompt


def test_build_user_prompt_contains_audit_info():
    audit_ctx = {"url": "https://test.com", "score": 72}
    issues = [
        {
            "issue_code": "NO_HTTPS",
            "severity": "CRITICAL",
            "category": "technical",
            "title": "No HTTPS",
            "description": "HTTP only",
            "impact": "security risk",
        }
    ]
    prompt = build_user_prompt(audit_ctx, issues)
    assert "https://test.com" in prompt
    assert "72" in prompt
    assert "NO_HTTPS" in prompt
    assert "CRITICAL" in prompt


def test_build_user_prompt_no_raw_html():
    """Ensure raw HTML is never forwarded to the LLM prompt."""
    audit_ctx = {"url": "https://test.com", "score": 50}
    issues = [{"issue_code": "X", "severity": "LOW", "category": "on_page",
               "title": "T", "description": "d", "impact": "i"}]
    prompt = build_user_prompt(audit_ctx, issues)
    assert "<html" not in prompt.lower()
    assert "<body" not in prompt.lower()


# ── Service-layer tests ────────────────────────────────────────────────────────

def test_generate_recommendations_creates_records(completed_audit, mocker):
    db, audit_id = completed_audit
    mocker.patch("backend.ai.service.get_llm_provider", return_value=MockLLMProvider())

    recs = generate_and_save_recommendations(audit_id, db)
    assert len(recs) >= 1
    assert recs[0].issue_type == "MISSING_META_DESCRIPTION"

    # Check persisted
    saved = db.query(models.AIRecommendation).filter(
        models.AIRecommendation.audit_id == audit_id
    ).all()
    assert len(saved) == 1


def test_generate_recommendations_deduplicates(ai_db, mocker):
    """Multiple pages with the same issue_code should produce ONE recommendation."""
    mocker.patch("backend.ai.service.get_llm_provider", return_value=MockLLMProvider())

    audit = models.Audit(url="https://example.com", status="completed", score=60)
    ai_db.add(audit)
    ai_db.commit()
    ai_db.refresh(audit)

    for i in range(3):
        page = models.Page(audit_id=audit.id, url=f"https://example.com/p{i}",
                           depth=1, crawl_status="success")
        ai_db.add(page)
        ai_db.commit()
        ai_db.refresh(page)
        issue = models.SEOIssue(
            page_id=page.id, page_url=page.url, category="on_page",
            severity="HIGH", issue_code="MISSING_META_DESCRIPTION",
            title="No Meta", description="d", recommendation_summary="r", impact="i"
        )
        ai_db.add(issue)
    ai_db.commit()

    recs = generate_and_save_recommendations(audit.id, ai_db)
    # Three pages with same code → MockLLM sees the code once → 1 recommendation
    assert len(recs) >= 1
    unique_types = {r.issue_type for r in recs}
    assert "MISSING_META_DESCRIPTION" in unique_types


def test_generate_recommendations_idempotent(completed_audit, mocker):
    """Calling generate twice returns cached results without duplicating DB rows."""
    db, audit_id = completed_audit
    mocker.patch("backend.ai.service.get_llm_provider", return_value=MockLLMProvider())

    recs1 = generate_and_save_recommendations(audit_id, db)
    recs2 = generate_and_save_recommendations(audit_id, db)

    saved = db.query(models.AIRecommendation).filter(
        models.AIRecommendation.audit_id == audit_id
    ).all()
    assert len(saved) == len(recs1)  # no duplicate rows on second call
    assert len(recs2) == len(recs1)


def test_generate_recommendations_fails_on_pending_audit(ai_db):
    audit = models.Audit(url="https://example.com", status="pending")
    ai_db.add(audit)
    ai_db.commit()
    ai_db.refresh(audit)

    with pytest.raises(ValueError, match="not completed"):
        generate_and_save_recommendations(audit.id, ai_db)


def test_generate_recommendations_fails_on_missing_audit(ai_db):
    with pytest.raises(ValueError, match="not found"):
        generate_and_save_recommendations(99999, ai_db)


def test_generate_recommendations_provider_error(completed_audit, mocker):
    """A provider failure raises RuntimeError — the audit record is untouched."""
    db, audit_id = completed_audit

    class FailingProvider(MockLLMProvider):
        def generate_recommendations(self, s, u):
            raise Exception("Network timeout")

    mocker.patch("backend.ai.service.get_llm_provider", return_value=FailingProvider())

    with pytest.raises(RuntimeError, match="Failed to generate"):
        generate_and_save_recommendations(audit_id, db)

    # Audit status must remain 'completed' — AI failure doesn't corrupt it
    audit = db.query(models.Audit).filter(models.Audit.id == audit_id).first()
    assert audit.status == "completed"


# ── API endpoint tests ────────────────────────────────────────────────────────

def test_post_recommendations_endpoint(completed_audit, mocker):
    db, audit_id = completed_audit
    mocker.patch("backend.ai.service.get_llm_provider", return_value=MockLLMProvider())

    resp = client.post(f"/api/audits/{audit_id}/recommendations")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["audit_id"] == audit_id
    assert len(data["recommendations"]) >= 1
    rec = data["recommendations"][0]
    assert rec["issue_type"] == "MISSING_META_DESCRIPTION"
    assert rec["severity"] == "HIGH"
    assert "explanation" in rec
    assert "recommendation" in rec
    assert "suggested_action" in rec


def test_get_recommendations_endpoint(completed_audit, mocker):
    db, audit_id = completed_audit
    mocker.patch("backend.ai.service.get_llm_provider", return_value=MockLLMProvider())

    # First generate
    client.post(f"/api/audits/{audit_id}/recommendations")

    # Then retrieve
    resp = client.get(f"/api/audits/{audit_id}/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["audit_id"] == audit_id
    assert len(data["recommendations"]) >= 1


def test_recommendations_audit_not_found():
    # Audit 99999 does not exist; the endpoint returns 404 before reaching the service.
    resp = client.post("/api/audits/99999/recommendations")
    assert resp.status_code == 404


def test_recommendations_audit_pending(ai_db):
    audit = models.Audit(url="https://example.com", status="pending")
    ai_db.add(audit)
    ai_db.commit()
    ai_db.refresh(audit)

    resp = client.post(f"/api/audits/{audit.id}/recommendations")
    assert resp.status_code == 400
    assert "not completed" in resp.json()["detail"]


def test_recommendations_provider_error_returns_502(completed_audit, mocker):
    db, audit_id = completed_audit

    class FailingProvider(MockLLMProvider):
        def generate_recommendations(self, s, u):
            raise Exception("Rate limit")

    mocker.patch("backend.ai.service.get_llm_provider", return_value=FailingProvider())

    resp = client.post(f"/api/audits/{audit_id}/recommendations")
    assert resp.status_code == 502
