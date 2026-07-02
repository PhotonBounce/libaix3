"""OpsBrief — Celery application configuration and task definitions."""

from __future__ import annotations

from celery import Celery, crontab
from celery.signals import beat_init

from .config import settings
from .models import Base, Briefing, RawIntel, SessionLocal, User, engine
from .external.nvd_client import fetch_last_24h
from .services.llm_service import summarize_intel_items
from .services.scoring import score_for_user

celery_app = Celery(
    "opsbrief",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "opsbrief.celery_app",
        "opsbrief.tasks.fetch_intel",
        "opsbrief.tasks.generate_briefings",
        "opsbrief.tasks.data_retention",
    ],
)

celery_app.conf.update(
    beat_schedule={
        "run-intel-pipeline-daily": {
            "task": "opsbrief.celery_app.run_intel_pipeline",
            "schedule": crontab(hour=3, minute=0),  # 3:00 AM UTC daily
        },
        "purge-old-conversations-weekly": {
            "task": "opsbrief.tasks.data_retention.purge_old_conversations",
            "schedule": crontab(day_of_week=0, hour=4, minute=0),  # Sunday 4:00 AM UTC
        },
        "purge-old-briefings-weekly": {
            "task": "opsbrief.tasks.data_retention.purge_old_briefings",
            "schedule": crontab(day_of_week=0, hour=4, minute=30),  # Sunday 4:30 AM UTC
        },
    },
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,
)


@beat_init.connect
def init_db(**kwargs):
    """Ensure tables exist before the beat scheduler starts."""
    Base.metadata.create_all(bind=engine)


@celery_app.task(ignore_result=True)
def run_intel_pipeline():
    """Wrapper that chains fetch_intel → generate_briefings."""
    fetch = celery_app.signature("opsbrief.tasks.fetch_intel.fetch_all_intel")
    gen = celery_app.signature("opsbrief.tasks.generate_briefings.generate_all_briefings")
    (fetch | gen).apply_async()
