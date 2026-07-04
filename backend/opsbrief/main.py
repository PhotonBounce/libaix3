"""OpsBrief — FastAPI entry point, auth, and core API routes."""

from __future__ import annotations

import bcrypt
import hashlib
import html
import json
import logging
import redis
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Generator
from uuid import uuid4

from fastapi import FastAPI, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from jwt.exceptions import PyJWTError as JWTError
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, case, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .models import (
    Base,
    Briefing,
    Conversation,
    RawIntel,
    SavedItem,
    SessionLocal,
    User,
    engine,
)
from .services.cache import cache

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")

# ── Redis (security-critical state) ───────────────────────────────────
_redis = None
_redis_available = False

try:
    _redis = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
    _redis.ping()
    _redis_available = True
    logger.info("Redis connected for security state")
except Exception as exc:
    logger.critical(f"Redis unavailable for security state — falling back to in-memory: {exc}")
    # In-memory fallback for rate limiting (per-process, NOT suitable for multi-worker production)
    _rate_limit_store: dict[str, list[float]] = {}
    _admin_rate_limit_store: dict[str, list[float]] = {}
    _token_blacklist: set[str] = set()

# Session security limits
SESSION_MAX_LIFETIME_SECONDS = 30 * 24 * 3600  # 30 days
MAX_REFRESH_COUNT = 100

# Dummy hash to prevent timing-based user enumeration on login
_DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt())

# ── Free-mode demo user helpers ───────────────────────────────────────

DEMO_USER_ID = "00000000-0000-0000-0000-000000000000"


def get_or_create_demo_user(db: Session) -> User:
    """Return the synthetic demo user, creating it if necessary."""
    user = db.query(User).filter(User.id == DEMO_USER_ID).first()
    if not user:
        user = User(
            id=DEMO_USER_ID,
            email=settings.DEMO_USER_EMAIL,
            password_hash="",  # no password for demo user
            name=settings.DEMO_USER_NAME,
            is_pro=1,
            subscription_tier="vip",
            subscription_status="active",
            preferences_json=json.dumps({
                "tech_stack": ["cisco", "aws", "linux"],
                "severity_threshold": "medium",
                "sources": ["nvd", "github", "cisco"],
                "notification_time": "08:00",
            }),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# ── Security ──────────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_client_ip(request: Request) -> str:
    """Extract real client IP from request, respecting reverse proxy headers."""
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def _log_security_event(event_type: str, ip_address: str, user_id: str | None = None, outcome: str = "success"):
    ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()[:16] if ip_address else "unknown"
    user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16] if user_id else "anonymous"
    security_logger.info(
        json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "ip_address": ip_hash,
            "user_id": user_hash,
            "outcome": outcome,
        })
    )


RATE_LIMIT_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local window_seconds = tonumber(ARGV[4])
local member = ARGV[5]

redis.call('zremrangebyscore', key, 0, window_start)
local count = redis.call('zcard', key)
if count >= max_requests then
    return 0
end
redis.call('zadd', key, now, member)
redis.call('expire', key, window_seconds)
return 1
"""

_rate_limit_script = None


def _check_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    now = datetime.now(timezone.utc).timestamp()
    window_start = now - window_seconds

    if _redis_available and _redis:
        global _rate_limit_script
        if _rate_limit_script is None:
            _rate_limit_script = _redis.register_script(RATE_LIMIT_LUA)
        redis_key = f"ratelimit:{key}"
        member = f"{now}:{uuid4()}"
        result = _rate_limit_script(
            keys=[redis_key],
            args=[now, window_start, max_requests, window_seconds, member]
        )
        if result == 0:
            endpoint = key.split(":")[0] if ":" in key else key
            ip_address = key.split(":", 1)[1] if ":" in key else "unknown"
            _log_security_event("rate_limit_triggered", ip_address=ip_address, outcome=f"endpoint={endpoint}")
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
    else:
        store = _admin_rate_limit_store if key.startswith("admin:") else _rate_limit_store
        timestamps = store.get(key, [])
        timestamps = [t for t in timestamps if t > window_start]
        if len(timestamps) >= max_requests:
            endpoint = key.split(":")[0] if ":" in key else key
            ip_address = key.split(":", 1)[1] if ":" in key else "unknown"
            _log_security_event("rate_limit_triggered", ip_address=ip_address, outcome=f"endpoint={endpoint}")
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
        timestamps.append(now)
        store[key] = timestamps


def _check_admin_rate_limit(ip: str) -> None:
    _check_rate_limit(f"admin:{ip}", 30, 60)


def rate_limit_register(request: Request):
    client_ip = _get_client_ip(request)
    _check_rate_limit(f"register:{client_ip}", 10, 3600)


def rate_limit_login(request: Request):
    client_ip = _get_client_ip(request)
    _check_rate_limit(f"token:{client_ip}", 10, 300)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_access_token(data: dict, expires: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "jti": str(uuid4())})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# Patch get_current_user to support free mode
_original_get_current_user = None


def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    if settings.FREE_MODE:
        return get_or_create_demo_user(db)

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        jti: str = payload.get("jti")
        if user_id is None or jti is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    if _redis_available and _redis:
        if _redis.get(f"blacklist:{jti}"):
            raise credentials_exception
    else:
        if jti in globals().get('_token_blacklist', set()):
            raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


def _reset_counters_if_needed(user_id: str, db: Session) -> User:
    """Reset daily counters if a new day has passed. Returns the refreshed user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    now = datetime.now(timezone.utc)
    reset_at = user.counters_reset_at
    if reset_at is None:
        needs_reset = True
    else:
        # Handle both offset-aware and offset-naive datetimes
        if reset_at.tzinfo is None:
            reset_at = reset_at.replace(tzinfo=timezone.utc)
        needs_reset = (now - reset_at).days >= 1
    if needs_reset:
        user.daily_briefings_used = 0
        user.daily_chats_used = 0
        user.counters_reset_at = now
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_user_limits(user: User) -> dict[str, int]:
    """Return usage limits based on user's subscription tier."""
    if user.is_vip:
        return {
            "daily_briefings": settings.VIP_DAILY_BRIEFINGS,
            "daily_chats": settings.VIP_DAILY_CHATS,
            "saved_items": settings.VIP_SAVED_ITEMS,
        }
    return {
        "daily_briefings": settings.FREE_DAILY_BRIEFINGS,
        "daily_chats": settings.FREE_DAILY_CHATS,
        "saved_items": settings.FREE_SAVED_ITEMS,
    }


