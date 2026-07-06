"""OpsBrief — SQLAlchemy models. 5 tables, no multi-tenant."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import func

from .config import settings

# Use plain UUID for SQLite compatibility, PG_UUID for PostgreSQL
UuidType = PG_UUID if "postgresql" in settings.DATABASE_URL else String

Base = declarative_base()
if "sqlite" in settings.DATABASE_URL:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True,
        echo=False,
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class User(Base):
    """A single user account."""

    __tablename__ = "users"

    id = Column(UuidType, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_pro = Column(Integer, default=0)  # boolean as int for SQLite compat (deprecated, use subscription fields)
    pro_expires_at = Column(DateTime(timezone=True), nullable=True)  # deprecated

    # Subscription / trial tracking (VIP tier)
    subscription_tier = Column(String(20), default="free", nullable=False)  # free, vip
    subscription_status = Column(String(20), default="none", nullable=False)  # none, trialing, active, cancelled, past_due
    trial_started_at = Column(DateTime(timezone=True), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    subscription_started_at = Column(DateTime(timezone=True), nullable=True)
    subscription_ends_at = Column(DateTime(timezone=True), nullable=True)
    subscription_renews_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    # Payment provider fields
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    paypal_subscription_id = Column(String(255), nullable=True)

    # Preferences stored as JSON string for simplicity
    preferences_json = Column(Text, default='{}')

    # Rate-limiting counters (reset daily via Celery)
    daily_briefings_used = Column(Integer, default=0)
    daily_chats_used = Column(Integer, default=0)
    counters_reset_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    briefings = relationship("Briefing", back_populates="user", cascade="all, delete-orphan")
    saved_items = relationship("SavedItem", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    crypto_payments = relationship("CryptoPayment", back_populates="user", cascade="all, delete-orphan")

    @property
    def is_vip(self) -> bool:
        """Check if user has an active VIP subscription or valid trial."""
        if self.subscription_tier != "vip":
            return False
        now = datetime.now(timezone.utc)
        if self.subscription_status == "trialing":
            trial_ends = self.trial_ends_at
            if trial_ends is not None and trial_ends.tzinfo is None:
                trial_ends = trial_ends.replace(tzinfo=timezone.utc)
            return trial_ends is None or trial_ends > now
        if self.subscription_status in ("active", "trialing"):
            sub_ends = self.subscription_ends_at
            if sub_ends is not None and sub_ends.tzinfo is None:
                sub_ends = sub_ends.replace(tzinfo=timezone.utc)
            return sub_ends is None or sub_ends > now
        return False


class RawIntel(Base):
    """Aggregated intelligence from external sources."""

    __tablename__ = "raw_intel"

    id = Column(UuidType, primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(50), nullable=False, index=True)
    source_id = Column(String(255), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=True)
    url = Column(String(1000), nullable=True)
    severity = Column(String(20), default="info", index=True)  # critical, high, medium, low, info
    cvss_score = Column(Float, nullable=True)
    affected_products = Column(Text, default='[]')  # JSON list of strings
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_raw_intel_source"),
        Index("ix_raw_intel_source_source_id", "source", "source_id"),
    )


class Briefing(Base):
    """Personalized daily digest generated per user."""

    __tablename__ = "briefings"

    id = Column(UuidType, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UuidType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    briefing_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    items = Column(Text, default='[]')  # JSON array of briefing items
    item_count = Column(Integer, default=0)
    is_read = Column(Integer, default=0)
    is_ready = Column(Integer, default=0)  # notification sent
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="briefings")


class SavedItem(Base):
    """User's personal knowledge base."""

    __tablename__ = "saved_items"

    id = Column(UuidType, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UuidType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    intel_id = Column(UuidType, ForeignKey("raw_intel.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(Text, default='[]')  # JSON array
    source = Column(String(50), default="briefing")  # briefing, chat, diagnosis
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", back_populates="saved_items")


class PaymentEvent(Base):
    """Audit log for payment provider webhook events."""

    __tablename__ = "payment_events"

    id = Column(UuidType, primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String(20), nullable=False, index=True)  # stripe, paypal, crypto
    event_type = Column(String(100), nullable=False, index=True)
    event_id = Column(String(255), nullable=False, index=True)
    payload_json = Column(Text, default='{}')
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user_id = Column(UuidType, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(20), default="pending")  # pending, processed, failed


class CryptoPayment(Base):
    """Crypto payment records for VIP subscription purchases."""

    __tablename__ = "crypto_payments"

    id = Column(UuidType, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UuidType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chain = Column(String(20), nullable=False, index=True)  # eth, btc, sol, tron, bnb, polygon, linea, base, arbitrum, op
    tx_hash = Column(String(255), nullable=False, index=True)
    amount_native = Column(String(50), nullable=False)  # raw amount in native token (string for precision)
    amount_usd = Column(Float, nullable=True)  # USD equivalent at verification time
    verified = Column(Integer, default=0)  # 0 = pending, 1 = verified
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="crypto_payments")

    __table_args__ = (
        UniqueConstraint("chain", "tx_hash", name="uq_crypto_payment_chain_tx"),
    )


class Conversation(Base):
    """Chat history for follow-up questions."""

    __tablename__ = "conversations"

    id = Column(UuidType, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UuidType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    messages = Column(Text, default='[]')  # JSON array of {role, content, timestamp}
    context_intel_id = Column(UuidType, ForeignKey("raw_intel.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="conversations")
