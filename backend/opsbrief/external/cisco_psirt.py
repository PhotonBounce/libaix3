"""OpsBrief — Cisco PSIRT RSS feed client.

Fetches security advisories from Cisco's public RSS feed and normalizes them
into our RawIntel schema.

Feed URL: https://tools.cisco.com/security/center/psirtrss20/CiscoSecurityAdvisory.xml
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser
import httpx

logger = logging.getLogger(__name__)

CISCO_RSS_URL = "https://tools.cisco.com/security/center/psirtrss20/CiscoSecurityAdvisory.xml"

# Keywords used to infer severity from advisory titles
SEVERITY_KEYWORDS = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "moderate": "medium",
    "low": "low",
}


async def fetch_recent_advisories(days: int = 1) -> list[dict]:
    """Fetch Cisco security advisories from RSS feed published in the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(CISCO_RSS_URL)
            resp.raise_for_status()
            feed_content = resp.text
    except Exception as e:
        logger.error(f"Cisco RSS feed request failed: {e}")
        return []

    # feedparser can parse from string
    parsed = feedparser.parse(feed_content)
    if parsed.bozo:
        logger.warning(f"Cisco RSS feed parse warning: {parsed.get('bozo_exception', 'unknown')}")

    all_items: list[dict] = []
    for entry in parsed.entries:
        item = _normalize_entry(entry)
        if not item:
            continue

        published_dt = item.get("published_at")
        if published_dt and published_dt < cutoff:
            continue

        all_items.append(item)

    logger.info(f"Fetched {len(all_items)} advisories from Cisco RSS for the last {days} days")
    return all_items


def _normalize_entry(entry: Any) -> dict | None:
    """Convert a feedparser entry into our RawIntel schema."""
    title = entry.get("title", "")
    if not title:
        return None

    summary = entry.get("summary", entry.get("description", ""))
    link = entry.get("link", "")

    # Use link as source_id if available, otherwise hash the title
    source_id = link if link else hashlib.sha256(title.encode()).hexdigest()[:16]

    # Parse published date
    published_dt = None
    published_str = entry.get("published", "")
    if not published_str:
        published_str = entry.get("updated", "")
    if published_str:
        try:
            # feedparser often returns parsed time as a struct_time in .published_parsed
            parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
            if parsed_time:
                published_dt = datetime.fromtimestamp(time.mktime(parsed_time), tz=timezone.utc)
            else:
                # Fallback to dateutil-like parsing via datetime.strptime for common RSS formats
                for fmt in (
                    "%a, %d %b %Y %H:%M:%S %Z",
                    "%a, %d %b %Y %H:%M:%S %z",
                    "%Y-%m-%dT%H:%M:%S%z",
                    "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%d %H:%M:%S",
                ):
                    try:
                        published_dt = datetime.strptime(published_str, fmt)
                        if published_dt.tzinfo is None:
                            published_dt = published_dt.replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue
        except Exception as e:
            logger.debug(f"Could not parse Cisco RSS date '{published_str}': {e}")

    # Infer severity from title keywords
    severity = "info"
    title_lower = title.lower()
    for keyword, mapped in SEVERITY_KEYWORDS.items():
        if keyword in title_lower:
            severity = mapped
            break

    # Try to extract affected products from title
    # Cisco titles often look like: "Cisco IOS XR Software ..." or "Cisco Secure ..."
    affected_products: list[str] = []
    # Look for patterns like "Cisco <Product Name>" or "for <Product>"
    product_match = re.search(r"Cisco\s+([A-Z][A-Za-z0-9\s\-]+?)(?:\s+Software|\s+Advisory|\s+Security|$)", title)
    if product_match:
        product = product_match.group(1).strip()
        if product:
            affected_products.append(product)

    return {
        "source": "cisco",
        "source_id": source_id,
        "title": title,
        "summary": summary,
        "url": link,
        "severity": severity,
        "cvss_score": None,  # RSS feed does not provide CVSS scores
        "affected_products": affected_products,
        "published_at": published_dt,
    }


async def fetch_last_24h() -> list[dict]:
    """Convenience wrapper for daily fetch."""
    return await fetch_recent_advisories(days=1)
