"""OpsBrief — Celery task: generate personalized daily briefings for all users.

Runs every night at 3 AM. Creates a briefing row per user with scored items.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from ..celery_app import celery_app
from ..models import Briefing, RawIntel, SessionLocal, User
from ..services.cache import cache
from ..services.llm_service import summarize_intel_items
from ..services.scoring import get_scorable_intel, score_for_user

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, ignore_result=True)
def generate_all_briefings(self, fetch_result=None) -> dict:
    """Generate daily briefings for every active user."""
    db = SessionLocal()
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        users = db.query(User).all()

        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        generated_count = 0

        for user in users:
            try:
                prefs = json.loads(user.preferences_json or "{}")

                # SQL-level pre-filter before Python scoring
                raw_items = get_scorable_intel(db, prefs, cutoff)

                # Score only the pre-filtered subset
                scored = []
                for item in raw_items:
                    score = score_for_user(item, prefs)
                    if score > 20.0:  # minimum relevance threshold
                        scored.append({"item": item, "score": score})

                if not scored:
                    continue

                # Sort by score descending, take top 10
                scored.sort(key=lambda x: x["score"], reverse=True)
                top = scored[:10]

                # AI summarization (batched for cost efficiency)
                summaries = summarize_intel_items([
                    {
                        "title": s["item"].title,
                        "summary": s["item"].summary,
                        "severity": s["item"].severity,
                    }
                    for s in top
                ])

                # Build briefing items JSON
                briefing_items = []
                for i, s in enumerate(top):
                    item = s["item"]
                    summary = summaries[i] if i < len(summaries) else {"headline": item.title, "summary": item.summary[:200]}
                    briefing_items.append({
                        "intel_id": str(item.id),
                        "source": item.source,
                        "source_id": item.source_id,
                        "headline": summary["headline"],
                        "summary": summary["summary"],
                        "severity": item.severity,
                        "cvss_score": item.cvss_score,
                        "url": item.url,
                        "relevance_score": round(s["score"], 1),
                        "published_at": item.published_at.isoformat() if item.published_at else None,
                    })

                # Upsert briefing for today
                existing = (
                    db.query(Briefing)
                    .filter(Briefing.user_id == user.id, Briefing.briefing_date == today)
                    .first()
                )
                if existing:
                    existing.items = json.dumps(briefing_items)
                    existing.item_count = len(briefing_items)
                    existing.is_ready = 1
                else:
                    briefing = Briefing(
                        user_id=user.id,
                        briefing_date=today,
                        items=json.dumps(briefing_items),
                        item_count=len(briefing_items),
                        is_ready=1,
                        is_read=0,
                    )
                    db.add(briefing)

                db.commit()
                # Invalidate stale cached briefing after successful commit
                cache.delete(f"briefing:{user.id}:{today}")
                generated_count += 1

            except Exception as e:
                logger.error(f"Failed to generate briefing for user {user.id}: {e}")
                db.rollback()
                continue

        logger.info(f"Generated {generated_count} briefings for {today}")
        return {"generated": generated_count, "date": today}

    except Exception as exc:
        logger.error(f"Briefing generation failed: {exc}")
        db.rollback()
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
