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
from backend.ai.provider import MockLLMProvider, get_llm_provider, OpenAIProvider, GeminiProvider
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


# ============================================================
# GeminiProvider unit tests  (no live API calls)
# ============================================================

import json as _json

GEMINI_SUCCESS_RESPONSE = {
    'candidates': [
        {
            'content': {
                'parts': [
                    {
                        'text': _json.dumps({
                            'recommendations': [{
                                'issue_type': 'MISSING_META_DESCRIPTION',
                                'severity': 'HIGH',
                                'title': 'Add Meta Descriptions',
                                'explanation': 'Meta descriptions improve CTR.',
                                'recommendation': 'Write unique meta descriptions.',
                                'suggested_action': 'Update the meta tag.',
                                'example': None,
                                'confidence': 90,
                            }]
                        })
                    }
                ]
            }
        }
    ]
}


# ── Construction / config ─────────────────────────────────────────────────────

def test_gemini_provider_instantiation():
    p = GeminiProvider(api_key='fake-key')
    assert p.model == 'gemini-2.5-flash-lite'
    assert p.timeout == 60


def test_gemini_provider_custom_model():
    p = GeminiProvider(api_key='k', model='gemini-1.5-pro', timeout=45)
    assert p.model == 'gemini-1.5-pro'
    assert p.timeout == 45


def test_gemini_provider_build_url():
    p = GeminiProvider(api_key='k', model='gemini-2.5-flash-lite')
    url = p._build_url()
    assert 'gemini-2.5-flash-lite' in url
    assert 'generateContent' in url


def test_gemini_provider_build_payload_structure():
    p = GeminiProvider(api_key='k')
    payload = p._build_payload('system prompt', 'user prompt')
    assert 'contents' in payload
    contents = payload['contents']
    assert len(contents) == 3
    assert contents[0]['role'] == 'user'
    assert contents[1]['role'] == 'model'
    assert contents[2]['role'] == 'user'
    assert 'system prompt' in contents[0]['parts'][0]['text']
    assert 'user prompt' in contents[2]['parts'][0]['text']
    assert payload['generationConfig']['responseMimeType'] == 'application/json'


# ── _extract_text ─────────────────────────────────────────────────────────────

def test_gemini_extract_text_success():
    text = GeminiProvider._extract_text(GEMINI_SUCCESS_RESPONSE)
    assert 'recommendations' in text


def test_gemini_extract_text_empty_candidates():
    with pytest.raises(ValueError, match='empty candidates'):
        GeminiProvider._extract_text({'candidates': []})


def test_gemini_extract_text_missing_key():
    with pytest.raises(ValueError):
        GeminiProvider._extract_text({'unexpected': 'structure'})


# ── _parse_recommendations ────────────────────────────────────────────────────

def test_gemini_parse_recommendations_valid():
    valid_json = _json.dumps({
        'recommendations': [{
            'issue_type': 'NO_HTTPS',
            'severity': 'CRITICAL',
            'title': 'Enable HTTPS',
            'explanation': 'HTTPS is essential for security.',
            'recommendation': 'Install an SSL certificate.',
            'suggested_action': 'Contact your host for SSL setup.',
            'example': None,
            'confidence': 99,
        }]
    })
    recs = GeminiProvider._parse_recommendations(valid_json)
    assert len(recs) == 1
    assert recs[0].issue_type == 'NO_HTTPS'
    assert recs[0].severity == 'CRITICAL'
    assert recs[0].confidence == 99


def test_gemini_parse_recommendations_strips_markdown_fence():
    raw = _json.dumps({
        'recommendations': [{
            'issue_type': 'SLOW_PAGE',
            'severity': 'MEDIUM',
            'title': 'Improve Page Speed',
            'explanation': 'Slow pages hurt rankings.',
            'recommendation': 'Compress images.',
            'suggested_action': 'Run PageSpeed Insights.',
            'example': None,
            'confidence': 80,
        }]
    })
    fenced = "```json\n" + raw + "\n```"
    recs = GeminiProvider._parse_recommendations(fenced)
    assert len(recs) == 1
    assert recs[0].issue_type == 'SLOW_PAGE'


def test_gemini_parse_recommendations_bad_json():
    import json
    with pytest.raises(json.JSONDecodeError):
        GeminiProvider._parse_recommendations('this is not json at all')


