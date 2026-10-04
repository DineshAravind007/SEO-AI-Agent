import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.connection import get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import backend.database.models

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

def _create_audit(client, url: str = "https://base.com") -> dict:
    r = client.post("/api/audits", json={"url": url, "max_pages": 2, "max_depth": 0})
    assert r.status_code == 200, r.text
    return r.json()

def test_add_competitors_valid(client):
    base = _create_audit(client, "https://base.com")
    r = client.post(f"/api/audits/{base['id']}/competitors", json={"urls": ["https://comp1.com", "https://comp2.com"]})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["competitor_audit"]["url"] == "https://comp1.com"

def test_add_competitors_duplicate_url_in_request(client):
    base = _create_audit(client, "https://base.com")
    r = client.post(f"/api/audits/{base['id']}/competitors", json={"urls": ["https://comp1.com", "https://comp1.com"]})
    assert r.status_code == 422 # Validation error from Pydantic

def test_add_competitors_same_as_base(client):
    base = _create_audit(client, "https://base.com")
    r = client.post(f"/api/audits/{base['id']}/competitors", json={"urls": ["https://base.com"]})
    assert r.status_code == 400

def test_get_competitors(client):
    base = _create_audit(client, "https://base.com")
    client.post(f"/api/audits/{base['id']}/competitors", json={"urls": ["https://comp1.com"]})
    r = client.get(f"/api/audits/{base['id']}/competitors")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["competitor_audit"]["url"] == "https://comp1.com"

def test_compare_competitors_base_pending(client):
    base = _create_audit(client, "https://base.com")
    client.post(f"/api/audits/{base['id']}/competitors", json={"urls": ["https://comp1.com"]})
    r = client.get(f"/api/audits/{base['id']}/competitors/comparison")
    assert r.status_code == 400
