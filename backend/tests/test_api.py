"""OpsBrief — Backend tests.

Run with: pytest tests/test_api.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set required env vars before importing app (lifespan checks these)
import os
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-must-be-at-least-32-chars")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key-thirty-two-chars-long")
os.environ.setdefault("FREE_MODE", "false")

# Mock anthropic module to avoid ImportError when llm_service.py is imported
from unittest.mock import MagicMock
mock_anthropic = MagicMock()
mock_anthropic.AsyncAnthropic = MagicMock
sys.modules["anthropic"] = mock_anthropic

from opsbrief.main import app, hash_password, get_db
from opsbrief.models import Base, User
from opsbrief import main as main_module

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Use in-memory SQLite for tests with StaticPool to share connection across sessions
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


class MockRedis:
    """Simple mock Redis for tests."""
    def ping(self):
        return True
    def get(self, key):
        return None
    def setex(self, key, ttl, value):
        pass
    def register_script(self, script):
        class MockScript:
            def __call__(self, keys=None, args=None):
                return 1
        return MockScript()


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    # Mock Redis for lifespan check
    original_redis = main_module._redis
    original_redis_available = main_module._redis_available
    main_module._redis = MockRedis()
    main_module._redis_available = True
    with TestClient(app) as c:
        yield c
    main_module._redis = original_redis
    main_module._redis_available = original_redis_available
    Base.metadata.drop_all(bind=engine)


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
    assert data["subscription_tier"] == "free"
    assert data["subscription_status"] == "none"
    assert data["is_pro"] is False

    # Login
    r = client.post("/api/auth/token", data={"username": "test@example.com", "password": "secret123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert token

    # Me
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "test@example.com"
    assert data["plan"] == "Free"
    assert data["daily_chats_limit"] == 5
    assert data["saved_intel_limit"] == 50


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
    data = r.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Test CVE"


def test_subscription_flow(client):
    # Register a new user
    r = client.post("/api/auth/register", json={"email": "sub@example.com", "password": "secret123", "name": "Sub"})
    assert r.status_code == 200
    assert r.json()["subscription_tier"] == "free"

    # Login
    r = client.post("/api/auth/token", data={"username": "sub@example.com", "password": "secret123"})
    token = r.json()["access_token"]

    # Check subscription status
    r = client.get("/api/subscription/status", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["tier"] == "free"
    assert data["is_vip_active"] is False
    assert data["price_yearly_cents"] == 200

    # Start trial
    r = client.post("/api/subscription/start-trial", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "trial_ends_at" in data

    # Check status after trial start
    r = client.get("/api/subscription/status", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["tier"] == "vip"
    assert data["is_trial_active"] is True
    assert data["is_vip_active"] is True

    # Check user profile reflects trial
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["plan"] == "Trial"
    assert data["is_vip_active"] is True
    assert data["daily_chats_limit"] == 50
    assert data["saved_intel_limit"] == 500

    # Upgrade to active VIP
    r = client.post("/api/subscription/upgrade", headers={"Authorization": f"Bearer {token}"}, json={"payment_method": "stripe"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["payment_method"] == "stripe"

    # Check status after upgrade
    r = client.get("/api/subscription/status", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["tier"] == "vip"
    assert data["is_trial_active"] is False
    assert data["is_vip_active"] is True

    # Cancel subscription
    r = client.post("/api/subscription/cancel", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "cancelled"
    assert "effective_until" in data

    # Check status after cancel
    r = client.get("/api/subscription/status", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "cancelled"
    assert data["is_vip_active"] is True  # still active until period ends


def test_subscription_upgrade_rejects_double_upgrade(client):
    r = client.post("/api/auth/register", json={"email": "dup@example.com", "password": "secret123", "name": "Dup"})
    assert r.status_code == 200

    r = client.post("/api/auth/token", data={"username": "dup@example.com", "password": "secret123"})
    token = r.json()["access_token"]

    # Start trial
    r = client.post("/api/subscription/start-trial", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200

    # Upgrade once
    r = client.post("/api/subscription/upgrade", headers={"Authorization": f"Bearer {token}"}, json={"payment_method": "paypal"})
    assert r.status_code == 200

    # Second upgrade should fail
    r = client.post("/api/subscription/upgrade", headers={"Authorization": f"Bearer {token}"}, json={"payment_method": "stripe"})
    assert r.status_code == 400


def test_admin_unauthorized(client):
    r = client.get("/api/admin/stats")
    assert r.status_code == 403

    r = client.get("/api/admin/stats", headers={"X-Admin-Key": "wrong"})
    assert r.status_code == 403


def test_admin_authorized(client):
    r = client.get("/api/admin/stats", headers={"X-Admin-Key": "test-admin-key-thirty-two-chars-long"})
    assert r.status_code == 200
    stats = r.json()
    assert "total_users" in stats
    assert "total_intel" in stats
    assert "severity_breakdown" in stats

    # Check admin users endpoint includes subscription fields
    r = client.get("/api/admin/users", headers={"X-Admin-Key": "test-admin-key-thirty-two-chars-long"})
    assert r.status_code == 200
    users = r.json()
    assert len(users) > 0
    assert "subscription_tier" in users[0]
    assert "subscription_status" in users[0]


def test_security_headers(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-content-type-options") == "nosniff"