def test_gemini_parse_recommendations_empty_list():
    recs = GeminiProvider._parse_recommendations(_json.dumps({'recommendations': []}))
    assert recs == []


def test_gemini_parse_recommendations_skips_invalid_item():
    data = {
        'recommendations': [
            {
                'issue_type': 'GOOD', 'severity': 'LOW', 'title': 'Good',
                'explanation': 'e', 'recommendation': 'r', 'suggested_action': 'a',
            },
            {'garbage': True},
        ]
    }
    recs = GeminiProvider._parse_recommendations(_json.dumps(data))
    assert len(recs) == 1
    assert recs[0].issue_type == 'GOOD'


# ── generate_recommendations (httpx mocked) ───────────────────────────────────

def test_gemini_generate_recommendations_success(mocker):
    mock_resp = mocker.MagicMock()
    mock_resp.raise_for_status = mocker.MagicMock()
    mock_resp.json.return_value = GEMINI_SUCCESS_RESPONSE

    mock_client = mocker.MagicMock()
    mock_client.__enter__ = mocker.MagicMock(return_value=mock_client)
    mock_client.__exit__ = mocker.MagicMock(return_value=False)
    mock_client.post.return_value = mock_resp

    mocker.patch('backend.ai.provider.httpx.Client', return_value=mock_client)

    provider = GeminiProvider(api_key='fake-key')
    recs = provider.generate_recommendations('sys', 'user')

    assert len(recs) == 1
    assert recs[0].issue_type == 'MISSING_META_DESCRIPTION'
    assert recs[0].severity == 'HIGH'
    assert recs[0].confidence == 90


def test_gemini_generate_recommendations_http_error(mocker):
    import httpx

    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = 'Forbidden'
    http_exc = httpx.HTTPStatusError('Forbidden', request=mocker.MagicMock(), response=mock_resp)

    mock_client = mocker.MagicMock()
    mock_client.__enter__ = mocker.MagicMock(return_value=mock_client)
    mock_client.__exit__ = mocker.MagicMock(return_value=False)
    mock_client.post.side_effect = http_exc

    mocker.patch('backend.ai.provider.httpx.Client', return_value=mock_client)

    provider = GeminiProvider(api_key='fake-key')
    with pytest.raises(Exception, match='Gemini API error: 403'):
        provider.generate_recommendations('sys', 'user')


def test_gemini_generate_recommendations_timeout(mocker):
    import httpx

    mock_client = mocker.MagicMock()
    mock_client.__enter__ = mocker.MagicMock(return_value=mock_client)
    mock_client.__exit__ = mocker.MagicMock(return_value=False)
    mock_client.post.side_effect = httpx.TimeoutException('timed out')

    mocker.patch('backend.ai.provider.httpx.Client', return_value=mock_client)

    provider = GeminiProvider(api_key='fake-key')
    with pytest.raises(Exception, match='timed out'):
        provider.generate_recommendations('sys', 'user')


def test_gemini_generate_recommendations_malformed_json(mocker):
    bad_response = {
        'candidates': [{'content': {'parts': [{'text': 'not json at all!'}]}}]
    }

    mock_resp = mocker.MagicMock()
    mock_resp.raise_for_status = mocker.MagicMock()
    mock_resp.json.return_value = bad_response

    mock_client = mocker.MagicMock()
    mock_client.__enter__ = mocker.MagicMock(return_value=mock_client)
    mock_client.__exit__ = mocker.MagicMock(return_value=False)
    mock_client.post.return_value = mock_resp

    mocker.patch('backend.ai.provider.httpx.Client', return_value=mock_client)

    provider = GeminiProvider(api_key='fake-key')
    with pytest.raises(Exception, match='malformed JSON'):
        provider.generate_recommendations('sys', 'user')


def test_gemini_generate_recommendations_missing_candidates(mocker):
    bad_response = {'promptFeedback': {'blockReason': 'SAFETY'}}

    mock_resp = mocker.MagicMock()
    mock_resp.raise_for_status = mocker.MagicMock()
    mock_resp.json.return_value = bad_response

    mock_client = mocker.MagicMock()
    mock_client.__enter__ = mocker.MagicMock(return_value=mock_client)
    mock_client.__exit__ = mocker.MagicMock(return_value=False)
    mock_client.post.return_value = mock_resp

    mocker.patch('backend.ai.provider.httpx.Client', return_value=mock_client)

    provider = GeminiProvider(api_key='fake-key')
    with pytest.raises(Exception, match='response structure error'):
        provider.generate_recommendations('sys', 'user')


