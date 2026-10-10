"""
Comprehensive tests for authentication and user security (Phase 1).
Covers:
  - Registration (success, duplicate email, validation)
  - Login (success, invalid password, nonexistent user, inactive user)
  - Logout
  - Session restoration (/api/auth/me)
  - Token expiration and tampering
  - Protected routes enforcement
  - Cross-user data isolation (audits & performance)
"""

import datetime
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import jwt

from backend.main import app
from backend.database.connection import get_db, Base
from backend.database.models import User, Audit
from backend.security.auth import (
    hash_password,
    create_access_token,
    JWT_SECRET,
    JWT_ALGORITHM,
)

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


# ── Registration Tests ────────────────────────────────────────────────────────

def test_register_success(client):
    res = client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "securepassword123", "name": "Alice Smith"},
    )
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["name"] == "Alice Smith"
    assert data["user"]["is_active"] is True
    assert "password_hash" not in data["user"]


def test_register_duplicate_email(client):
    client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "password": "password123", "name": "Bob"},
    )
    res = client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "password": "anotherpassword", "name": "Bob Clone"},
    )
    assert res.status_code == 400
    assert "Email already registered" in res.json()["detail"]


def test_register_invalid_data(client):
    # Missing required password
    res = client.post("/api/auth/register", json={"email": "incomplete@example.com"})
    assert res.status_code == 422

    # Short password
    res = client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "123"},
    )
    assert res.status_code == 422


# ── Login Tests ───────────────────────────────────────────────────────────────

def test_login_success(client):
    client.post(
        "/api/auth/register",
        json={"email": "carol@example.com", "password": "mysecretpass123", "name": "Carol"},
    )
    res = client.post(
        "/api/auth/login",
        json={"email": "carol@example.com", "password": "mysecretpass123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "carol@example.com"


def test_login_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={"email": "dave@example.com", "password": "correctpassword", "name": "Dave"},
    )
    res = client.post(
        "/api/auth/login",
        json={"email": "dave@example.com", "password": "wrongpassword"},
    )
    assert res.status_code == 401
    assert "Incorrect email or password" in res.json()["detail"]


def test_login_nonexistent_user(client):
    res = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "somepassword"},
    )
    assert res.status_code == 401
    assert "Incorrect email or password" in res.json()["detail"]


def test_login_inactive_user(client):
    # Create user directly in DB with is_active=False
    db = TestingSessionLocal()
    user = User(
        email="inactive@example.com",
        password_hash=hash_password("pass12345"),
        name="Inactive User",
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.close()

    res = client.post(
        "/api/auth/login",
        json={"email": "inactive@example.com", "password": "pass12345"},
    )
    assert res.status_code == 401
    assert "Inactive user account" in res.json()["detail"] or "inactive" in res.json()["detail"].lower()


# ── Logout Tests ──────────────────────────────────────────────────────────────

def test_logout(client):
    res = client.post("/api/auth/logout")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


# ── Session Restoration & Token Verification (/api/auth/me) ───────────────────

def test_get_me_authenticated(client):
    reg = client.post(
        "/api/auth/register",
        json={"email": "eva@example.com", "password": "password123", "name": "Eva"},
    )
    token = reg.json()["access_token"]

    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "eva@example.com"
    assert data["name"] == "Eva"


def test_get_me_unauthenticated(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert "Not authenticated" in res.json()["detail"]


def test_get_me_invalid_token(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.fake.token"})
    assert res.status_code == 401
    assert "Invalid or expired token" in res.json()["detail"]


def test_get_me_expired_token(client):
    reg = client.post(
        "/api/auth/register",
        json={"email": "frank@example.com", "password": "password123", "name": "Frank"},
    )
    user_id = reg.json()["user"]["id"]

    # Generate an expired token
    expired_payload = {
        "sub": str(user_id),
        "email": "frank@example.com",
        "exp": datetime.datetime.now(datetime.timezone.utc) - timedelta(minutes=10),
    }
    expired_token = jwt.encode(expired_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


# ── Protected Routes & Cross-User Data Isolation ─────────────────────────────

def test_protected_audits_endpoint_without_token(client):
    res = client.get("/api/audits")
    assert res.status_code == 401


def test_cross_user_audit_isolation(client):
    # Register User 1
    r1 = client.post(
        "/api/auth/register",
        json={"email": "user1@example.com", "password": "password123", "name": "User One"},
    )
    token1 = r1.json()["access_token"]

    # Register User 2
    r2 = client.post(
        "/api/auth/register",
        json={"email": "user2@example.com", "password": "password123", "name": "User Two"},
    )
    token2 = r2.json()["access_token"]

    # User 1 creates an audit
    create_res = client.post(
        "/api/audits",
        json={"url": "https://user1site.com", "max_pages": 2, "max_depth": 0},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert create_res.status_code == 200
    audit_id = create_res.json()["id"]

    # User 1 can fetch their audit
    res_owner = client.get(f"/api/audits/{audit_id}", headers={"Authorization": f"Bearer {token1}"})
    assert res_owner.status_code == 200
    assert res_owner.json()["url"] == "https://user1site.com"

    # User 2 CANNOT fetch User 1's audit -> 403 Forbidden
    res_other = client.get(f"/api/audits/{audit_id}", headers={"Authorization": f"Bearer {token2}"})
    assert res_other.status_code == 403

    # User 2 CANNOT see User 1's audit in audit list
    list_user2 = client.get("/api/audits", headers={"Authorization": f"Bearer {token2}"})
    assert list_user2.status_code == 200
    audits_user2 = list_user2.json()["audits"]
    assert all(a["id"] != audit_id for a in audits_user2)

    # User 2 CANNOT access User 1's performance endpoint -> 403 Forbidden
    perf_other = client.get(f"/api/audits/{audit_id}/performance", headers={"Authorization": f"Bearer {token2}"})
    assert perf_other.status_code == 403
