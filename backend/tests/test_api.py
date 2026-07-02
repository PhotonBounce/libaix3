"""OpsBrief — Backend tests.

Run with: pytest tests/test_api.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "opsbrief"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from opsbrief.main import app, hash_password
from opsbrief.models import Base

# Use in-memory SQLite for tests
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    # Override the dependency
    from opsbrief import main
    original_session = main.SessionLocal
    main.SessionLocal = TestingSessionLocal

    with TestClient(app) as c:
        yield c

    Base.metadata.drop_all(bind=engine)
    main.SessionLocal = original_session


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_and_login(client):
    # Register
    r = client.post("/api/auth/register", json={"email": "test@example.com", "password": "secret123", "name": "Test"})
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test"

    # Login
    r = client.post("/api/auth/token", data={"username": "test@example.com", "password": "secret123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert token

    # Me
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "test@example.com"


def test_briefing_not_ready(client):
    # Login first
    r = client.post("/api/auth/token", data={"username": "test@example.com", "password": "secret123"})
    token = r.json()["access_token"]

    r = client.get("/api/briefing/today", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_preferences(client):
    r = client.post("/api/auth/token", data={"username": "test@example.com", "password": "secret123"})
    token = r.json()["access_token"]

    # Update preferences
    r = client.put("/api/preferences", headers={"Authorization": f"Bearer {token}"}, json={
        "tech_stack": ["cisco", "aws"],
        "severity_threshold": "high",
        "sources": [],
        "notification_time": "09:00"
    })
    assert r.status_code == 200

    # Get preferences
    r = client.get("/api/preferences", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    prefs = r.json()
    assert prefs["tech_stack"] == ["cisco", "aws"]
    assert prefs["severity_threshold"] == "high"


def test_chat_rate_limit(client):
    r = client.post("/api/auth/token", data={"username": "test@example.com", "password": "secret123"})
    token = r.json()["access_token"]

    # Without OpenAI key, chat returns graceful error but still counts
    for i in range(6):
        r = client.post("/api/chat", headers={"Authorization": f"Bearer {token}"}, json={"message": f"test {i}"})

    # 6th request should be rate limited (free tier = 5)
    assert r.status_code == 429


def test_save_intel(client):
    r = client.post("/api/auth/token", data={"username": "test@example.com", "password": "secret123"})
    token = r.json()["access_token"]

    r = client.post("/api/intel/save", headers={"Authorization": f"Bearer {token}"}, json={
        "title": "Test CVE",
        "content": "Test content",
        "tags": ["test"],
        "source": "test",
    })
    assert r.status_code == 200

    r = client.get("/api/intel/saved", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["title"] == "Test CVE"


def test_admin_unauthorized(client):
    r = client.get("/api/admin/stats")
    assert r.status_code == 403

    r = client.get("/api/admin/stats", headers={"X-Admin-Key": "wrong"})
    assert r.status_code == 403


def test_admin_authorized(client):
    import os
    os.environ["ADMIN_API_KEY"] = "test-admin-key"
    from opsbrief.config import Settings
    settings = Settings()

    r = client.get("/api/admin/stats", headers={"X-Admin-Key": "test-admin-key"})
    assert r.status_code == 200
    stats = r.json()
    assert "total_users" in stats
    assert "total_intel" in stats
    assert "severity_breakdown" in stats


def test_security_headers(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-content-type-options") == "nosniff"
