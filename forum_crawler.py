"""
forum_crawler.py — Crawl free public forums and Q&A sites for knowledge.

Targets: StackExchange (ServerFault, SuperUser, NetworkEngineering),
Reddit public JSON API, and generic forum scraping via HTML parsing.
All sources are free, public, and respect rate limits.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

from file_processor import classify_domain, generate_qa_from_text

USER_AGENT = (
    "libaix-crawler/1.0 (educational neural network project; "
    "github.com/lindapot-art/libaix)"
)
EXTRA_KNOWLEDGE_DIR = Path("data/extra_knowledge")
FORUM_CONFIG_PATH = Path("data/forum_config.json")
CRAWL_DELAY = 2.0  # be polite to public APIs

_STRIP_HTML = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return unescape(_STRIP_HTML.sub("", text)).strip()


def _http_get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def _http_get_json(url: str, timeout: int = 30) -> dict:
    return json.loads(_http_get(url, timeout))


# ── StackExchange API (free, no key needed for 300 req/day) ──────────

STACK_SITES = {
    "serverfault": "serverfault.com",
    "superuser": "superuser.com",
    "networkengineering": "networkengineering.stackexchange.com",
    "security": "security.stackexchange.com",
    "unix": "unix.stackexchange.com",
}

SE_API = "https://api.stackexchange.com/2.3"


def crawl_stackexchange(
    query: str,
    site: str = "serverfault",
    max_questions: int = 15,
) -> list[dict[str, str]]:
    """Search StackExchange for answered questions on a topic."""
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    site_domain = STACK_SITES.get(site, site)

    # Search for questions
    params = urllib.parse.urlencode({
        "order": "desc",
        "sort": "relevance",
        "q": query,
        "site": site_domain,
        "filter": "withbody",
        "accepted": "True",
        "pagesize": str(min(max_questions, 30)),
    })
    url = f"{SE_API}/search/advanced?{params}"

    try:
        data = _http_get_json(url)
    except Exception:
        return entries

    time.sleep(CRAWL_DELAY)

    for item in data.get("items", [])[:max_questions]:
        title = _strip_html(item.get("title", ""))
        body = _strip_html(item.get("body", ""))
        if not title or not body:
            continue

        ql = title.lower()
        if ql in seen:
            continue
        seen.add(ql)

        # Question title → Question, accepted answer body → Answer
        domain = classify_domain(f"{title} {body}")
        answer_text = _truncate(body, 500)

        entries.append({
            "question": title if title.endswith("?") else f"{title}?",
            "answer": answer_text,
            "domain": domain,
            "source": f"stackexchange:{site}:{item.get('question_id', '')}",
        })

        # Also extract sub-QA from the body
        sub_entries = generate_qa_from_text(body)
        for se in sub_entries:
            sel = se["question"].lower()
            if sel not in seen:
                seen.add(sel)
                se["source"] = f"stackexchange:{site}:{item.get('question_id', '')}"
                entries.append(se)

    return entries


# ── Reddit public JSON API (no auth needed for public subreddits) ────

REDDIT_SUBREDDITS = [
    "networking", "netsec", "sysadmin", "homelab",
    "wifi", "cybersecurity", "ccna", "ITCareerQuestions",
]


def crawl_reddit(
    query: str,
    subreddit: str = "networking",
    max_posts: int = 15,
) -> list[dict[str, str]]:
    """Search a subreddit for informational posts."""
    entries: list[dict[str, str]] = []
    seen: set[str] = set()

    params = urllib.parse.urlencode({
        "q": query,
        "restrict_sr": "1",
        "sort": "relevance",
        "t": "all",
        "limit": str(min(max_posts, 25)),
    })
    url = f"https://www.reddit.com/r/{subreddit}/search.json?{params}"

    try:
        data = _http_get_json(url)
    except Exception:
        return entries

    time.sleep(CRAWL_DELAY)

    for child in data.get("data", {}).get("children", [])[:max_posts]:
        post = child.get("data", {})
        title = post.get("title", "").strip()
        selftext = post.get("selftext", "").strip()

        if not title or post.get("over_18") or post.get("quarantine"):
            continue
        if len(selftext) < 50:
            continue

        ql = title.lower()
        if ql in seen:
            continue
        seen.add(ql)

        domain = classify_domain(f"{title} {selftext}")
        answer_text = _truncate(selftext, 500)

        question = title if title.endswith("?") else f"What is known about {title}?"
        entries.append({
            "question": question,
            "answer": answer_text,
            "domain": domain,
            "source": f"reddit:r/{subreddit}:{post.get('id', '')}",
        })

        sub_entries = generate_qa_from_text(selftext)
        for se in sub_entries:
            sel = se["question"].lower()
            if sel not in seen:
                seen.add(sel)
                se["source"] = f"reddit:r/{subreddit}"
                entries.append(se)

    return entries


# ── Combined forum crawl ─────────────────────────────────────────────

def crawl_forums(
    topic: str,
    keywords: list[str] | None = None,
    max_per_source: int = 10,
    sources: list[str] | None = None,
) -> list[dict[str, str]]:
    """Crawl multiple forum sources for a topic."""
    keywords = keywords or []
    all_entries: list[dict[str, str]] = []
    seen: set[str] = set()

    search_queries = [topic] + keywords[:3]
    enabled_sources = sources or ["stackexchange", "reddit"]

    for query in search_queries:
        # StackExchange sites
        if "stackexchange" in enabled_sources:
            for site in ["serverfault", "networkengineering", "security"]:
                try:
                    results = crawl_stackexchange(query, site, max_per_source)
                    for e in results:
                        ql = e["question"].lower()
                        if ql not in seen:
                            seen.add(ql)
                            all_entries.append(e)
                except Exception:
                    continue
                time.sleep(CRAWL_DELAY)

        # Reddit
        if "reddit" in enabled_sources:
            for sub in ["networking", "netsec", "sysadmin"]:
                try:
                    results = crawl_reddit(query, sub, max_per_source)
                    for e in results:
                        ql = e["question"].lower()
                        if ql not in seen:
                            seen.add(ql)
                            all_entries.append(e)
                except Exception:
                    continue
                time.sleep(CRAWL_DELAY)

    return all_entries


# ── Config management ────────────────────────────────────────────────

def load_forum_config() -> dict:
    if FORUM_CONFIG_PATH.exists():
        return json.loads(FORUM_CONFIG_PATH.read_text(encoding="utf-8"))
    return _default_forum_config()


def save_forum_config(config: dict) -> None:
    FORUM_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    FORUM_CONFIG_PATH.write_text(
        json.dumps(config, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _default_forum_config() -> dict:
    return {
        "topics": [
            {
                "name": "Wi-Fi Security",
                "keywords": ["WPA3", "802.1X", "wireless security"],
                "enabled": True,
                "max_per_source": 10,
                "sources": ["stackexchange", "reddit"],
            },
            {
                "name": "Network Troubleshooting",
                "keywords": ["packet loss", "latency", "DNS resolution"],
                "enabled": True,
                "max_per_source": 10,
                "sources": ["stackexchange", "reddit"],
            },
        ],
        "last_crawl": None,
        "stats": {},
    }


def save_forum_knowledge(entries: list[dict], topic_name: str) -> Path:
    EXTRA_KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w\-]", "_", topic_name.lower())
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fp = EXTRA_KNOWLEDGE_DIR / f"forum_{safe}_{ts}.json"
    fp.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return fp


def run_all_forum_crawlers() -> dict:
    """Run all enabled forum crawler topics."""
    config = load_forum_config()
    results: dict[str, dict] = {}
    total_new = 0

    for topic in config.get("topics", []):
        if not topic.get("enabled", True):
            results[topic["name"]] = {"status": "disabled", "entries": 0}
            continue
        try:
            entries = crawl_forums(
                topic["name"],
                topic.get("keywords", []),
                topic.get("max_per_source", 10),
                topic.get("sources", ["stackexchange", "reddit"]),
            )
            if entries:
                fp = save_forum_knowledge(entries, topic["name"])
                results[topic["name"]] = {
                    "status": "success",
                    "entries": len(entries),
                    "file": str(fp),
                }
                total_new += len(entries)
            else:
                results[topic["name"]] = {"status": "no_results", "entries": 0}
        except Exception as exc:
            results[topic["name"]] = {"status": f"error: {exc}", "entries": 0}

    # Update stats
    stats = config.get("stats", {})
    for name, result in results.items():
        if name not in stats:
            stats[name] = {"total_crawled": 0, "crawl_count": 0}
        stats[name]["total_crawled"] += result.get("entries", 0)
        stats[name]["crawl_count"] += 1
        stats[name]["last_crawl"] = datetime.now(timezone.utc).isoformat()

    config["last_crawl"] = datetime.now(timezone.utc).isoformat()
    config["stats"] = stats
    save_forum_config(config)

    return {"topics": results, "total_new_entries": total_new, "stats": stats}


def crawl_single_forum_topic(
    topic_name: str,
    keywords: list[str] | None = None,
    max_per_source: int = 10,
    sources: list[str] | None = None,
) -> dict:
    """One-shot forum crawl for a single topic."""
    entries = crawl_forums(topic_name, keywords, max_per_source, sources)
    if entries:
        fp = save_forum_knowledge(entries, topic_name)

        # Update stats
        config = load_forum_config()
        stats = config.get("stats", {})
        if topic_name not in stats:
            stats[topic_name] = {"total_crawled": 0, "crawl_count": 0}
        stats[topic_name]["total_crawled"] += len(entries)
        stats[topic_name]["crawl_count"] += 1
        stats[topic_name]["last_crawl"] = datetime.now(timezone.utc).isoformat()
        config["stats"] = stats
        save_forum_config(config)

        return {
            "status": "success",
            "entries": len(entries),
            "file": str(fp),
            "samples": entries[:3],
        }
    return {"status": "no_results", "entries": 0}


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text.strip()
    truncated = text[:max_len]
    last_period = truncated.rfind(".")
    if last_period > max_len // 3:
        return truncated[: last_period + 1].strip()
    return truncated.strip() + "."
