import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.connection import get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import json

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

@pytest.fixture()
def client():
    return TestClient(app)

def test_status_unconfigured(client, mocker):
    mocker.patch("backend.api.gsc.is_gsc_configured", return_value=False)
    response = client.get("/api/gsc/status")
    assert response.status_code == 200
    assert response.json() == {"configured": False, "connected": False}

def test_status_configured_not_connected(client, mocker):
    mocker.patch("backend.api.gsc.is_gsc_configured", return_value=True)
    mocker.patch("backend.api.gsc.is_user_connected", return_value=False)
    response = client.get("/api/gsc/status")
    assert response.status_code == 200
    assert response.json() == {"configured": True, "connected": False}

def test_login_unconfigured(client, mocker):
    mocker.patch("backend.api.gsc.is_gsc_configured", return_value=False)
    response = client.get("/api/gsc/auth/login")
    assert response.status_code == 400

def test_login_configured(client, mocker):
    mocker.patch("backend.api.gsc.is_gsc_configured", return_value=True)
    mocker.patch("backend.api.gsc.get_auth_url", return_value=("http://google.com/auth", "test_state"))
    # Disable redirect following to inspect headers
    response = client.get("/api/gsc/auth/login", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "http://google.com/auth"
    # Session cookie is set
    assert "session" in response.cookies

def test_callback_invalid_state(client):
    response = client.get("/api/gsc/auth/callback?state=invalid&code=123")
    assert response.status_code == 400
    assert "Invalid OAuth state" in response.json()["detail"]

def test_sites_unauthenticated(client, mocker):
    mocker.patch("backend.api.gsc.is_user_connected", return_value=False)
    response = client.get("/api/gsc/sites")
    assert response.status_code == 401

def test_sites_authenticated(client, mocker):
    mocker.patch("backend.api.gsc.is_user_connected", return_value=True)
    mocker.patch("backend.api.gsc.get_sites", return_value=[{"siteUrl": "https://test.com", "permissionLevel": "siteOwner"}])
    response = client.get("/api/gsc/sites")
    assert response.status_code == 200
    assert response.json()[0]["siteUrl"] == "https://test.com"

def test_performance_unauthenticated(client, mocker):
    mocker.patch("backend.api.gsc.is_user_connected", return_value=False)
    response = client.post("/api/gsc/performance", json={
        "site_url": "https://test.com",
        "start_date": "2023-01-01",
        "end_date": "2023-01-31"
    })
    assert response.status_code == 401

def test_performance_authenticated(client, mocker):
    mocker.patch("backend.api.gsc.is_user_connected", return_value=True)
    mocker.patch("backend.api.gsc.get_performance", return_value={
        "summary": {"clicks": 100, "impressions": 1000, "ctr": 0.1, "position": 5.0},
        "queries": [],
        "pages": []
    })
    response = client.post("/api/gsc/performance", json={
        "site_url": "https://test.com",
        "start_date": "2023-01-01",
        "end_date": "2023-01-31"
    })
    assert response.status_code == 200
    assert response.json()["summary"]["clicks"] == 100
