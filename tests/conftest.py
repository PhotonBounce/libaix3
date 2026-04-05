"""Shared test configuration — runs before any test module imports."""
import os

import pytest

# Set admin credentials for testing before any module imports admin.py
os.environ.setdefault("ADMIN_USER", "testadmin")
os.environ.setdefault("ADMIN_PASS", "testpass123")


@pytest.fixture(autouse=True)
def _set_testing_mode():
    """Enable TESTING flag so rate-limiter is bypassed in all tests."""
    from app import app
    app.config["TESTING"] = True
    yield
    app.config["TESTING"] = False


@pytest.fixture(autouse=True)
def _mock_extra_knowledge_io(monkeypatch):
    """Prevent tests from scanning 863+ extra_knowledge JSON files.

    The cold-cache scan in admin._get_extra_domains_raw causes 30s+ timeouts
    in any test that renders the admin dashboard or imports admin at module
    level.  Stub out the three heavy helpers.
    """
    try:
        import admin
        monkeypatch.setattr(admin, "_get_extra_domains", lambda: [])
        monkeypatch.setattr(admin, "_count_extra_knowledge", lambda: 0)
        monkeypatch.setattr(admin, "_list_extra_files", lambda: [])
    except (ImportError, AttributeError):
        pass
