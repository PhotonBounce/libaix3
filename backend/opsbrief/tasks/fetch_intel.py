"""OpsBrief — Celery task: fetch intelligence from all sources.

Runs every 6 hours. Fetches from NVD (and later Cisco, GitHub, etc.),
deduplicates, and stores in the raw_intel table.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import or_, and_

from ..celery_app import celery_app
from ..config import settings
from ..models import RawIntel, SessionLocal
from ..external.nvd_client import fetch_last_24h as nvd_fetch_last_24h
from ..external.github_advisories import fetch_last_24h as github_fetch_last_24h
from ..external.cisco_psirt import fetch_last_24h as cisco_fetch_last_24h

logger = logging.getLogger(__name__)


def _store_items(db, items: list[dict]) -> tuple[int, int]:
    """Insert a list of normalized items into raw_intel, skipping duplicates.
    Returns (inserted_count, skipped_count)."""
    if not items:
        return 0, 0

    # Bulk lookup: batched queries to stay under SQLite's 999 parameter limit.
    # Each item uses 2 parameters (source + source_id), so chunk at 200 items = 400 params.
    existing_set = set()
    keys = [(item["source"], item["source_id"]) for item in items]
    chunk_size = 200
    for i in range(0, len(keys), chunk_size):
        chunk = keys[i:i + chunk_size]
        conditions = [and_(RawIntel.source == s, RawIntel.source_id == sid) for s, sid in chunk]
        existing_rows = db.query(RawIntel).filter(or_(*conditions)).all()
        existing_set.update({(r.source, r.source_id) for r in existing_rows})

    inserted = 0
    skipped = 0
    for item in items:
        if (item["source"], item["source_id"]) in existing_set:
            skipped += 1
            continue

        intel = RawIntel(
            source=item["source"],
            source_id=item["source_id"],
            title=item["title"],
            summary=item["summary"],
            url=item.get("url"),
            severity=item.get("severity", "info"),
            cvss_score=item.get("cvss_score"),
            affected_products=json.dumps(item.get("affected_products", [])),
            published_at=item.get("published_at"),
        )
        db.add(intel)
        inserted += 1
    return inserted, skipped


@celery_app.task(bind=True, max_retries=3, ignore_result=True)
def fetch_all_intel(self) -> dict:
    """Fetch from all configured sources and store in raw_intel.

    Returns a per-source breakdown:
        {
            "nvd": {"inserted": X, "skipped": Y},
            "github": {"inserted": X, "skipped": Y},
            "cisco": {"inserted": X, "skipped": Y},
        }
    """
    import asyncio

    # Map of source name -> async fetch callable
    fetchers = {
        "nvd": nvd_fetch_last_24h,
        "github": github_fetch_last_24h,
        "cisco": cisco_fetch_last_24h,
    }

    # Fetch all sources in parallel FIRST (close HTTP clients before opening DB)
    tasks = [fetcher() for fetcher in fetchers.values()]
    fetched_results = asyncio.run(asyncio.gather(*tasks, return_exceptions=True))

    results = {}

    db = SessionLocal()
    try:
        for source_name, result in zip(fetchers.keys(), fetched_results):
            if isinstance(result, Exception):
                logger.error(f"{source_name.upper()} fetch failed: {result}")
                results[source_name] = {"inserted": 0, "skipped": 0, "error": str(result)}
                continue

            # Safety net: cap at MAX_ITEMS_PER_SOURCE
            if len(result) > settings.MAX_ITEMS_PER_SOURCE:
                logger.warning(f"{source_name.upper()} capped at {settings.MAX_ITEMS_PER_SOURCE} items")
                result = result[:settings.MAX_ITEMS_PER_SOURCE]

            inserted, skipped = _store_items(db, result)
            results[source_name] = {"inserted": inserted, "skipped": skipped}
            logger.info(f"{source_name.upper()}: inserted={inserted}, skipped={skipped}")

        db.commit()

        total_inserted = sum(r.get("inserted", 0) for r in results.values())
        total_skipped = sum(r.get("skipped", 0) for r in results.values())
        logger.info(f"Fetch complete: {total_inserted} new items, {total_skipped} duplicates")
        return results
    except Exception as exc:
        logger.error(f"Fetch failed: {exc}")
        db.rollback()
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
