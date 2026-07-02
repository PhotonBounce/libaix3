"""OpsBrief — Celery task: data retention and cleanup.

Scheduled weekly to purge old conversations and briefings per
our data retention policy.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from ..celery_app import celery_app
from ..models import Briefing, Conversation, SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(ignore_result=True)
def purge_old_conversations() -> dict:
    """Delete Conversation rows older than 12 months."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=365)
        result = db.query(Conversation).filter(Conversation.created_at < cutoff).delete(
            synchronize_session=False
        )
        db.commit()
        logger.info(f"Purged {result} conversations older than 12 months")
        return {"purged": result, "table": "conversations", "cutoff_days": 365}
    except Exception:
        db.rollback()
        logger.exception("Failed to purge old conversations")
        raise
    finally:
        db.close()


@celery_app.task(ignore_result=True)
def purge_old_briefings() -> dict:
    """Delete Briefing rows older than 6 months."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=180)
        result = db.query(Briefing).filter(Briefing.created_at < cutoff).delete(
            synchronize_session=False
        )
        db.commit()
        logger.info(f"Purged {result} briefings older than 6 months")
        return {"purged": result, "table": "briefings", "cutoff_days": 180}
    except Exception:
        db.rollback()
        logger.exception("Failed to purge old briefings")
        raise
    finally:
        db.close()
