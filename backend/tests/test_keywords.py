import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.connection import get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import backend.database.models
from backend.database.models import Audit, Page

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
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)

@pytest.fixture()
def client():
    return TestClient(app)

def _create_completed_audit_with_page(client) -> dict:
    db = TestingSessionLocal()
    audit = Audit(url="https://test.com", status="completed")
    db.add(audit)
    db.commit()
    db.refresh(audit)
    
    page = Page(
        audit_id=audit.id,
        url="https://test.com",
        title="Test SEO Keyword",
        meta_description="A meta about SEO keyword",
        h1_list='["Main SEO keyword heading"]',
        h2_list='[]',
        crawl_status="success"
    )
    db.add(page)
    db.commit()
    audit_id = audit.id
    db.close()
    
    return {"id": audit_id}

def test_analyze_keywords_valid(client):
    audit = _create_completed_audit_with_page(client)
    r = client.post(f"/api/audits/{audit['id']}/keywords/analyze", json={"keywords": ["seo keyword", "missing"]})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    
    kw1 = next(d for d in data if d["keyword"] == "seo keyword")
    assert kw1["usage"]["title_matches"] == 1
    assert kw1["usage"]["meta_matches"] == 1
    assert kw1["usage"]["h1_matches"] == 1
    assert kw1["opportunity_score"] > 50
    assert len(kw1["gaps"]) == 0
    
    kw2 = next(d for d in data if d["keyword"] == "missing")
    assert kw2["usage"]["title_matches"] == 0
    assert kw2["usage"]["pages_containing"] == 0
    assert len(kw2["gaps"]) > 0

def test_analyze_keywords_incomplete_audit(client):
    db = TestingSessionLocal()
    audit = Audit(url="https://test.com", status="pending")
    db.add(audit)
    db.commit()
    audit_id = audit.id
    db.close()
    
    r = client.post(f"/api/audits/{audit_id}/keywords/analyze", json={"keywords": ["seo keyword"]})
    assert r.status_code == 400

def test_analyze_keywords_duplicate_request(client):
    audit = _create_completed_audit_with_page(client)
    r = client.post(f"/api/audits/{audit['id']}/keywords/analyze", json={"keywords": ["seo", "seo", " SEO "]})
    assert r.status_code == 200
    # Should deduplicate to 1
    data = r.json()
    assert len(data) == 1

def test_get_keywords(client):
    audit = _create_completed_audit_with_page(client)
    client.post(f"/api/audits/{audit['id']}/keywords/analyze", json={"keywords": ["test"]})
    r = client.get(f"/api/audits/{audit['id']}/keywords")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["keyword"] == "test"