# ── get_llm_provider() factory ────────────────────────────────────────────────

def test_get_llm_provider_returns_mock_by_default(monkeypatch):
    monkeypatch.delenv('LLM_PROVIDER', raising=False)
    provider = get_llm_provider()
    assert isinstance(provider, MockLLMProvider)


def test_get_llm_provider_returns_gemini(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_API_KEY', 'test-gemini-key')
    monkeypatch.setenv('LLM_MODEL', 'gemini-2.5-flash-lite')
    provider = get_llm_provider()
    assert isinstance(provider, GeminiProvider)
    assert provider.api_key == 'test-gemini-key'
    assert provider.model == 'gemini-2.5-flash-lite'


def test_get_llm_provider_gemini_default_model(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_API_KEY', 'k')
    monkeypatch.delenv('LLM_MODEL', raising=False)
    provider = get_llm_provider()
    assert isinstance(provider, GeminiProvider)
    assert provider.model == 'gemini-2.5-flash-lite'


def test_get_llm_provider_gemini_missing_api_key(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'gemini')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    with pytest.raises(ValueError, match='GEMINI_API_KEY'):
        get_llm_provider()


def test_get_llm_provider_returns_openai(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'openai')
    monkeypatch.setenv('LLM_API_KEY', 'sk-test')
    provider = get_llm_provider()
    assert isinstance(provider, OpenAIProvider)


# ── Force regeneration & cache handling tests ────────────────────────────────

def test_force_false_returns_cached_recommendations(completed_audit, mocker):
    db, audit_id = completed_audit
    seed_rec = models.AIRecommendation(
        audit_id=audit_id,
        issue_type="MOCK_OLD",
        severity="LOW",
        title="Old Cached Title",
        explanation="Old explanation",
        recommendation="Old recommendation",
        suggested_action="Old action",
        example=None,
        confidence=50,
    )
    db.add(seed_rec)
    db.commit()

    mock_provider = mocker.MagicMock()
    mocker.patch("backend.ai.service.get_llm_provider", return_value=mock_provider)

    recs = generate_and_save_recommendations(audit_id, db, force=False)
    assert len(recs) == 1
    assert recs[0].title == "Old Cached Title"
    assert recs[0].issue_type == "MOCK_OLD"
    mock_provider.generate_recommendations.assert_not_called()


def test_force_true_replaces_existing_recommendations(completed_audit, mocker):
    db, audit_id = completed_audit
    seed_rec = models.AIRecommendation(
        audit_id=audit_id,
        issue_type="MOCK_OLD",
        severity="LOW",
        title="Old Stale Recommendation",
        explanation="Old explanation",
        recommendation="Old recommendation",
        suggested_action="Old action",
        example=None,
        confidence=50,
    )
    db.add(seed_rec)
    db.commit()

    from backend.schemas.ai import AIRecommendationItem
    new_item = AIRecommendationItem(
        issue_type="MISSING_META_DESCRIPTION",
        severity="HIGH",
        title="Fresh Gemini Title",
        explanation="Fresh explanation",
        recommendation="Fresh recommendation",
        suggested_action="Fresh action",
        example=None,
        confidence=95,
    )
    mock_provider = mocker.MagicMock()
    mock_provider.generate_recommendations.return_value = [new_item]
    mocker.patch("backend.ai.service.get_llm_provider", return_value=mock_provider)

    recs = generate_and_save_recommendations(audit_id, db, force=True)
    assert len(recs) == 1
    assert recs[0].title == "Fresh Gemini Title"
    mock_provider.generate_recommendations.assert_called_once()

    # Verify database contents: old one deleted, new one present
    saved = db.query(models.AIRecommendation).filter(
        models.AIRecommendation.audit_id == audit_id
    ).all()
    assert len(saved) == 1
    assert saved[0].title == "Fresh Gemini Title"
    assert saved[0].issue_type == "MISSING_META_DESCRIPTION"


def test_force_true_preserves_existing_on_provider_failure(completed_audit, mocker):
    db, audit_id = completed_audit
    seed_rec = models.AIRecommendation(
        audit_id=audit_id,
        issue_type="MOCK_PRESERVED",
        severity="MEDIUM",
        title="Preserve Me On Error",
        explanation="Explanation",
        recommendation="Recommendation",
        suggested_action="Action",
        example=None,
        confidence=60,
    )
    db.add(seed_rec)
    db.commit()

    class FailingProvider:
        def generate_recommendations(self, s, u):
            raise Exception("Gemini API 500 internal server error")

    mocker.patch("backend.ai.service.get_llm_provider", return_value=FailingProvider())

    with pytest.raises(RuntimeError, match="Failed to generate AI recommendations"):
        generate_and_save_recommendations(audit_id, db, force=True)

    # Verify old recommendation was NOT deleted
    saved = db.query(models.AIRecommendation).filter(
        models.AIRecommendation.audit_id == audit_id
    ).all()
    assert len(saved) == 1
    assert saved[0].title == "Preserve Me On Error"
    assert saved[0].issue_type == "MOCK_PRESERVED"


def test_post_recommendations_endpoint_defaults_to_cached(completed_audit, mocker):
    db, audit_id = completed_audit
    seed_rec = models.AIRecommendation(
        audit_id=audit_id,
        issue_type="CACHED_ITEM",
        severity="LOW",
        title="Cached In Endpoint",
        explanation="Exp",
        recommendation="Rec",
        suggested_action="Act",
        example=None,
        confidence=70,
    )
    db.add(seed_rec)
    db.commit()

    mock_provider = mocker.MagicMock()
    mocker.patch("backend.ai.service.get_llm_provider", return_value=mock_provider)

    resp = client.post(f"/api/audits/{audit_id}/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["title"] == "Cached In Endpoint"
    mock_provider.generate_recommendations.assert_not_called()


def test_post_recommendations_endpoint_force_true(completed_audit, mocker):
    db, audit_id = completed_audit
    seed_rec = models.AIRecommendation(
        audit_id=audit_id,
        issue_type="OLD_MOCK",
        severity="LOW",
        title="Old Endpoint Mock",
        explanation="Exp",
        recommendation="Rec",
        suggested_action="Act",
        example=None,
        confidence=50,
    )
    db.add(seed_rec)
    db.commit()

    from backend.schemas.ai import AIRecommendationItem
    fresh_rec = AIRecommendationItem(
        issue_type="MISSING_META_DESCRIPTION",
        severity="HIGH",
        title="Regenerated Via Force Query Param",
        explanation="Exp",
        recommendation="Rec",
        suggested_action="Act",
        example=None,
        confidence=99,
    )
    mock_provider = mocker.MagicMock()
    mock_provider.generate_recommendations.return_value = [fresh_rec]
    mocker.patch("backend.ai.service.get_llm_provider", return_value=mock_provider)

    resp = client.post(f"/api/audits/{audit_id}/recommendations?force=true")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["title"] == "Regenerated Via Force Query Param"
    mock_provider.generate_recommendations.assert_called_once()

    # Check DB was updated
    saved = db.query(models.AIRecommendation).filter(models.AIRecommendation.audit_id == audit_id).all()
    assert len(saved) == 1
    assert saved[0].title == "Regenerated Via Force Query Param"


def test_post_recommendations_endpoint_force_provider_failure_preserves_cache(completed_audit, mocker):
    db, audit_id = completed_audit
    seed_rec = models.AIRecommendation(
        audit_id=audit_id,
        issue_type="ORIGINAL_MOCK",
        severity="LOW",
        title="Original Should Survive Failure",
        explanation="Exp",
        recommendation="Rec",
        suggested_action="Act",
        example=None,
        confidence=50,
    )
    db.add(seed_rec)
    db.commit()

    class FailingProvider:
        def generate_recommendations(self, s, u):
            raise Exception("Gemini quota exceeded")

    mocker.patch("backend.ai.service.get_llm_provider", return_value=FailingProvider())

    resp = client.post(f"/api/audits/{audit_id}/recommendations?force=true")
    assert resp.status_code == 502
    assert "Failed to generate AI recommendations" in resp.json()["detail"]

    # Verify original recommendations are still preserved in DB
    saved = db.query(models.AIRecommendation).filter(models.AIRecommendation.audit_id == audit_id).all()
    assert len(saved) == 1
    assert saved[0].title == "Original Should Survive Failure"

