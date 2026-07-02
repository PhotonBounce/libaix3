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

# ── Security ──────────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_client_ip(request: Request) -> str:
    """Extract real client IP from request, respecting reverse proxy headers."""
    # In production behind nginx, X-Real-IP is set by nginx and is trustworthy
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def _log_security_event(event_type: str, ip_address: str, user_id: str | None = None, outcome: str = "success"):
    # Hash sensitive PII before logging
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


# Redis-backed rate limiter for auth endpoints
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
        # In-memory fallback (single-process only)
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


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
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
        # In-memory fallback (single-process only)
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
    daily_briefings_used: int
    daily_chats_used: int

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
    # Redis is required for security-critical state (rate limiting, token blacklist)
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
    return current_user


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
        raise HTTPException(status_code=404, detail="Briefing not ready yet. Check back later.")
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
    db.expire(current_user)
    # Re-query from the same session to read the updated counter
    fresh_user = db.query(User).filter(User.id == current_user.id).first()
    if not fresh_user.is_pro and fresh_user.daily_chats_used > settings.FREE_DAILY_CHATS:
        db.rollback()
        raise HTTPException(status_code=429, detail="Daily chat limit reached. Upgrade to Pro.")

    try:
        # Simple LLM response for MVP (no RAG yet)
        from .services.llm_service import query_with_context
        answer = await query_with_context(req.message, user_id=str(current_user.id))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="LLM service unavailable")

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
    count = db.query(SavedItem).filter(SavedItem.user_id == current_user.id).count()
    if not current_user.is_pro and count >= settings.FREE_SAVED_ITEMS:
        raise HTTPException(status_code=429, detail="Saved item limit reached. Upgrade to Pro.")

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


# ── Preferences Routes ───────────────────────────────────────────────

@app.get("/api/preferences", response_model=PreferencesOut, tags=["preferences"])
def get_preferences(current_user: User = Depends(get_current_user)):
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
            "is_pro": bool(u.is_pro),
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
