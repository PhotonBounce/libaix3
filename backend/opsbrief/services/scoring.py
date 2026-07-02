"""OpsBrief — Relevance scoring algorithm.

Scores each raw intel item for a specific user based on their preferences.
"""

from __future__ import annotations

import json
from typing import Any

from ..models import RawIntel


# Keyword mapping for quick tech-stack matching
TECH_KEYWORDS = {
    "cisco": ["cisco", "ios", "ios-xe", "ios-xr", "asa", "firepower", "meraki"],
    "juniper": ["juniper", "junos", "srx", "mx", "ex", "qfx"],
    "paloalto": ["palo alto", "paloalto", "pan-os", "panos", "prisma"],
    "fortinet": ["fortinet", "fortigate", "fortios", "forti"],
    "aws": ["aws", "amazon", "ec2", "s3", "rds", "lambda", "eks"],
    "azure": ["azure", "microsoft", "entra", "active directory"],
    "gcp": ["gcp", "google cloud", "gke", "cloud run"],
    "kubernetes": ["kubernetes", "k8s", "kubectl", "helm", "etcd"],
    "docker": ["docker", "containerd", "oci"],
    "linux": ["linux", "ubuntu", "debian", "red hat", "centos", "fedora", "kernel"],
    "windows": ["windows", "microsoft", "iis", "active directory"],
    "python": ["python", "pip", "pypi"],
    "javascript": ["javascript", "node.js", "npm", "node"],
    "vmware": ["vmware", "esxi", "vsphere", "vcenter"],
}

SEVERITY_WEIGHTS = {
    "critical": 10.0,
    "high": 7.0,
    "medium": 4.0,
    "low": 1.0,
    "info": 0.0,
}


SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]


def get_scorable_intel(db, preferences: dict, cutoff: datetime | None = None) -> list[RawIntel]:
    """Return raw intel pre-filtered at the SQL level by severity and source.

    Filters to severities at or above the user's threshold, and to their
    selected sources (if any), before Python-level scoring.
    """
    from datetime import datetime
    severity_threshold = preferences.get("severity_threshold", "medium").lower()
    sources = set(s.lower() for s in preferences.get("sources", []))

    threshold_index = SEVERITY_ORDER.index(severity_threshold) if severity_threshold in SEVERITY_ORDER else 2
    allowed_severities = SEVERITY_ORDER[:threshold_index + 1]

    query = db.query(RawIntel).filter(RawIntel.severity.in_(allowed_severities))
    if sources:
        query = query.filter(RawIntel.source.in_(sources))
    if cutoff is not None:
        query = query.filter(RawIntel.fetched_at >= cutoff)
    return query.all()


def score_for_user(intel: RawIntel, preferences: dict) -> float:
    """Return a relevance score (0–100) for an intel item against user preferences."""
    tech_stack = set(t.lower() for t in preferences.get("tech_stack", []))
    severity_threshold = preferences.get("severity_threshold", "medium").lower()
    sources = set(s.lower() for s in preferences.get("sources", []))

    score = 0.0

    # 1. Tech stack match (0–60 points)
    text = f"{intel.title} {intel.summary} {intel.affected_products or ''}".lower()
    matched = 0
    for tech in tech_stack:
        keywords = TECH_KEYWORDS.get(tech, [tech])
        if any(kw in text for kw in keywords):
            matched += 1
    score += (matched / max(len(tech_stack), 1)) * 60.0

    # 2. Severity (0–30 points)
    severity = (intel.severity or "info").lower()
    sev_score = SEVERITY_WEIGHTS.get(severity, 0.0)
    score += (sev_score / 10.0) * 30.0

    # 3. Source match (0–10 points)
    if not sources or (intel.source or "").lower() in sources:
        score += 10.0

    return min(score, 100.0)
