"""OpsBrief — Configuration management via environment variables."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings


def _env(key: str, default: str | None = None, allow_empty: bool = False) -> str | None:
    """Read env var. Empty string is treated as unset unless allow_empty=True."""
    val = os.environ.get(key)
    if val is None or (val == "" and not allow_empty):
        return default
    return val


class Settings(BaseSettings):
    """All runtime configuration."""

    # ── Free Mode ───────────────────────────────────────────────────────
    FREE_MODE: bool = _env("FREE_MODE", "true").lower() in ("true", "1", "yes")
    DEMO_USER_EMAIL: str = _env("DEMO_USER_EMAIL", "demo@opsbrief.local")
    DEMO_USER_NAME: str = _env("DEMO_USER_NAME", "Demo User")

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = _env(
        "DATABASE_URL",
        "sqlite:///./opsbrief.db",  # dev default — swap for Postgres in prod
    )

    # ── Redis / Celery ────────────────────────────────────────────────
    REDIS_URL: str = _env("REDIS_URL", "redis://localhost:6379/0", allow_empty=True) or ""
    CELERY_BROKER_URL: str = _env("CELERY_BROKER_URL", REDIS_URL or "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = _env("CELERY_RESULT_BACKEND", REDIS_URL or "redis://localhost:6379/0")

    # ── Environment ─────────────────────────────────────────────────────
    ENVIRONMENT: str = _env("ENVIRONMENT", "development")

    # ── Security ────────────────────────────────────────────────────────
    SECRET_KEY: str = _env("SECRET_KEY", secrets.token_urlsafe(32))
    JWT_SECRET_KEY: str = _env("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour

    # ── Anthropic Claude ────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str | None = _env("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL: str = _env("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    # ── Data sources ────────────────────────────────────────────────────
    NVD_API_KEY: str | None = _env("NVD_API_KEY")
    STACKEXCHANGE_API_KEY: str | None = _env("STACKEXCHANGE_API_KEY")
    GITHUB_TOKEN: str | None = _env("GITHUB_TOKEN")

    # ── Notifications ───────────────────────────────────────────────────
    FCM_SERVER_KEY: str | None = _env("FCM_SERVER_KEY")

    # ── Admin ───────────────────────────────────────────────────────────
    # Supports both ADMIN_API_KEY (code naming) and ADMIN_KEY (Render env naming)
    ADMIN_API_KEY: str | None = _env("ADMIN_API_KEY") or _env("ADMIN_KEY")

    # ── Payment Providers ───────────────────────────────────────────────
    # Stripe
    STRIPE_SECRET_KEY: str | None = _env("STRIPE_SECRET_KEY")
    STRIPE_PUBLISHABLE_KEY: str | None = _env("STRIPE_PUBLISHABLE_KEY")
    STRIPE_WEBHOOK_SECRET: str | None = _env("STRIPE_WEBHOOK_SECRET")
    STRIPE_PRICE_ID_YEARLY: str | None = _env("STRIPE_PRICE_ID_YEARLY")
    # PayPal
    PAYPAL_CLIENT_ID: str | None = _env("PAYPAL_CLIENT_ID")
    PAYPAL_CLIENT_SECRET: str | None = _env("PAYPAL_CLIENT_SECRET")
    PAYPAL_WEBHOOK_ID: str | None = _env("PAYPAL_WEBHOOK_ID")
    PAYPAL_API_BASE: str = _env("PAYPAL_API_BASE", "https://api-m.sandbox.paypal.com")

    # ── App behaviour ───────────────────────────────────────────────────
    FREE_DAILY_BRIEFINGS: int = 1
    FREE_DAILY_CHATS: int = 5
    FREE_SAVED_ITEMS: int = 50
    PRO_PRICE_MONTHLY: int = 999  # cents, i.e. $9.99
    VIP_PRICE_YEARLY_CENTS: int = 200  # $2.00/year
    TRIAL_DURATION_DAYS: int = 7  # 1-week free trial
    MAX_ITEMS_PER_SOURCE: int = 500

    # ── VIP Tier Limits ─────────────────────────────────────────────────
    VIP_DAILY_BRIEFINGS: int = 3
    VIP_DAILY_CHATS: int = 50
    VIP_SAVED_ITEMS: int = 500

    # ── CORS ────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = _env("CORS_ORIGINS", "")

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