def _make_aware(dt: datetime | None) -> datetime | None:
    """Ensure a datetime is timezone-aware (UTC) for safe comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ── Pydantic Schemas ─────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    name: str | None = Field(default=None, max_length=100)

    @field_validator("password")
    @classmethod
    def _password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

    @field_validator("name")
    @classmethod
    def _name_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 100:
            raise ValueError("Name must be at most 100 characters")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None
    is_pro: bool
    is_team: bool = False
    plan: str | None = None
    daily_briefings_used: int
    daily_chats_used: int
    daily_briefings_limit: int | None = None
    daily_chats_limit: int | None = None
    saved_intel_limit: int | None = None
    # Subscription fields
    subscription_tier: str | None = None
    subscription_status: str | None = None
    trial_started_at: str | None = None
    trial_ends_at: str | None = None
    subscription_started_at: str | None = None
    subscription_ends_at: str | None = None
    subscription_renews_at: str | None = None
    cancelled_at: str | None = None
    is_trial_active: bool = False
    is_vip_active: bool = False

    class Config:
        from_attributes = True


class BriefingOut(BaseModel):
    id: str
    briefing_date: str
    items: list[dict]
    is_read: bool
    is_ready: bool
    sent_at: datetime | None

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str = Field(max_length=2000)
    context_intel_id: str | None = None


class ChatResponse(BaseModel):
    answer: str


class SavedItemCreate(BaseModel):
    title: str = Field(max_length=255)
    content: str = Field(max_length=10000)
    tags: list[str] = Field(default=[], max_length=20)
    source: str = "briefing"
    intel_id: str | None = None

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, v: list[str]) -> list[str]:
        if len(v) > 20:
            raise ValueError("At most 20 tags allowed")
        for tag in v:
            if len(tag) > 50:
                raise ValueError("Each tag must be at most 50 characters")
        return v


class PreferencesUpdate(BaseModel):
    tech_stack: list[str] = []
    severity_threshold: str = "medium"
    sources: list[str] = []
    notification_time: str = "08:00"


class BriefingHistoryItem(BaseModel):
    id: str
    date: str
    is_read: bool
    item_count: int


class SavedIntelItem(BaseModel):
    id: str
    title: str
    content: str
    tags: list[str]
    source: str
    created_at: str | None


class SavedIntelOut(BaseModel):
    total: int
    items: list[SavedIntelItem]


class StatusOut(BaseModel):
    status: str


class SavedItemIdOut(BaseModel):
    id: str


class SeverityBreakdown(BaseModel):
    critical: int
    high: int
    medium: int
    low: int
    info: int


class SourceBreakdown(BaseModel):
    nvd: int
    github: int
    cisco: int


class AdminStatsOut(BaseModel):
    total_users: int
    total_intel: int
    briefings_today: int
    critical_items: int
    severity_breakdown: SeverityBreakdown
    source_breakdown: SourceBreakdown


class AdminIntelItem(BaseModel):
    id: str
    source: str
    source_id: str
    title: str
    severity: str
    cvss_score: float | None
    published_at: str | None
    fetched_at: str | None


class AdminUserItem(BaseModel):
    id: str
    email: str
    name: str | None
    is_pro: bool
    subscription_tier: str | None = None
    subscription_status: str | None = None
    trial_ends_at: str | None = None
    subscription_ends_at: str | None = None
    stripe_customer_id: str | None = None
    paypal_subscription_id: str | None = None
    created_at: str | None
    daily_chats_used: int


class HealthOut(BaseModel):
    status: str
    database: str


class PreferencesOut(BaseModel):
    tech_stack: list[str] = []
    severity_threshold: str = "medium"
    sources: list[str] = []
    notification_time: str = "08:00"

    class Config:
        extra = "allow"


# ── Lifespan / Startup ───────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if not settings.JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY environment variable must be set")
    if len(settings.JWT_SECRET_KEY) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be at least 32 characters long")
    # Redis is required for security-critical state, but in FREE_MODE we gracefully degrade
    if not settings.FREE_MODE:
        try:
            _redis.ping()
        except Exception as exc:
            raise RuntimeError(f"Redis is required for security state but is unavailable: {exc}")
    yield


app = FastAPI(title="OpsBrief", version="1.0.0", lifespan=lifespan, debug=False, docs_url=None, redoc_url=None, openapi_url=None)


# Global exception handler to prevent stack trace leakage in production
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return Response(
        content=json.dumps({"detail": "Internal server error"}),
        status_code=500,
        media_type="application/json",
    )

# Security headers middleware
class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def wrapped_send(message):
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                # Prevent clickjacking
                headers.append([b"x-frame-options", b"DENY"])
                # Prevent MIME sniffing
                headers.append([b"x-content-type-options", b"nosniff"])
                # Referrer policy
                headers.append([b"referrer-policy", b"strict-origin-when-cross-origin"])
                # CSP for API (restrictive for frontend iframe protection)
                headers.append([b"content-security-policy", b"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"])
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, wrapped_send)

app.add_middleware(SecurityHeadersMiddleware)

# Cache-Control middleware for authenticated API responses
@app.middleware("http")
async def cache_control_middleware(request: Request, call_next):
    response = await call_next(request)
    auth_header = request.headers.get("Authorization")
    path = request.url.path
    if auth_header or path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response.headers["Vary"] = "Authorization"
    return response

# CORS — tighten in production via env var
_cors_origins = settings.CORS_ORIGINS.split(",") if hasattr(settings, "CORS_ORIGINS") and settings.CORS_ORIGINS else ["http://localhost:3000", "http://localhost:8000"]
if getattr(settings, "ENVIRONMENT", "development") == "production" and not (hasattr(settings, "CORS_ORIGINS") and settings.CORS_ORIGINS):
    raise RuntimeError("CORS_ORIGINS must be set in production. Set the CORS_ORIGINS environment variable to a comma-separated list of allowed origins.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Auth Routes ──────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=UserOut, tags=["auth"])
def register(req: RegisterRequest, db: Session = Depends(get_db), _rate_limit: None = Depends(rate_limit_register)):
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        name=req.name,
        subscription_tier="free",
        subscription_status="none",
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Registration failed.")
    return user


@app.post("/api/auth/token", response_model=TokenResponse, tags=["auth"])
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db), _rate_limit: None = Depends(rate_limit_login)):
    user = db.query(User).filter(User.email == form_data.username).first()
    client_ip = _get_client_ip(request)
    if not user:
        # Consume same time as a real bcrypt check to prevent timing-based user enumeration
        bcrypt.checkpw(b"dummy", _DUMMY_HASH)
        _log_security_event("failed_login", ip_address=client_ip, user_id=form_data.username, outcome="failure")
        raise HTTPException(status_code=401, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    if not verify_password(form_data.password, user.password_hash):
        _log_security_event("failed_login", ip_address=client_ip, user_id=form_data.username, outcome="failure")
        raise HTTPException(status_code=401, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    now = datetime.now(timezone.utc)
    token = create_access_token({"sub": str(user.id), "auth_time": now.timestamp(), "refresh_count": 0})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/auth/me", response_model=UserOut, tags=["auth"])
def me(current_user: User = Depends(get_current_user)):
    if settings.FREE_MODE:
        return {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "is_pro": True,
            "is_team": True,
            "plan": "VIP (Guest Demo)",
            "daily_briefings_used": 0,
            "daily_chats_used": 0,
            "daily_briefings_limit": 9999,
            "daily_chats_limit": 9999,
            "saved_intel_limit": 9999,
            "subscription_tier": "vip",
            "subscription_status": "active",
            "trial_started_at": None,
            "trial_ends_at": None,
            "subscription_started_at": None,
            "subscription_ends_at": None,
            "subscription_renews_at": None,
            "cancelled_at": None,
            "is_trial_active": False,
            "is_vip_active": True,
        }
    # Build subscription booleans
    now = datetime.now(timezone.utc)
    trial_ends = _make_aware(current_user.trial_ends_at)
    is_trial_active = bool(
        current_user.subscription_status == "trialing"
        and trial_ends
        and trial_ends > now
    )
    is_vip_active = current_user.is_vip or bool(current_user.is_pro)
    limits = get_user_limits(current_user)
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.name,
        "is_pro": is_vip_active,
        "is_team": is_vip_active,
        "plan": "Trial" if is_trial_active else ("VIP" if is_vip_active else "Free"),
        "daily_briefings_used": current_user.daily_briefings_used,
        "daily_chats_used": current_user.daily_chats_used,
        "daily_briefings_limit": limits["daily_briefings"],
        "daily_chats_limit": limits["daily_chats"],
        "saved_intel_limit": limits["saved_items"],
        "subscription_tier": current_user.subscription_tier or "free",
        "subscription_status": current_user.subscription_status or "none",
        "trial_started_at": current_user.trial_started_at.isoformat() if current_user.trial_started_at else None,
        "trial_ends_at": current_user.trial_ends_at.isoformat() if current_user.trial_ends_at else None,
        "subscription_started_at": current_user.subscription_started_at.isoformat() if current_user.subscription_started_at else None,
        "subscription_ends_at": current_user.subscription_ends_at.isoformat() if current_user.subscription_ends_at else None,
        "subscription_renews_at": current_user.subscription_renews_at.isoformat() if current_user.subscription_renews_at else None,
        "cancelled_at": current_user.cancelled_at.isoformat() if current_user.cancelled_at else None,
        "is_trial_active": is_trial_active,
        "is_vip_active": is_vip_active,
    }


@app.post("/api/auth/refresh", response_model=TokenResponse, tags=["auth"])
def refresh_token(request: Request, current_user: User = Depends(get_current_user)):
    client_ip = _get_client_ip(request)
    # Rate limit: 10 per hour per IP and per user
    _check_rate_limit(f"refresh:{client_ip}", 10, 3600)
    _check_rate_limit(f"refresh:user:{current_user.id}", 10, 3600)

    # Extract old token from Authorization header and blacklist it
    auth_header = request.headers.get("Authorization")
    auth_time = None
    refresh_count = 0
    if auth_header and auth_header.startswith("Bearer "):
        old_token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(old_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            jti = payload.get("jti")
            exp = payload.get("exp")
            auth_time = payload.get("auth_time")
            refresh_count = payload.get("refresh_count", 0)
            if jti:
                ttl = max(0, int(exp - datetime.now(timezone.utc).timestamp())) if exp else settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
                if _redis_available and _redis:
                    _redis.setex(f"blacklist:{jti}", ttl, "1")
                else:
                    _token_blacklist.add(jti)
        except JWTError:
            pass

    now = datetime.now(timezone.utc)
    if auth_time is not None:
        if now.timestamp() - auth_time > SESSION_MAX_LIFETIME_SECONDS:
            _log_security_event("session_expired", ip_address=client_ip, user_id=str(current_user.id), outcome="failure")
            raise HTTPException(status_code=401, detail="Session expired. Please log in again.")

    new_refresh_count = refresh_count + 1
    if new_refresh_count > MAX_REFRESH_COUNT:
        _log_security_event("refresh_limit_exceeded", ip_address=client_ip, user_id=str(current_user.id), outcome="failure")
        raise HTTPException(status_code=401, detail="Maximum refresh limit reached. Please log in again.")

    token = create_access_token({"sub": str(current_user.id), "auth_time": auth_time or now.timestamp(), "refresh_count": new_refresh_count})
    return {"access_token": token, "token_type": "bearer"}


@app.post("/api/auth/logout", response_model=StatusOut, tags=["auth"])
def logout(request: Request, token: str = Depends(oauth2_scheme)):
    client_ip = _get_client_ip(request)
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")
        user_id = payload.get("sub")
        if jti:
            ttl = max(0, int(exp - datetime.now(timezone.utc).timestamp())) if exp else settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            if _redis_available and _redis:
                _redis.setex(f"blacklist:{jti}", ttl, "1")
            else:
                _token_blacklist.add(jti)
        _log_security_event("logout", ip_address=client_ip, user_id=user_id, outcome="success")
    except JWTError:
        pass
    return {"status": "ok"}


@app.delete("/api/auth/me", response_model=StatusOut, tags=["auth"])
def delete_account(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    client_ip = _get_client_ip(request)
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.query(SavedItem).filter(SavedItem.user_id == user.id).delete()
    db.query(Conversation).filter(Conversation.user_id == user.id).delete()
    db.query(Briefing).filter(Briefing.user_id == user.id).delete()
    db.delete(user)
    db.commit()
    cache.delete_pattern(f"briefing:{user.id}:")
    _log_security_event("account_deletion", ip_address=client_ip, user_id=str(user.id), outcome="success")
    return {"status": "deleted"}


@app.get("/api/auth/export", tags=["auth"])
def export_user_data(response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Export all user data as JSON for GDPR Article 15 (right of access)."""
    user_data = {
        "id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.name,
        "is_pro": bool(current_user.is_pro),
        "subscription_tier": current_user.subscription_tier,
        "subscription_status": current_user.subscription_status,
        "trial_ends_at": current_user.trial_ends_at.isoformat() if current_user.trial_ends_at else None,
        "subscription_ends_at": current_user.subscription_ends_at.isoformat() if current_user.subscription_ends_at else None,
        "subscription_renews_at": current_user.subscription_renews_at.isoformat() if current_user.subscription_renews_at else None,
        "cancelled_at": current_user.cancelled_at.isoformat() if current_user.cancelled_at else None,
        "stripe_customer_id": current_user.stripe_customer_id,
        "stripe_subscription_id": current_user.stripe_subscription_id,
        "paypal_subscription_id": current_user.paypal_subscription_id,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "pro_expires_at": current_user.pro_expires_at.isoformat() if current_user.pro_expires_at else None,
    }

    try:
        preferences = json.loads(current_user.preferences_json or "{}")
    except json.JSONDecodeError:
        preferences = {}

    saved_items = db.query(SavedItem).filter(SavedItem.user_id == current_user.id).all()
    saved_items_data = [
        {
            "id": str(i.id),
            "title": i.title,
            "content": i.content,
            "tags": json.loads(i.tags),
            "source": i.source,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in saved_items
    ]

    conversations = db.query(Conversation).filter(Conversation.user_id == current_user.id).all()
    conversations_data = [
        {
            "id": str(c.id),
            "title": c.title,
            "messages": json.loads(c.messages),
            "context_intel_id": str(c.context_intel_id) if c.context_intel_id else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in conversations
    ]

    briefings = db.query(Briefing).filter(Briefing.user_id == current_user.id).all()
    briefings_data = [
        {
            "id": str(b.id),
            "briefing_date": b.briefing_date,
            "items": json.loads(b.items),
            "is_read": bool(b.is_read),
            "is_ready": bool(b.is_ready),
            "sent_at": b.sent_at.isoformat() if b.sent_at else None,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in briefings
    ]

    response.headers["Content-Disposition"] = 'attachment; filename="opsbrief-export.json"'
    return {
        "user_profile": user_data,
        "preferences": preferences,
        "saved_intel": saved_items_data,
        "conversation_history": conversations_data,
        "briefings": briefings_data,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Mock data for free mode ───────────────────────────────────────────

_FREE_BRIEFING_ITEMS = [
    {
        "intel_id": "mock-cve-001",
        "source": "nvd",
        "source_id": "CVE-2024-1087",
        "headline": "Linux kernel privilege escalation via use-after-free",
        "summary": "A use-after-free vulnerability in the Linux kernel's netfilter subsystem could allow a local attacker to escalate privileges. Patch available in versions 6.7.2 and later.",
        "severity": "critical",
        "cvss_score": 8.4,
        "url": "https://nvd.nist.gov/vuln/detail/CVE-2024-1087",
        "relevance_score": 95.0,
        "published_at": "2024-06-14T10:00:00Z",
    },
    {
        "intel_id": "mock-cve-002",
        "source": "github",
        "source_id": "GHSA-4x8x-2p5m-m4c7",
        "headline": "OpenSSL denial of service in TLS handshake",
        "summary": "An attacker can send a malicious ClientHello message to trigger an infinite loop during TLS handshake processing, causing a denial of service.",
        "severity": "high",
        "cvss_score": 7.5,
        "url": "https://github.com/advisories/GHSA-4x8x-2p5m-m4c7",
        "relevance_score": 88.0,
        "published_at": "2024-06-14T08:30:00Z",
    },
    {
        "intel_id": "mock-cve-003",
        "source": "cisco",
        "source_id": "CSCwf12345",
        "headline": "Cisco IOS XE Web UI command injection vulnerability",
        "summary": "A vulnerability in the web-based management interface of Cisco IOS XE Software could allow an authenticated remote attacker to inject commands and execute arbitrary code.",
        "severity": "high",
        "cvss_score": 7.2,
        "url": "https://sec.cloudapps.cisco.com/security/center/content/CiscoSecurityAdvisory/cisco-sa-iosxe-webui-cmdinject",
        "relevance_score": 82.0,
        "published_at": "2024-06-13T14:20:00Z",
    },
    {
        "intel_id": "mock-cve-004",
        "source": "nvd",
        "source_id": "CVE-2024-2567",
        "headline": "AWS CLI credential leak in verbose logging mode",
        "summary": "When AWS CLI is run with --debug, temporary credentials may be logged to stderr. If logs are collected by a central system, this could expose sensitive credentials.",
        "severity": "medium",
        "cvss_score": 5.3,
        "url": "https://nvd.nist.gov/vuln/detail/CVE-2024-2567",
        "relevance_score": 76.0,
        "published_at": "2024-06-12T16:00:00Z",
    },
    {
        "intel_id": "mock-cve-005",
        "source": "github",
        "source_id": "GHSA-9v8x-3p5m-m2c1",
        "headline": "Kubernetes container escape via cgroups v1",
        "summary": "A flaw in the handling of cgroups v1 allows a container with CAP_SYS_ADMIN to escape to the host. Affected clusters running cgroups v1 should upgrade to cgroups v2.",
        "severity": "high",
        "cvss_score": 7.8,
        "url": "https://github.com/advisories/GHSA-9v8x-3p5m-m2c1",
        "relevance_score": 90.0,
        "published_at": "2024-06-12T09:00:00Z",
    },
]


# ── Briefing Routes ──────────────────────────────────────────────────

@app.get("/api/briefing/today", response_model=BriefingOut, tags=["briefings"])
def get_today_briefing(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _reset_counters_if_needed(current_user.id, db)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cache_key = f"briefing:{current_user.id}:{today}"
    cached = cache.get(cache_key)
    if cached:
        return BriefingOut(**cached)
    briefing = (
        db.query(Briefing)
        .filter(Briefing.user_id == current_user.id, Briefing.briefing_date == today)
        .first()
    )
    if not briefing:
        if settings.FREE_MODE:
            # Return mock briefing in free mode so the app is usable immediately
            return BriefingOut(
                id="mock-briefing-001",
                briefing_date=today,
                items=_FREE_BRIEFING_ITEMS,
                is_read=True,
                is_ready=True,
                sent_at=None,
            )
        raise HTTPException(status_code=404, detail="Briefing not ready yet. Check back later.")
    # Check daily briefing limit and increment counter
    if not settings.FREE_MODE:
        limits = get_user_limits(current_user)
        fresh_user = db.query(User).filter(User.id == current_user.id).first()
        if not fresh_user.is_vip and fresh_user.daily_briefings_used >= limits["daily_briefings"]:
            raise HTTPException(status_code=429, detail=f"Daily briefing limit reached. Upgrade to VIP for {settings.VIP_DAILY_BRIEFINGS} briefings/day.")
        fresh_user.daily_briefings_used += 1
    # Mark as read
    briefing.is_read = 1
    db.commit()
    result = BriefingOut(
        id=str(briefing.id),
        briefing_date=briefing.briefing_date,
        items=json.loads(briefing.items),
        is_read=bool(briefing.is_read),
        is_ready=bool(briefing.is_ready),
        sent_at=briefing.sent_at,
    )
    cache.set(cache_key, result.model_dump(mode="json"), ttl=300)
    return result


@app.get("/api/briefing/history", response_model=list[BriefingHistoryItem], tags=["briefings"])
def get_briefing_history(current_user: User = Depends(get_current_user), db: Session = Depends(get_db), limit: int = Query(30, ge=0, le=100)):
    rows = (
        db.query(Briefing)
        .filter(Briefing.user_id == current_user.id)
        .order_by(Briefing.briefing_date.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(b.id),
            "date": b.briefing_date,
            "is_read": bool(b.is_read),
            "item_count": len(json.loads(b.items)),
        }
        for b in rows
    ]


# ── Chat Routes ──────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
async def chat(req: ChatRequest, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _reset_counters_if_needed(current_user.id, db)

    if not settings.FREE_MODE:
        # Per-minute rate limit: 10 per minute per user
        _check_rate_limit(f"chat_minute:{current_user.id}", 10, 60)

        # Validate foreign key if provided
        if req.context_intel_id is not None:
            intel_exists = db.query(RawIntel).filter(RawIntel.id == req.context_intel_id).first()
            if not intel_exists:
                raise HTTPException(status_code=400, detail="Invalid context_intel_id")

        # Atomic increment to avoid race condition
        db.execute(
            update(User)
            .where(User.id == current_user.id)
            .values(daily_chats_used=User.daily_chats_used + 1)
        )
        db.flush()
        # Re-query from the same session to read the updated counter
        fresh_user = db.query(User).filter(User.id == current_user.id).first()
        limits = get_user_limits(fresh_user)
        if not fresh_user.is_vip and fresh_user.daily_chats_used > limits["daily_chats"]:
            db.rollback()
            raise HTTPException(status_code=429, detail=f"Daily chat limit reached. Upgrade to VIP for {settings.VIP_DAILY_CHATS} chats/day.")

    try:
        from .services.llm_service import query_with_context
        answer = await query_with_context(req.message, user_id=str(current_user.id))
    except Exception:
        if not settings.FREE_MODE:
            db.rollback()
            raise HTTPException(status_code=500, detail="LLM service unavailable")
        answer = "AI is currently unavailable. In a live deployment with an Anthropic API key, I would answer your question about CVEs, configurations, and security topics."

    if not settings.ANTHROPIC_API_KEY:
        answer = (
            "This is a demo response. In production with an Anthropic Claude API key configured, I would:\n\n"
            "1. Analyze your question about CVEs, configurations, or security topics\n"
            "2. Search relevant security advisories and documentation\n"
            "3. Provide a concise, actionable answer with citations\n\n"
            "Your question was: \"" + req.message[:200] + "\""
        )

    conv = Conversation(
        user_id=current_user.id,
        title=req.message[:50],
        messages=json.dumps([{"role": "user", "content": req.message}, {"role": "assistant", "content": answer}]),
        context_intel_id=req.context_intel_id,
    )
    db.add(conv)
    db.commit()

    return {"answer": answer}


# ── Saved Intel Routes ───────────────────────────────────────────────

@app.post("/api/intel/save", response_model=SavedItemIdOut, tags=["saved-intel"])
def save_intel(req: SavedItemCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not settings.FREE_MODE:
        count = db.query(SavedItem).filter(SavedItem.user_id == current_user.id).count()
        limits = get_user_limits(current_user)
        if not current_user.is_vip and count >= limits["saved_items"]:
            raise HTTPException(status_code=429, detail=f"Saved item limit reached. Upgrade to VIP for {settings.VIP_SAVED_ITEMS} items.")

    # Validate foreign key if provided
    if req.intel_id is not None:
        intel_exists = db.query(RawIntel).filter(RawIntel.id == req.intel_id).first()
        if not intel_exists:
            raise HTTPException(status_code=400, detail="Invalid intel_id")

    item = SavedItem(
        user_id=current_user.id,
        intel_id=req.intel_id,
        title=req.title,
        content=req.content,
        tags=json.dumps(req.tags),
        source=req.source,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid intel_id")
    return {"id": str(item.id)}


@app.get("/api/intel/saved", response_model=SavedIntelOut, tags=["saved-intel"])
def get_saved_intel(current_user: User = Depends(get_current_user), db: Session = Depends(get_db), q: str | None = Query(None, max_length=255), limit: int = Query(20, ge=0, le=100), offset: int = Query(0, ge=0, le=10000)):
    query = db.query(SavedItem).filter(SavedItem.user_id == current_user.id)
    if q:
        safe_q = q.replace("%", "\\%").replace("_", "\\_")
        query = query.filter(
            (SavedItem.title.ilike(f"%{safe_q}%")) | (SavedItem.content.ilike(f"%{safe_q}%"))
        )
    total = query.count()
    items = query.order_by(SavedItem.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": str(i.id),
                "title": i.title,
                "content": i.content[:200],
                "tags": json.loads(i.tags),
                "source": i.source,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ],
    }


@app.delete("/api/intel/saved/{item_id}", response_model=StatusOut, tags=["saved-intel"])
def delete_saved_intel(item_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(SavedItem).filter(SavedItem.id == item_id, SavedItem.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"status": "deleted"}


# ── Subscription Routes ──────────────────────────────────────────────

class SubscriptionStatusOut(BaseModel):
    status: str  # none, trialing, active, cancelled, past_due
    tier: str  # free, vip
    is_trial_active: bool
    is_vip_active: bool
    trial_ends_at: str | None = None
    subscription_ends_at: str | None = None
    subscription_renews_at: str | None = None
    cancelled_at: str | None = None
    days_remaining: int | None = None
    price_yearly_cents: int
    limits: dict


class StartTrialOut(BaseModel):
    success: bool
    message: str
    trial_ends_at: str | None = None


class SubscriptionUpgradeRequest(BaseModel):
    payment_method: str = Field(pattern="^(stripe|paypal)$")


class UpgradeOut(BaseModel):
    success: bool
    message: str
    checkout_url: str | None = None
    payment_method: str | None = None


@app.get("/api/subscription/status", response_model=SubscriptionStatusOut, tags=["subscription"])
def subscription_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if settings.FREE_MODE:
        return {
            "status": "active",
            "tier": "vip",
            "is_trial_active": False,
            "is_vip_active": True,
            "trial_ends_at": None,
            "subscription_ends_at": None,
            "subscription_renews_at": None,
            "cancelled_at": None,
            "days_remaining": None,
            "price_yearly_cents": settings.VIP_PRICE_YEARLY_CENTS,
            "limits": {"daily_briefings": 9999, "daily_chats": 9999, "saved_items": 9999},
        }
    now = datetime.now(timezone.utc)
    user = db.query(User).filter(User.id == current_user.id).first()
    status = user.subscription_status or "none"
    tier = user.subscription_tier or "free"
    trial_ends = _make_aware(user.trial_ends_at)
    sub_ends = _make_aware(user.subscription_ends_at)
    is_trial_active = bool(
        status == "trialing" and trial_ends and trial_ends > now
    )
    is_vip_active = user.is_vip or bool(user.is_pro)
    days_remaining = None
    if is_trial_active and trial_ends:
        days_remaining = max(0, (trial_ends - now).days)
    elif is_vip_active and sub_ends:
        days_remaining = max(0, (sub_ends - now).days)
    limits = get_user_limits(user)
    return {
        "status": status,
        "tier": tier,
        "is_trial_active": is_trial_active,
        "is_vip_active": is_vip_active,
        "trial_ends_at": user.trial_ends_at.isoformat() if user.trial_ends_at else None,
        "subscription_ends_at": user.subscription_ends_at.isoformat() if user.subscription_ends_at else None,
        "subscription_renews_at": user.subscription_renews_at.isoformat() if user.subscription_renews_at else None,
        "cancelled_at": user.cancelled_at.isoformat() if user.cancelled_at else None,
        "days_remaining": days_remaining,
        "price_yearly_cents": settings.VIP_PRICE_YEARLY_CENTS,
        "limits": limits,
    }


@app.post("/api/subscription/start-trial", response_model=StartTrialOut, tags=["subscription"])
def start_trial(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if settings.FREE_MODE:
        return {"success": True, "message": "Trial started (demo mode)", "trial_ends_at": None}
    user = db.query(User).filter(User.id == current_user.id).first()
    # Only allow trial if currently free and never had one
    if user.subscription_tier == "vip" and user.is_vip:
        raise HTTPException(status_code=400, detail="You already have an active VIP subscription.")
    if user.trial_started_at is not None:
        raise HTTPException(status_code=400, detail="Trial already used.")
    now = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=settings.TRIAL_DURATION_DAYS)
    user.subscription_tier = "vip"
    user.subscription_status = "trialing"
    user.trial_started_at = now
    user.trial_ends_at = trial_end
    user.subscription_ends_at = trial_end
    db.commit()
    return {
        "success": True,
        "message": f"Your {settings.TRIAL_DURATION_DAYS}-day VIP trial has started!",
        "trial_ends_at": trial_end.isoformat(),
    }


@app.post("/api/subscription/upgrade", response_model=UpgradeOut, tags=["subscription"])
def upgrade_vip(req: SubscriptionUpgradeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if settings.FREE_MODE:
        return {"success": True, "message": "Upgraded to VIP (demo mode)", "checkout_url": None, "payment_method": req.payment_method}
    user = db.query(User).filter(User.id == current_user.id).first()
    now = datetime.now(timezone.utc)
    # If already active VIP, block double-upgrade
    trial_ends = _make_aware(user.trial_ends_at)
    if user.subscription_tier == "vip" and user.is_vip and user.subscription_status == "active":
        raise HTTPException(status_code=400, detail="You already have an active VIP subscription.")
    # If on trial, keep trial end date and extend subscription from there
    base_date = trial_ends if trial_ends and trial_ends > now else now
    sub_end = base_date + timedelta(days=365)
    user.subscription_tier = "vip"
    user.subscription_status = "active"
    user.subscription_started_at = now
    user.subscription_ends_at = sub_end
    user.subscription_renews_at = sub_end
    user.is_pro = 1
    if req.payment_method == "stripe":
        user.stripe_customer_id = f"cus_mock_{user.id}"
        user.stripe_subscription_id = f"sub_mock_{user.id}"
    elif req.payment_method == "paypal":
        user.paypal_subscription_id = f"paypal_mock_{user.id}"
    db.commit()
    return {
        "success": True,
        "message": "Welcome to VIP! Your subscription is active.",
        "checkout_url": None,  # In production, return a Stripe/PayPal checkout URL
        "payment_method": req.payment_method,
    }


class CancelOut(BaseModel):
    status: str
    effective_until: str | None = None


@app.post("/api/subscription/cancel", response_model=CancelOut, tags=["subscription"])
def cancel_subscription(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if settings.FREE_MODE:
        return {"status": "cancelled", "effective_until": None}
    user = db.query(User).filter(User.id == current_user.id).first()
    if user.subscription_tier != "vip":
        raise HTTPException(status_code=400, detail="No active VIP subscription to cancel.")
    if user.subscription_status == "cancelled":
        raise HTTPException(status_code=400, detail="Subscription already cancelled.")
    now = datetime.now(timezone.utc)
    user.subscription_status = "cancelled"
    user.cancelled_at = now
    db.commit()
    return {
        "status": "cancelled",
        "effective_until": user.subscription_ends_at.isoformat() if user.subscription_ends_at else None,
    }


# ── Preferences Routes ───────────────────────────────────────────────

@app.get("/api/preferences", response_model=PreferencesOut, tags=["preferences"])
def get_preferences(current_user: User = Depends(get_current_user)):
    if settings.FREE_MODE:
        return {
            "tech_stack": ["cisco", "aws", "linux"],
            "severity_threshold": "medium",
            "sources": ["nvd", "github", "cisco"],
            "notification_time": "08:00",
        }
    try:
        prefs = json.loads(current_user.preferences_json or "{}")
    except json.JSONDecodeError:
        prefs = {}
    return prefs


@app.put("/api/preferences", response_model=StatusOut, tags=["preferences"])
def update_preferences(req: PreferencesUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user.id).first()
    user.preferences_json = req.model_dump_json()
    db.commit()
    return {"status": "ok"}


# ── Admin Routes ─────────────────────────────────────────────────────

def admin_auth_with_rate_limit(request: Request, x_admin_key: str = Header(None, alias="X-Admin-Key")):
    """Verify admin API key and apply rate limiting."""
    client_ip = _get_client_ip(request)
    _check_admin_rate_limit(client_ip)
    expected = getattr(settings, "ADMIN_API_KEY", None)
    if not expected:
        raise HTTPException(status_code=403, detail="Admin access not configured")
    if x_admin_key is None or not secrets.compare_digest(x_admin_key, expected):
        _log_security_event("failed_admin_key", ip_address=client_ip, outcome="failure")
        raise HTTPException(status_code=403, detail="Invalid admin key")
    return True


@app.get("/api/admin/stats", response_model=AdminStatsOut, tags=["admin"])
def admin_stats(request: Request, db: Session = Depends(get_db), _: bool = Depends(admin_auth_with_rate_limit)):
    # Build stats from individual scalar queries so empty RawIntel does not hide user counts
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_intel = db.query(func.count(RawIntel.id)).scalar() or 0
    briefings_today = db.query(func.count(Briefing.id)).filter(Briefing.briefing_date == today).scalar() or 0
    critical_items = db.query(func.count(RawIntel.id)).filter(RawIntel.severity == "critical").scalar() or 0

    sev_counts = db.query(
        func.coalesce(func.sum(case((RawIntel.severity == "critical", 1), else_=0)), 0).label("sev_critical"),
        func.coalesce(func.sum(case((RawIntel.severity == "high", 1), else_=0)), 0).label("sev_high"),
        func.coalesce(func.sum(case((RawIntel.severity == "medium", 1), else_=0)), 0).label("sev_medium"),
        func.coalesce(func.sum(case((RawIntel.severity == "low", 1), else_=0)), 0).label("sev_low"),
        func.coalesce(func.sum(case((RawIntel.severity == "info", 1), else_=0)), 0).label("sev_info"),
        func.coalesce(func.sum(case((RawIntel.source == "nvd", 1), else_=0)), 0).label("src_nvd"),
        func.coalesce(func.sum(case((RawIntel.source == "github", 1), else_=0)), 0).label("src_github"),
        func.coalesce(func.sum(case((RawIntel.source == "cisco", 1), else_=0)), 0).label("src_cisco"),
    ).select_from(RawIntel).first()

    if sev_counts is None:
        sev_counts = type('obj', (object,), {
            'sev_critical': 0, 'sev_high': 0, 'sev_medium': 0, 'sev_low': 0, 'sev_info': 0,
            'src_nvd': 0, 'src_github': 0, 'src_cisco': 0
        })()

    return {
        "total_users": total_users,
        "total_intel": total_intel,
        "briefings_today": briefings_today,
        "critical_items": critical_items,
        "severity_breakdown": {
            "critical": sev_counts.sev_critical,
            "high": sev_counts.sev_high,
            "medium": sev_counts.sev_medium,
            "low": sev_counts.sev_low,
            "info": sev_counts.sev_info,
        },
        "source_breakdown": {
            "nvd": sev_counts.src_nvd,
            "github": sev_counts.src_github,
            "cisco": sev_counts.src_cisco,
        },
    }


@app.get("/api/admin/intel", response_model=list[AdminIntelItem], tags=["admin"])
def admin_intel(request: Request, limit: int = Query(20, ge=0, le=100), offset: int = Query(0, ge=0, le=10000), db: Session = Depends(get_db), _: bool = Depends(admin_auth_with_rate_limit)):
    items = (
        db.query(RawIntel)
        .order_by(RawIntel.published_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(i.id),
            "source": i.source,
            "source_id": i.source_id,
            "title": i.title,
            "severity": i.severity,
            "cvss_score": i.cvss_score,
            "published_at": i.published_at.isoformat() if i.published_at else None,
            "fetched_at": i.fetched_at.isoformat() if i.fetched_at else None,
        }
        for i in items
    ]


@app.get("/api/admin/users", response_model=list[AdminUserItem], tags=["admin"])
def admin_users(request: Request, limit: int = Query(50, ge=0, le=100), offset: int = Query(0, ge=0, le=10000), db: Session = Depends(get_db), _: bool = Depends(admin_auth_with_rate_limit)):
    users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "name": u.name,
            "is_pro": u.is_vip or bool(u.is_pro),
            "subscription_tier": u.subscription_tier or "free",
            "subscription_status": u.subscription_status or "none",
            "trial_ends_at": u.trial_ends_at.isoformat() if u.trial_ends_at else None,
            "subscription_ends_at": u.subscription_ends_at.isoformat() if u.subscription_ends_at else None,
            "stripe_customer_id": u.stripe_customer_id,
            "paypal_subscription_id": u.paypal_subscription_id,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "daily_chats_used": u.daily_chats_used,
        }
        for u in users
    ]


# ── Health Check ─────────────────────────────────────────────────────

@app.get("/health", response_model=HealthOut, tags=["health"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return {"status": "degraded", "database": "disconnected"}
