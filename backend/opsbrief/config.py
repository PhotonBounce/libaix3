"""OpsBrief — Configuration management via environment variables."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All runtime configuration."""

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        "sqlite:///./opsbrief.db",  # dev default — swap for Postgres in prod
    )

    # ── Redis / Celery ────────────────────────────────────────────────
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

    # ── Environment ─────────────────────────────────────────────────────
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")

    # ── Security ────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("SECRET_KEY", secrets.token_urlsafe(32))
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour

    # ── OpenAI ──────────────────────────────────────────────────────────
    OPENAI_API_KEY: str | None = os.environ.get("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    # ── Data sources ────────────────────────────────────────────────────
    NVD_API_KEY: str | None = os.environ.get("NVD_API_KEY")
    STACKEXCHANGE_API_KEY: str | None = os.environ.get("STACKEXCHANGE_API_KEY")
    GITHUB_TOKEN: str | None = os.environ.get("GITHUB_TOKEN")

    # ── Notifications ───────────────────────────────────────────────────
    FCM_SERVER_KEY: str | None = os.environ.get("FCM_SERVER_KEY")

    # ── Admin ───────────────────────────────────────────────────────────
    ADMIN_API_KEY: str | None = os.environ.get("ADMIN_API_KEY")

    # ── App behaviour ───────────────────────────────────────────────────
    FREE_DAILY_BRIEFINGS: int = 1
    FREE_DAILY_CHATS: int = 5
    FREE_SAVED_ITEMS: int = 50
    PRO_PRICE_MONTHLY: int = 999  # cents, i.e. $9.99
    MAX_ITEMS_PER_SOURCE: int = 500

    # ── CORS ────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = os.environ.get("CORS_ORIGINS", "")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def validate_admin_key(self) -> None:
        """Validate that ADMIN_API_KEY meets minimum length requirement if set."""
        if self.ADMIN_API_KEY is not None and len(self.ADMIN_API_KEY) < 32:
            raise RuntimeError("ADMIN_API_KEY must be at least 32 characters long if set")


# singleton
settings = Settings()
settings.validate_admin_key()
