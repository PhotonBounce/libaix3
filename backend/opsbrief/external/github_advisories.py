"""OpsBrief — GitHub Security Advisories API client.

Fetches security advisories from the GitHub API and normalizes them into our
RawIntel schema.

Docs: https://docs.github.com/en/rest/security-advisories/global-advisories
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com/advisories"
GITHUB_TOKEN = settings.GITHUB_TOKEN

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"


SEVERITY_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "moderate": "medium",
}


async def fetch_recent_advisories(days: int = 1) -> list[dict]:
    """Fetch GitHub security advisories published in the last N days."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    # GitHub API returns ISO 8601 timestamps; we filter client-side by updated
    # since the API does not support a published-since query param directly.
    # The 'updated' param filters advisories updated since a given date.
    # We use per_page=100 and iterate via Link headers.
    params: dict[str, Any] = {
        "per_page": 100,
        "page": 1,
    }

    all_items: list[dict] = []
    async with httpx.AsyncClient(timeout=30.0, headers=HEADERS) as client:
        while True:
            try:
                resp = await client.get(GITHUB_API_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"GitHub Advisories API request failed: {e}")
                break

            if not isinstance(data, list):
                logger.error(f"Unexpected GitHub API response shape: {type(data)}")
                break

            for advisory in data:
                published = advisory.get("published_at", "")
                try:
                    published_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    published_dt = None

                # Filter client-side to only advisories published in the requested window
                if published_dt and published_dt < start:
                    # As we paginate, older items may appear; we can't break here
                    # because the API order isn't strictly by published date.
                    # So we just skip and continue.
                    continue

                item = _normalize_advisory(advisory)
                if item:
                    all_items.append(item)

            if len(all_items) >= settings.MAX_ITEMS_PER_SOURCE:
                logger.warning(f"GitHub capped at {settings.MAX_ITEMS_PER_SOURCE} items")
                break

            # Handle pagination via Link header
            link_header = resp.headers.get("link", "")
            next_page = _parse_next_page(link_header)
            if not next_page:
                break
            params["page"] = next_page

    logger.info(f"Fetched {len(all_items)} advisories from GitHub for the last {days} days")
    return all_items


def _normalize_advisory(advisory: dict) -> dict | None:
    """Convert GitHub advisory JSON into our RawIntel schema."""
    ghsa_id = advisory.get("ghsa_id", "")
    if not ghsa_id:
        return None

    title = advisory.get("summary", "")
    summary = advisory.get("description", "")
    url = advisory.get("html_url", f"https://github.com/advisories/{ghsa_id}")

    # Severity handling: GitHub returns both 'severity' string and optional 'cvss' object
    raw_severity = advisory.get("severity", "").lower().strip()
    severity = SEVERITY_MAP.get(raw_severity, "info")

    cvss = advisory.get("cvss", {})
    cvss_score = cvss.get("score") if isinstance(cvss, dict) else None

    # If no cvss_score but we have a severity string, try to approximate a score
    # for downstream consumers that expect a numeric value.
    if cvss_score is None and severity in ("critical", "high", "medium", "low"):
        # Approximate mapping; kept as None to stay honest when source lacks data
        pass

    # Affected products: GitHub returns 'vulnerabilities' with package info
    affected_products: list[str] = []
    vulnerabilities = advisory.get("vulnerabilities", [])
    for vuln in vulnerabilities:
        package = vuln.get("package", {})
        ecosystem = package.get("ecosystem", "")
        name = package.get("name", "")
        if ecosystem and name:
            affected_products.append(f"{ecosystem}:{name}")
        elif name:
            affected_products.append(name)

    published = advisory.get("published_at", "")
    try:
        published_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        published_dt = None

    return {
        "source": "github",
        "source_id": str(ghsa_id),
        "title": title or f"GHSA-{ghsa_id}",
        "summary": summary,
        "url": url,
        "severity": severity,
        "cvss_score": cvss_score,
        "affected_products": affected_products[:10],
        "published_at": published_dt,
    }


def _parse_next_page(link_header: str) -> int | None:
    """Parse the GitHub Link header to find the next page number."""
    if not link_header:
        return None
    # Link header format: <url>; rel="next", <url>; rel="last"
    for part in link_header.split(","):
        section = part.strip()
        if 'rel="next"' in section:
            # Extract page number from URL query string
            url_part = section.split(";")[0].strip().strip("<>").strip()
            if "page=" in url_part:
                try:
                    import urllib.parse
                    parsed = urllib.parse.urlparse(url_part)
                    query = urllib.parse.parse_qs(parsed.query)
                    page_values = query.get("page")
                    if page_values:
                        return int(page_values[0])
                except (ValueError, ImportError):
                    pass
    return None


async def fetch_last_24h() -> list[dict]:
    """Convenience wrapper for daily fetch."""
    return await fetch_recent_advisories(days=1)
