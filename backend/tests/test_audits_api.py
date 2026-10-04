from fastapi.testclient import TestClient
from backend.main import app
from backend.database.connection import get_db, Base, engine
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest
import backend.database.models # Import models so Base knows about them

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine_test = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

Base.metadata.create_all(bind=engine_test)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_create_audit():
    response = client.post("/api/audits", json={"url": "https://example.com", "max_pages": 5, "max_depth": 1})
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["url"] == "https://example.com"
    assert data["max_pages"] == 5
    assert data["max_depth"] == 1
    assert data["status"] == "pending"

def test_get_audit():
    # First create one
    post_response = client.post("/api/audits", json={"url": "https://test.com"})
    audit_id = post_response.json()["id"]

    # Then get it
    get_response = client.get(f"/api/audits/{audit_id}")
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["id"] == audit_id
    assert data["url"] == "https://test.com"

def test_get_nonexistent_audit():
    response = client.get("/api/audits/99999")
    assert response.status_code == 404

def test_get_audit_pages_skeleton():
    response = client.get("/api/audits/1/pages")
    assert response.status_code == 200
    assert response.json() == {"pages": []}

def test_get_audit_issues_skeleton():
    response = client.get("/api/audits/1/issues")
    assert response.status_code == 200
    assert response.json() == {"issues": []}
