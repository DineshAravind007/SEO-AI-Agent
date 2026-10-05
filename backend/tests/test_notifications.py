import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.database.connection import get_db, Base
from backend.database.models import User, MonitoringProject
from backend.services.notification_service import notification_service

# In-memory SQLite DB for testing
engine_test = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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

@pytest.fixture()
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture()
def user_token(client, db):
    # Register and login a user
    client.post("/api/auth/register", json={"email": "test@example.com", "password": "password123", "name": "Test User"})
    res = client.post("/api/auth/login", json={"email": "test@example.com", "password": "password123"})
    return res.json()["access_token"]

def test_get_preferences_default(client, user_token):
    res = client.get("/api/notifications/preferences", headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["email_enabled"] is True
    assert data["score_drop_alert"] is True
    assert data["critical_issue_alert"] is True
    assert data["high_issue_alert"] is True
    assert data["weekly_summary"] is False

def test_update_preferences(client, user_token):
    res = client.put("/api/notifications/preferences", json={
        "email_enabled": False,
        "score_drop_alert": False,
        "critical_issue_alert": True,
        "high_issue_alert": False,
        "weekly_summary": True
    }, headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["email_enabled"] is False
    assert data["weekly_summary"] is True

def test_unauthenticated_access(client):
    res = client.get("/api/notifications/preferences")
    assert res.status_code == 401
    
    res = client.get("/api/notifications/history")
    assert res.status_code == 401

def test_send_alert_records_history(db, client, user_token):
    user = db.query(User).filter(User.email == "test@example.com").first()
    
    # Mock email provider to just return True
    notification_service.email_provider.is_configured = lambda: True
    notification_service.email_provider.send = lambda to, sub, body: True
    
    notification_service.send_alert(db, user, 1, "score_drop", "CRITICAL", "Test Alert", "<html></html>")
    
    res = client.get("/api/notifications/history", headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200
    history = res.json()
    assert len(history) == 1
    assert history[0]["notification_type"] == "score_drop"
    assert history[0]["severity"] == "CRITICAL"
    assert history[0]["status"] == "sent"

def test_send_alert_skipped_if_disabled(db, client, user_token):
    user = db.query(User).filter(User.email == "test@example.com").first()
    client.put("/api/notifications/preferences", json={
        "email_enabled": False,
        "score_drop_alert": True,
        "critical_issue_alert": True,
        "high_issue_alert": True,
        "weekly_summary": False
    }, headers={"Authorization": f"Bearer {user_token}"})
    
    notification_service.send_alert(db, user, 1, "score_drop", "CRITICAL", "Test Alert", "<html></html>")
    
    res = client.get("/api/notifications/history", headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200
    history = res.json()
    assert len(history) == 1
    assert history[0]["status"] == "skipped"
    assert "Email disabled" in history[0]["error_message"]
