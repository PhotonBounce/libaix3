"""OpsBrief — Payment webhook handlers for Stripe and PayPal.

Endpoints:
  POST /api/webhooks/stripe   — Stripe webhook events
  POST /api/webhooks/paypal   — PayPal webhook events
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..models import CryptoPayment, PaymentEvent, SessionLocal, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["payments"])

# ── DB helper (same pattern as main.py) ───────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Stripe helpers ────────────────────────────────────────────────────

# Lazy import stripe to avoid hard dependency if not configured
_stripe = None

def _get_stripe():
    global _stripe
    if _stripe is None:
        import stripe as stripe_lib
        stripe_lib.api_key = settings.STRIPE_SECRET_KEY or ""
        _stripe = stripe_lib
    return _stripe


# ── PayPal helpers ────────────────────────────────────────────────────

_paypal_token_cache: dict[str, Any] = {}


async def _get_paypal_access_token() -> str:
    """Fetch (and cache) a PayPal access token."""
    cached = _paypal_token_cache.get("token")
    expires = _paypal_token_cache.get("expires", 0)
    if cached and datetime.now(timezone.utc).timestamp() < expires:
        return cached

    if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
        raise RuntimeError("PayPal credentials not configured")

    base_url = settings.PAYPAL_API_BASE
    auth = base64.b64encode(
        f"{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_CLIENT_SECRET}".encode()
    ).decode()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base_url}/v1/oauth2/token",
            headers={"Authorization": f"Basic {auth}"},
            data="grant_type=client_credentials",
        )
        resp.raise_for_status()
        data = resp.json()
        token = data["access_token"]
        expires_in = data.get("expires_in", 30000)
        _paypal_token_cache["token"] = token
        _paypal_token_cache["expires"] = datetime.now(timezone.utc).timestamp() + expires_in - 60
        return token


async def _verify_paypal_event(event_id: str) -> dict:
    """Verify a PayPal webhook event by fetching it from the API."""
    token = await _get_paypal_access_token()
    base_url = settings.PAYPAL_API_BASE
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{base_url}/v1/notifications/webhooks-events/{event_id}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()


# ─── Logging helper ───────────────────────────────────────────────────

def _log_payment_event(
    db: Session,
    provider: str,
    event_type: str,
    event_id: str,
    payload: dict,
    user_id: str | None = None,
    status: str = "pending",
) -> None:
    """Persist a webhook event for audit/debugging."""
    try:
        event = PaymentEvent(
            provider=provider,
            event_type=event_type,
            event_id=event_id,
            payload_json=json.dumps(payload),
            user_id=user_id,
            status=status,
        )
        db.add(event)
        db.commit()
    except Exception as exc:
        logger.error(f"Failed to log payment event: {exc}")
        db.rollback()


# ─── User subscription helpers ────────────────────────────────────────

def _activate_vip(
    db: Session,
    user: User,
    provider: str,
    customer_id: str | None = None,
    subscription_id: str | None = None,
    ends_at: datetime | None = None,
) -> None:
    """Mark a user as active VIP with a 1-year renewal."""
    now = datetime.now(timezone.utc)
    user.subscription_tier = "vip"
    user.subscription_status = "active"
    user.subscription_started_at = now
    user.subscription_ends_at = ends_at or (now + timedelta(days=365))
    user.subscription_renews_at = user.subscription_ends_at
    user.is_pro = 1
    if provider == "stripe":
        user.stripe_customer_id = customer_id
        user.stripe_subscription_id = subscription_id
    elif provider == "paypal":
        user.paypal_subscription_id = subscription_id
    db.add(user)
    db.commit()


def _cancel_vip(db: Session, user: User) -> None:
    """Mark a user subscription as cancelled (keep access until end date)."""
    user.subscription_status = "cancelled"
    user.cancelled_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()


def _mark_past_due(db: Session, user: User) -> None:
    """Mark a subscription as past_due."""
    user.subscription_status = "past_due"
    db.add(user)
    db.commit()


def _find_user_by_stripe_customer(db: Session, customer_id: str) -> User | None:
    return db.query(User).filter(User.stripe_customer_id == customer_id).first()


def _find_user_by_paypal_subscription(db: Session, subscription_id: str) -> User | None:
    return db.query(User).filter(User.paypal_subscription_id == subscription_id).first()


# ═══════════════════════════════════════════════════════════════════════
#  Stripe Webhook
# ═══════════════════════════════════════════════════════════════════════

@router.post("/webhooks/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
):
    """Handle Stripe webhook events."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.warning("Stripe webhook received but STRIPE_WEBHOOK_SECRET is not set")
        raise HTTPException(status_code=500, detail="Stripe webhook not configured")

    payload = await request.body()
    body_text = payload.decode("utf-8") if isinstance(payload, bytes) else payload

    try:
        stripe = _get_stripe()
        event = stripe.Webhook.construct_event(
            body_text, stripe_signature or "", settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as exc:
        logger.warning(f"Stripe webhook signature verification failed: {exc}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_id = event.get("id", "unknown")
    event_type = event.get("type", "unknown")
    data_obj = event.get("data", {}).get("object", {})

    logger.info(f"Stripe webhook received: {event_type} ({event_id})")

    _log_payment_event(db, "stripe", event_type, event_id, event)

    # ── checkout.session.completed ────────────────────────────────────
    if event_type == "checkout.session.completed":
        customer_id = data_obj.get("customer")
        subscription_id = data_obj.get("subscription")
        user = _find_user_by_stripe_customer(db, customer_id) if customer_id else None
        if user:
            _activate_vip(
                db, user, "stripe",
                customer_id=customer_id,
                subscription_id=subscription_id,
            )
            logger.info(f"Activated VIP for user {user.id} via Stripe checkout")
        else:
            logger.warning(f"Stripe checkout completed but no user found for customer {customer_id}")

    # ── invoice.paid ──────────────────────────────────────────────────
    elif event_type == "invoice.paid":
        customer_id = data_obj.get("customer")
        subscription_id = data_obj.get("subscription")
        lines = data_obj.get("lines", {}).get("data", [])
        period_end = None
        if lines:
            period_end = lines[0].get("period", {}).get("end")
        user = _find_user_by_stripe_customer(db, customer_id) if customer_id else None
        if user:
            ends_at = datetime.fromtimestamp(period_end, tz=timezone.utc) if period_end else None
            _activate_vip(
                db, user, "stripe",
                customer_id=customer_id,
                subscription_id=subscription_id,
                ends_at=ends_at,
            )
            logger.info(f"Extended VIP for user {user.id} via invoice.paid")
        else:
            logger.warning(f"invoice.paid but no user found for customer {customer_id}")

    # ── invoice.payment_failed ────────────────────────────────────────
    elif event_type == "invoice.payment_failed":
        customer_id = data_obj.get("customer")
        user = _find_user_by_stripe_customer(db, customer_id) if customer_id else None
        if user:
            _mark_past_due(db, user)
            logger.info(f"Marked past_due for user {user.id} via invoice.payment_failed")
        else:
            logger.warning(f"invoice.payment_failed but no user found for customer {customer_id}")

    # ── customer.subscription.updated ───────────────────────────────
    elif event_type == "customer.subscription.updated":
        customer_id = data_obj.get("customer")
        subscription_id = data_obj.get("id")
        sub_status = data_obj.get("status")
        current_period_end = data_obj.get("current_period_end")
        user = _find_user_by_stripe_customer(db, customer_id) if customer_id else None
        if user:
            if sub_status == "active":
                ends_at = datetime.fromtimestamp(current_period_end, tz=timezone.utc) if current_period_end else None
                _activate_vip(db, user, "stripe", customer_id=customer_id, subscription_id=subscription_id, ends_at=ends_at)
            elif sub_status == "canceled":
                _cancel_vip(db, user)
            elif sub_status == "past_due":
                _mark_past_due(db, user)
            logger.info(f"Synced subscription for user {user.id} via customer.subscription.updated ({sub_status})")
        else:
            logger.warning(f"customer.subscription.updated but no user found for customer {customer_id}")

    # ── customer.subscription.deleted ─────────────────────────────────
    elif event_type == "customer.subscription.deleted":
        customer_id = data_obj.get("customer")
        user = _find_user_by_stripe_customer(db, customer_id) if customer_id else None
        if user:
            _cancel_vip(db, user)
            logger.info(f"Cancelled VIP for user {user.id} via customer.subscription.deleted")
        else:
            logger.warning(f"customer.subscription.deleted but no user found for customer {customer_id}")

    return {"status": "ok"}


# ═══════════════════════════════════════════════════════════════════════
#  PayPal Webhook
# ═══════════════════════════════════════════════════════════════════════

@router.post("/webhooks/paypal", status_code=status.HTTP_200_OK)
async def paypal_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle PayPal webhook events.

    PayPal does not send a pre-verified signature header in the same way Stripe does.
    We verify by fetching the event from PayPal's API using the event ID.
    """
    if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
        logger.warning("PayPal webhook received but credentials are not set")
        raise HTTPException(status_code=500, detail="PayPal webhook not configured")

    try:
        payload = await request.json()
    except Exception as exc:
        logger.warning(f"PayPal webhook invalid JSON: {exc}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_id = payload.get("id", "unknown")
    event_type = payload.get("event_type", "unknown")

    # Verify event with PayPal API
    try:
        verified = await _verify_paypal_event(event_id)
    except Exception as exc:
        logger.warning(f"PayPal event verification failed for {event_id}: {exc}")
        raise HTTPException(status_code=400, detail="Event verification failed")

    # Use the verified payload from PayPal API (not the raw webhook payload)
    data = verified.get("resource", {})
    event_type = verified.get("event_type", event_type)

    logger.info(f"PayPal webhook received: {event_type} ({event_id})")

    _log_payment_event(db, "paypal", event_type, event_id, verified)

    # ── BILLING.SUBSCRIPTION.ACTIVATED ──────────────────────────────
    if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
        subscription_id = data.get("id")
        # Try to find user by PayPal subscription ID
        user = _find_user_by_paypal_subscription(db, subscription_id) if subscription_id else None
        if not user:
            # Fallback: custom_id or subscriber.email can be used to link
            custom_id = data.get("custom_id")
            if custom_id:
                user = db.query(User).filter(User.id == custom_id).first()
        if user:
            _activate_vip(db, user, "paypal", subscription_id=subscription_id)
            logger.info(f"Activated VIP for user {user.id} via PayPal subscription activated")
        else:
            logger.warning(f"PayPal ACTIVATED but no user found for subscription {subscription_id}")

    # ── BILLING.SUBSCRIPTION.CANCELLED ──────────────────────────────
    elif event_type == "BILLING.SUBSCRIPTION.CANCELLED":
        subscription_id = data.get("id")
        user = _find_user_by_paypal_subscription(db, subscription_id) if subscription_id else None
        if user:
            _cancel_vip(db, user)
            logger.info(f"Cancelled VIP for user {user.id} via PayPal subscription cancelled")
        else:
            logger.warning(f"PayPal CANCELLED but no user found for subscription {subscription_id}")

    # ── BILLING.SUBSCRIPTION.SUSPENDED ────────────────────────────────
    elif event_type == "BILLING.SUBSCRIPTION.SUSPENDED":
        subscription_id = data.get("id")
        user = _find_user_by_paypal_subscription(db, subscription_id) if subscription_id else None
        if user:
            _mark_past_due(db, user)
            logger.info(f"Marked past_due for user {user.id} via PayPal subscription suspended")
        else:
            logger.warning(f"PayPal SUSPENDED but no user found for subscription {subscription_id}")

    # ── BILLING.SUBSCRIPTION.PAYMENT.FAILED ───────────────────────────
    elif event_type == "BILLING.SUBSCRIPTION.PAYMENT.FAILED":
        subscription_id = data.get("id")
        user = _find_user_by_paypal_subscription(db, subscription_id) if subscription_id else None
        if user:
            _mark_past_due(db, user)
            logger.info(f"Marked past_due for user {user.id} via PayPal payment failed")
        else:
            logger.warning(f"PayPal PAYMENT.FAILED but no user found for subscription {subscription_id}")

    # ── BILLING.SUBSCRIPTION.RE-ACTIVATED ─────────────────────────────
    elif event_type == "BILLING.SUBSCRIPTION.RE-ACTIVATED":
        subscription_id = data.get("id")
        user = _find_user_by_paypal_subscription(db, subscription_id) if subscription_id else None
        if user:
            _activate_vip(db, user, "paypal", subscription_id=subscription_id)
            logger.info(f"Re-activated VIP for user {user.id} via PayPal subscription re-activated")
        else:
            logger.warning(f"PayPal RE-ACTIVATED but no user found for subscription {subscription_id}")

    # ── BILLING.SUBSCRIPTION.UPDATED ──────────────────────────────────
    elif event_type == "BILLING.SUBSCRIPTION.UPDATED":
        subscription_id = data.get("id")
        status_val = data.get("status", "").upper()
        user = _find_user_by_paypal_subscription(db, subscription_id) if subscription_id else None
        if user:
            if status_val == "ACTIVE":
                _activate_vip(db, user, "paypal", subscription_id=subscription_id)
            elif status_val == "CANCELLED":
                _cancel_vip(db, user)
            elif status_val == "SUSPENDED":
                _mark_past_due(db, user)
            logger.info(f"Synced PayPal subscription for user {user.id} status={status_val}")
        else:
            logger.warning(f"PayPal UPDATED but no user found for subscription {subscription_id}")

    return {"status": "ok"}


# ═══════════════════════════════════════════════════════════════════════
#  Payment event audit log (admin)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/admin/payments/events", tags=["admin"])
def list_payment_events(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    provider: str | None = None,
    db: Session = Depends(get_db),
):
    """List recent payment webhook events (admin only)."""
    from ..main import admin_auth_with_rate_limit
    _ = Depends(admin_auth_with_rate_limit)  # type: ignore[assignment]
    # Actually invoke it manually since we can't use Depends in a nested way here
    admin_auth_with_rate_limit(request, x_admin_key=request.headers.get("X-Admin-Key"))

    query = db.query(PaymentEvent).order_by(PaymentEvent.processed_at.desc())
    if provider:
        query = query.filter(PaymentEvent.provider == provider)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": str(e.id),
                "provider": e.provider,
                "event_type": e.event_type,
                "event_id": e.event_id,
                "user_id": str(e.user_id) if e.user_id else None,
                "status": e.status,
                "processed_at": e.processed_at.isoformat() if e.processed_at else None,
            }
            for e in items
        ],
    }


# ═══════════════════════════════════════════════════════════════════════
#  Crypto Payment Verification
# ═══════════════════════════════════════════════════════════════════════

CRYPTO_CHAIN_CONFIG = {
    "eth": {
        "wallet": settings.CRYPTO_WALLET_ETH,
        "rpc": "https://cloudflare-eth.com",
        "coingecko_id": "ethereum",
    },
    "btc": {
        "wallet": settings.CRYPTO_WALLET_BTC,
        "coingecko_id": "bitcoin",
    },
    "sol": {
        "wallet": settings.CRYPTO_WALLET_SOL,
        "rpc": "https://api.mainnet-beta.solana.com",
        "coingecko_id": "solana",
    },
    "tron": {
        "wallet": settings.CRYPTO_WALLET_TRON,
        "coingecko_id": "tron",
    },
    "bnb": {
        "wallet": settings.CRYPTO_WALLET_BNB,
        "rpc": "https://bsc-dataseed.binance.org/",
        "coingecko_id": "binancecoin",
    },
    "polygon": {
        "wallet": settings.CRYPTO_WALLET_POLYGON,
        "rpc": "https://polygon-rpc.com",
        "coingecko_id": "matic-network",
    },
    "linea": {
        "wallet": settings.CRYPTO_WALLET_LINEA,
        "rpc": "https://rpc.linea.build",
        "coingecko_id": "ethereum",
    },
    "base": {
        "wallet": settings.CRYPTO_WALLET_BASE,
        "rpc": "https://mainnet.base.org",
        "coingecko_id": "ethereum",
    },
    "arbitrum": {
        "wallet": settings.CRYPTO_WALLET_ARBITRUM,
        "rpc": "https://arb1.arbitrum.io/rpc",
        "coingecko_id": "ethereum",
    },
    "op": {
        "wallet": settings.CRYPTO_WALLET_OPTIMISM,
        "rpc": "https://mainnet.optimism.io",
        "coingecko_id": "ethereum",
    },
}

# Approximate minimum native amounts for ~$2 USD (fallback if price API fails)
_MIN_NATIVE_FALLBACK = {
    "eth": 0.0006,
    "btc": 0.00002,
    "sol": 0.01,
    "tron": 25.0,
    "bnb": 0.003,
    "polygon": 2.5,
    "linea": 0.0006,
    "base": 0.0006,
    "arbitrum": 0.0006,
    "op": 0.0006,
}


async def _get_coingecko_price_usd(coingecko_id: str) -> float | None:
    """Fetch current USD price from CoinGecko (free tier, no API key)."""
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            data = resp.json()
            price = data.get(coingecko_id, {}).get("usd")
            return float(price) if price is not None else None
    except Exception as exc:
        logger.warning(f"CoinGecko price fetch failed: {exc}")
        return None


async def _verify_evm_tx(rpc_url: str, tx_hash: str, expected_to: str) -> dict | None:
    """Verify an EVM transaction via JSON-RPC."""
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getTransactionByHash",
        "params": [tx_hash],
        "id": 1,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            rpc_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        result = data.get("result")
        if not result:
            return None
        # Must be mined (not pending)
        if not result.get("blockHash"):
            return None
        tx_to = (result.get("to") or "").lower()
        if tx_to != expected_to.lower():
            return None
        value_wei = int(result.get("value", "0x0"), 16)
        return {"value_wei": value_wei}


async def _verify_btc_tx(tx_hash: str, expected_to: str) -> dict | None:
    """Verify a BTC transaction via BlockCypher."""
    url = f"https://api.blockcypher.com/v1/btc/main/txs/{tx_hash}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        if data.get("confirmations", 0) < 1:
            return None
        outputs = data.get("outputs", [])
        total_received = 0
        for out in outputs:
            addresses = out.get("addresses") or []
            if expected_to in addresses:
                total_received += out.get("value", 0)
        if total_received <= 0:
            return None
        return {"value_sat": total_received}


async def _verify_eth_blockcypher(tx_hash: str, expected_to: str) -> dict | None:
    """Verify an ETH transaction via BlockCypher."""
    url = f"https://api.blockcypher.com/v1/eth/main/txs/{tx_hash}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        if data.get("confirmations", 0) < 1:
            return None
        tx_to = (data.get("to") or "").lower()
        if tx_to != expected_to.lower():
            return None
        return {"value_wei": data.get("value", 0)}


async def _verify_sol_tx(tx_hash: str, expected_to: str) -> dict | None:
    """Verify a Solana transaction via RPC."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            tx_hash,
            {"encoding": "json", "commitment": "confirmed", "maxSupportedTransactionVersion": 0},
        ],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post("https://api.mainnet-beta.solana.com", json=payload)
        resp.raise_for_status()
        data = resp.json()
        result = data.get("result")
        if not result:
            return None
        meta = result.get("meta", {})
        if meta.get("err") is not None:
            return None
        account_keys = result.get("transaction", {}).get("message", {}).get("accountKeys", [])
        target_idx = None
        for idx, key in enumerate(account_keys):
            if key == expected_to:
                target_idx = idx
                break
        if target_idx is None:
            return None
        pre_balances = meta.get("preBalances", [])
        post_balances = meta.get("postBalances", [])
        if target_idx >= len(pre_balances) or target_idx >= len(post_balances):
            return None
        lamports_received = post_balances[target_idx] - pre_balances[target_idx]
        if lamports_received <= 0:
            return None
        return {"value_lamports": lamports_received}


async def _verify_tron_tx(tx_hash: str, expected_to: str) -> dict | None:
    """Verify a TRON transaction via Tronscan API."""
    url = f"https://apilist.tronscanapi.com/api/transaction-info?hash={tx_hash}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        if data.get("contractRet") != "SUCCESS":
            return None
        to_addr = data.get("toAddress", "")
        if to_addr != expected_to:
            return None
        amount = float(data.get("contractData", {}).get("amount", 0))
        return {"value_sun": amount}


async def _verify_crypto_tx(chain: str, tx_hash: str, expected_wallet: str) -> dict | None:
    """Route tx verification to the correct chain handler."""
    if chain == "btc":
        return await _verify_btc_tx(tx_hash, expected_wallet)
    elif chain == "eth":
        try:
            return await _verify_eth_blockcypher(tx_hash, expected_wallet)
        except Exception:
            return await _verify_evm_tx("https://cloudflare-eth.com", tx_hash, expected_wallet)
    elif chain == "sol":
        return await _verify_sol_tx(tx_hash, expected_wallet)
    elif chain == "tron":
        return await _verify_tron_tx(tx_hash, expected_wallet)
    elif chain in ("bnb", "polygon", "linea", "base", "arbitrum", "op"):
        rpc = CRYPTO_CHAIN_CONFIG[chain]["rpc"]
        return await _verify_evm_tx(rpc, tx_hash, expected_wallet)
    return None


def _calculate_usd_value(chain: str, tx_info: dict, price: float | None) -> float | None:
    """Convert native transaction amount to USD."""
    if chain == "btc":
        native = tx_info.get("value_sat", 0) / 1e8
    elif chain == "sol":
        native = tx_info.get("value_lamports", 0) / 1e9
    elif chain == "tron":
        native = tx_info.get("value_sun", 0) / 1e6
    else:
        native = tx_info.get("value_wei", 0) / 1e18
    if price is not None:
        return native * price
    return None


# ── Pydantic schemas for crypto ────────────────────────────────────────

class CryptoPaymentRequest(BaseModel):
    chain: str = Field(pattern="^(eth|btc|sol|tron|bnb|polygon|linea|base|arbitrum|op)$")
    tx_hash: str = Field(max_length=255)
    amount: str = Field(max_length=50)
    user_id: str = Field(max_length=36)


class CryptoPaymentResponse(BaseModel):
    success: bool
    message: str
    amount_usd: float | None = None
    verified: bool = False


class CryptoWalletsOut(BaseModel):
    eth: str | None
    btc: str | None
    sol: str | None
    tron: str | None
    bnb: str | None
    polygon: str | None
    linea: str | None
    base: str | None
    arbitrum: str | None
    op: str | None


# ═══════════════════════════════════════════════════════════════════════
#  Crypto Payment Routes
# ═══════════════════════════════════════════════════════════════════════

@router.get("/api/payments/crypto/wallets", response_model=CryptoWalletsOut, tags=["payments"])
def get_crypto_wallets():
    """Return all crypto wallet addresses for the frontend."""
    return {
        "eth": settings.CRYPTO_WALLET_ETH,
        "btc": settings.CRYPTO_WALLET_BTC,
        "sol": settings.CRYPTO_WALLET_SOL,
        "tron": settings.CRYPTO_WALLET_TRON,
        "bnb": settings.CRYPTO_WALLET_BNB,
        "polygon": settings.CRYPTO_WALLET_POLYGON,
        "linea": settings.CRYPTO_WALLET_LINEA,
        "base": settings.CRYPTO_WALLET_BASE,
        "arbitrum": settings.CRYPTO_WALLET_ARBITRUM,
        "op": settings.CRYPTO_WALLET_OPTIMISM,
    }


@router.post("/api/payments/crypto", response_model=CryptoPaymentResponse, tags=["payments"])
async def submit_crypto_payment(
    req: CryptoPaymentRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Submit a crypto payment for verification.

    Verifies the transaction on-chain, checks the amount is >= $2 USD,
    and upgrades the user to VIP for 1 year if valid.
    """
    # Authenticate user
    from ..main import get_current_user

    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
    try:
        current_user = get_current_user(token=token, db=db)
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Verify user_id matches authenticated user
    if str(current_user.id) != req.user_id:
        raise HTTPException(status_code=403, detail="user_id does not match authenticated user")

    # Validate chain
    if req.chain not in CRYPTO_CHAIN_CONFIG:
        raise HTTPException(status_code=400, detail="Unsupported chain")

    # Check for duplicate transaction
    existing = db.query(CryptoPayment).filter(
        CryptoPayment.chain == req.chain,
        CryptoPayment.tx_hash == req.tx_hash,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Transaction already processed")

    # Verify on-chain
    config = CRYPTO_CHAIN_CONFIG[req.chain]
    try:
        tx_info = await _verify_crypto_tx(req.chain, req.tx_hash, config["wallet"])
    except Exception as exc:
        logger.error(f"Crypto tx verification failed for {req.chain} {req.tx_hash}: {exc}")
        raise HTTPException(status_code=400, detail="Transaction verification failed")

    if not tx_info:
        raise HTTPException(
            status_code=400,
            detail="Transaction not found, not confirmed, or recipient mismatch",
        )

    # Calculate USD value
    price = await _get_coingecko_price_usd(config["coingecko_id"])
    amount_usd = _calculate_usd_value(req.chain, tx_info, price)

    # Check minimum ($2 USD) — fallback to hardcoded minimum if price API fails
    min_passed = False
    if amount_usd is not None and amount_usd >= 2.0:
        min_passed = True
    elif amount_usd is None:
        # Price API failed — check against hardcoded minimum
        fallback = _MIN_NATIVE_FALLBACK.get(req.chain)
        if fallback is not None:
            if req.chain == "btc":
                native = tx_info.get("value_sat", 0) / 1e8
            elif req.chain == "sol":
                native = tx_info.get("value_lamports", 0) / 1e9
            elif req.chain == "tron":
                native = tx_info.get("value_sun", 0) / 1e6
            else:
                native = tx_info.get("value_wei", 0) / 1e18
            if native >= fallback:
                min_passed = True

    if not min_passed:
        # Record unverified payment
        payment = CryptoPayment(
            user_id=current_user.id,
            chain=req.chain,
            tx_hash=req.tx_hash,
            amount_native=str(req.amount),
            amount_usd=amount_usd,
            verified=0,
        )
        db.add(payment)
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Payment amount (${amount_usd:.2f} USD) is below the $2.00 minimum"
            if amount_usd is not None
            else "Payment amount is below the $2.00 minimum",
        )

    # Record verified payment
    now = datetime.now(timezone.utc)
    payment = CryptoPayment(
        user_id=current_user.id,
        chain=req.chain,
        tx_hash=req.tx_hash,
        amount_native=str(req.amount),
        amount_usd=amount_usd,
        verified=1,
        verified_at=now,
    )
    db.add(payment)

    # Upgrade user to VIP for 1 year
    user = db.query(User).filter(User.id == current_user.id).first()
    user.subscription_tier = "vip"
    user.subscription_status = "active"
    user.subscription_started_at = now
    user.subscription_ends_at = now + timedelta(days=365)
    user.subscription_renews_at = user.subscription_ends_at
    user.is_pro = 1
    db.commit()

    _log_payment_event(
        db,
        provider="crypto",
        event_type="payment_verified",
        event_id=req.tx_hash,
        payload={"chain": req.chain, "amount_usd": amount_usd, "user_id": str(current_user.id)},
        user_id=str(current_user.id),
        status="processed",
    )

    return {
        "success": True,
        "message": "Payment verified and VIP activated for 1 year",
        "amount_usd": round(amount_usd, 2) if amount_usd is not None else None,
        "verified": True,
    }
