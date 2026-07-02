"""OpsBrief — NVD (National Vulnerability Database) API client.

Fetches CVE data from the NVD API v2 and normalizes it into our RawIntel
schema. No scraping. Official API only.

Docs: https://nvd.nist.gov/developers/vulnerabilities
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_API_KEY = settings.NVD_API_KEY

HEADERS = {}
if NVD_API_KEY:
    HEADERS["apiKey"] = NVD_API_KEY


async def fetch_recent_cves(days: int = 1) -> list[dict]:
    """Fetch CVEs published in the last N days."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    # NVD expects ISO-8601 format with timezone
    start_str = start.strftime("%Y-%m-%dT%H:%M:%S.000") + "+00:00"
    end_str = end.strftime("%Y-%m-%dT%H:%M:%S.000") + "+00:00"

    params = {
        "pubStartDate": start_str,
        "pubEndDate": end_str,
        "resultsPerPage": 100,
        "startIndex": 0,
    }

    all_items: list[dict] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            try:
                resp = await client.get(NVD_API_BASE, params=params, headers=HEADERS)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"NVD API request failed: {e}")
                break

            vulnerabilities = data.get("vulnerabilities", [])
            if not vulnerabilities:
                break

            for v in vulnerabilities:
                cve = v.get("cve", {})
                item = _normalize_cve(cve)
                if item:
                    all_items.append(item)

            if len(all_items) >= settings.MAX_ITEMS_PER_SOURCE:
                logger.warning(f"NVD capped at {settings.MAX_ITEMS_PER_SOURCE} items")
                break

            total = data.get("totalResults", 0)
            if len(all_items) >= total:
                break

            params["startIndex"] += params["resultsPerPage"]
            if params["startIndex"] >= total:
                break

    logger.info(f"Fetched {len(all_items)} CVEs from NVD for the last {days} days")
    return all_items


def _normalize_cve(cve: dict) -> dict | None:
    """Convert NVD CVE JSON into our RawIntel schema."""
    cve_id = cve.get("id", "")
    if not cve_id:
        return None

    descriptions = cve.get("descriptions", [])
    en_desc = next((d.get("value", "") for d in descriptions if d.get("lang") == "en"), "")

    metrics = cve.get("metrics", {})
    cvss = None
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        if key in metrics and metrics[key]:
            cvss = metrics[key][0].get("cvssData", {})
            break

    cvss_score = cvss.get("baseScore") if cvss else None
    severity = cvss.get("baseSeverity", "info").lower() if cvss else "info"

    # Affected products (CPE strings)
    configurations = cve.get("configurations", [])
    products: list[str] = []
    for config in configurations:
        for node in config.get("nodes", []):
            for match in node.get("cpeMatch", []):
                criteria = match.get("criteria", "")
                if criteria:
                    products.append(criteria)

    published = cve.get("published", "")
    try:
        published_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        published_dt = None

    return {
        "source": "nvd",
        "source_id": cve_id,
        "title": f"CVE-{cve_id}: {en_desc[:80]}..." if len(en_desc) > 80 else f"CVE-{cve_id}: {en_desc}",
        "summary": en_desc,
        "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
        "severity": severity,
        "cvss_score": cvss_score,
        "affected_products": products[:10],  # limit
        "published_at": published_dt,
    }


async def fetch_last_24h() -> list[dict]:
    """Convenience wrapper for daily fetch."""
    return await fetch_recent_cves(days=1)
