"""Decision Intelligence product side-path for AI Intelligence Factory.

This module is intentionally isolated from the article persistence state machine.
It owns Technology Intelligence DB / Decision History DB schema checks, entity
identity, current-state upsert, and append-only history.  It must never redefine
legacy Decision Score / Status semantics.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

logger = logging.getLogger(__name__)

NOTION_DECISION_INTELLIGENCE_API_KEY = os.environ.get("NOTION_DECISION_INTELLIGENCE_API_KEY", "").strip()
NOTION_API_VERSION = os.environ.get("NOTION_API_VERSION", "2026-03-11")
ENABLE_DECISION_INTELLIGENCE_DB = os.environ.get(
    "ENABLE_DECISION_INTELLIGENCE_DB", "false"
).lower() in {"1", "true", "yes", "on"}

NOTION_TECH_DATABASE_ID = os.environ.get("NOTION_TECH_DATABASE_ID", "").strip()
NOTION_TECH_DATA_SOURCE_ID = os.environ.get("NOTION_TECH_DATA_SOURCE_ID", "").strip()
NOTION_HISTORY_DATABASE_ID = os.environ.get("NOTION_HISTORY_DATABASE_ID", "").strip()
NOTION_HISTORY_DATA_SOURCE_ID = os.environ.get("NOTION_HISTORY_DATA_SOURCE_ID", "").strip()

NOTION_SUBSCRIBER_TECH_DATABASE_ID = os.environ.get("NOTION_SUBSCRIBER_TECH_DATABASE_ID", "").strip()
NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID = os.environ.get("NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID", "").strip()
NOTION_MONTHLY_DATABASE_ID = os.environ.get("NOTION_MONTHLY_DATABASE_ID", "").strip()
NOTION_MONTHLY_DATA_SOURCE_ID = os.environ.get("NOTION_MONTHLY_DATA_SOURCE_ID", "").strip()
ENABLE_SUBSCRIBER_TECH_SYNC = os.environ.get("ENABLE_SUBSCRIBER_TECH_SYNC", "false").lower() in {"1", "true", "yes", "on"}
ENABLE_DECISION_MONTHLY_DIGEST = os.environ.get("ENABLE_DECISION_MONTHLY_DIGEST", "false").lower() in {"1", "true", "yes", "on"}

ENABLE_JAPANESE_DISPLAY_LABEL = os.environ.get("ENABLE_JAPANESE_DISPLAY_LABEL", "false").lower() == "true"

ADOPTION_STATUSES = {"WATCH", "TEST", "ADOPT", "AVOID"}
CONFIDENCE_LEVELS = {"LOW", "MEDIUM", "HIGH"}
READINESS_LEVELS = {"LOW", "MEDIUM", "HIGH"}
ENTITY_RESOLUTION_STATUSES = {"RESOLVED", "AMBIGUOUS", "LEGACY_PENDING"}
TRACKING_STATUSES = {"ACTIVE", "PAUSED", "ARCHIVED"}
ASSESSMENT_STATES = {"SCREENED", "ASSESSED", "LEGACY_PENDING", "HISTORY_PENDING"}
SNAPSHOT_TYPES = {"INITIAL", "CHANGE", "PERIODIC", "MIGRATION"}

MEANINGFUL_SCORE_DELTA = max(1, int(os.environ.get("DI_MEANINGFUL_SCORE_DELTA", "5")))
STATUS_HYSTERESIS_SCORE_DELTA = max(0, int(os.environ.get("DI_STATUS_HYSTERESIS_SCORE_DELTA", "3")))
RISK_TEXT_SIMILARITY_THRESHOLD = min(0.99, max(0.50, float(os.environ.get("DI_RISK_TEXT_SIMILARITY_THRESHOLD", "0.82"))))
PRODUCT_TIMEZONE = os.environ.get("DI_PRODUCT_TIMEZONE", "Asia/Tokyo")

TECH_PROP_NAME = "Technology / Project Name"
TECH_PROP_JAPANESE_DISPLAY_LABEL = "Japanese Display Label"
TECH_PROP_PRIMARY_URL = "Primary URL"
TECH_PROP_SOURCE = "Source"
TECH_PROP_CATEGORY = "Category"
TECH_PROP_ADOPTION_SCORE = "Adoption Score"
TECH_PROP_ADOPTION_STATUS = "Adoption Status"
TECH_PROP_EVIDENCE_CONFIDENCE = "Evidence Confidence"
TECH_PROP_PRODUCTION_READINESS = "Production Readiness"
TECH_PROP_MAIN_RISK = "Main Risk"
TECH_PROP_BEST_FOR = "Best For"
TECH_PROP_AVOID_FOR = "Avoid For"
TECH_PROP_SHORT_RATIONALE = "Short Rationale"
TECH_PROP_FIRST_SEEN = "First Seen"
TECH_PROP_LAST_REVIEWED = "Last Reviewed"
TECH_PROP_PREVIOUS_SCORE = "Previous Score"
TECH_PROP_SCORE_CHANGE = "Score Change"
TECH_PROP_LAST_CHANGE_AT = "Last Change At"
TECH_PROP_RELATED_ARTICLE = "Related Article"
TECH_PROP_EVIDENCE_URLS = "Primary Evidence URLs"
TECH_PROP_ENTITY_ID = "Canonical Entity ID"
TECH_PROP_ENTITY_STATUS = "Entity Resolution Status"
TECH_PROP_ENTITY_ALIASES = "Entity Aliases"
TECH_PROP_TRACKING_STATUS = "Tracking Status"
TECH_PROP_TRACKING_ELIGIBILITY = "Tracking Eligibility"
TECH_PROP_TRACKING_REASON = "Tracking Reason"
TECH_PROP_ASSESSMENT_STATE = "Assessment State"
TECH_PROP_LAST_EVIDENCE_UPDATE = "Last Evidence Update"
TECH_PROP_NEXT_REVIEW = "Next Review"
TECH_PROP_PIPELINE_STATUS = "Pipeline Status"
TECH_PROP_CONTENT_STATUS = "Content Status"
TECH_PROP_ARTICLE_STATUS = "Article Status"
TECH_PROP_SCREENING_SCORE = "Screening Score"
TECH_PROP_SCREENING_REASON = "Screening Reason"
TECH_PROP_SOURCE_SUMMARY = "Source Summary"
TECH_PROP_PUBLISHED_AT = "Published At"
TECH_PROP_ANALYZED_AT = "Analyzed At"

HISTORY_PROP_TITLE = "History Entry"
HISTORY_PROP_TECHNOLOGY = "Technology"
HISTORY_PROP_REVIEWED_AT = "Reviewed At"
HISTORY_PROP_ADOPTION_SCORE = "Adoption Score"
HISTORY_PROP_ADOPTION_STATUS = "Adoption Status"
HISTORY_PROP_PRODUCTION_READINESS = "Production Readiness"
HISTORY_PROP_EVIDENCE_CONFIDENCE = "Evidence Confidence"
HISTORY_PROP_MAIN_RISK = "Main Risk"
HISTORY_PROP_CHANGE_REASON = "Change Reason"
HISTORY_PROP_EVIDENCE_ADDED = "Evidence Added"
HISTORY_PROP_PREVIOUS_SCORE = "Previous Score"
HISTORY_PROP_SCORE_DELTA = "Score Delta"
HISTORY_PROP_PREVIOUS_STATUS = "Previous Adoption Status"
HISTORY_PROP_STATUS_CHANGED = "Status Changed"
HISTORY_PROP_SNAPSHOT_TYPE = "Snapshot Type"
HISTORY_PROP_ENTITY_ID = "Canonical Entity ID"
HISTORY_PROP_EVENT_ID = "History Event ID"

SUB_PROP_NAME = "Technology / Project Name"
SUB_PROP_JAPANESE_DISPLAY_LABEL = "Japanese Display Label"
SUB_PROP_PRIMARY_URL = "Primary URL"
SUB_PROP_SOURCE = "Source"
SUB_PROP_CATEGORY = "Category"
SUB_PROP_ADOPTION_SCORE = "Adoption Score"
SUB_PROP_ADOPTION_STATUS = "Adoption Status"
SUB_PROP_EVIDENCE_CONFIDENCE = "Evidence Confidence"
SUB_PROP_PRODUCTION_READINESS = "Production Readiness"
SUB_PROP_MAIN_RISK = "Main Risk"
SUB_PROP_BEST_FOR = "Best For"
SUB_PROP_AVOID_FOR = "Avoid For"
SUB_PROP_SHORT_RATIONALE = "Short Rationale"
SUB_PROP_FIRST_SEEN = "First Seen"
SUB_PROP_LAST_REVIEWED = "Last Reviewed"
SUB_PROP_SCORE_CHANGE = "Score Change"
SUB_PROP_RELATED_ARTICLE = "Related Article"
SUB_PROP_EVIDENCE_URLS = "Primary Evidence URLs"
SUB_PROP_ENTITY_ID = "Canonical Entity ID"

MONTHLY_PROP_TITLE = "Monthly Digest"
MONTHLY_PROP_PERIOD_ID = "Period ID"
MONTHLY_PROP_GENERATED_AT = "Generated At"
MONTHLY_PROP_CHANGE_COUNT = "Change Count"
MONTHLY_PROP_SUMMARY = "Summary"

TECH_REQUIRED_PROPERTY_TYPES = {
    TECH_PROP_NAME: "title",
    TECH_PROP_PRIMARY_URL: "url",
    TECH_PROP_SOURCE: "multi_select",
    TECH_PROP_CATEGORY: "select",
    TECH_PROP_ADOPTION_SCORE: "number",
    TECH_PROP_ADOPTION_STATUS: "select",
    TECH_PROP_EVIDENCE_CONFIDENCE: "select",
    TECH_PROP_PRODUCTION_READINESS: "select",
    TECH_PROP_MAIN_RISK: "rich_text",
    TECH_PROP_BEST_FOR: "rich_text",
    TECH_PROP_AVOID_FOR: "rich_text",
    TECH_PROP_SHORT_RATIONALE: "rich_text",
    TECH_PROP_FIRST_SEEN: "date",
    TECH_PROP_LAST_REVIEWED: "date",
    TECH_PROP_PREVIOUS_SCORE: "number",
    TECH_PROP_SCORE_CHANGE: "number",
    TECH_PROP_LAST_CHANGE_AT: "date",
    TECH_PROP_RELATED_ARTICLE: "url",
    TECH_PROP_EVIDENCE_URLS: "rich_text",
    TECH_PROP_ENTITY_ID: "rich_text",
    TECH_PROP_ENTITY_STATUS: "select",
    TECH_PROP_ENTITY_ALIASES: "rich_text",
    TECH_PROP_TRACKING_STATUS: "select",
    TECH_PROP_TRACKING_ELIGIBILITY: "checkbox",
    TECH_PROP_TRACKING_REASON: "rich_text",
    TECH_PROP_ASSESSMENT_STATE: "select",
    TECH_PROP_LAST_EVIDENCE_UPDATE: "date",
    TECH_PROP_NEXT_REVIEW: "date",
    TECH_PROP_PIPELINE_STATUS: "select",
    TECH_PROP_CONTENT_STATUS: "select",
    TECH_PROP_ARTICLE_STATUS: "select",
    TECH_PROP_SCREENING_SCORE: "number",
    TECH_PROP_SCREENING_REASON: "rich_text",
    TECH_PROP_SOURCE_SUMMARY: "rich_text",
    TECH_PROP_PUBLISHED_AT: "date",
    TECH_PROP_ANALYZED_AT: "date",
}

HISTORY_REQUIRED_PROPERTY_TYPES = {
    HISTORY_PROP_TITLE: "title",
    HISTORY_PROP_TECHNOLOGY: "relation",
    HISTORY_PROP_REVIEWED_AT: "date",
    HISTORY_PROP_ADOPTION_SCORE: "number",
    HISTORY_PROP_ADOPTION_STATUS: "select",
    HISTORY_PROP_PRODUCTION_READINESS: "select",
    HISTORY_PROP_EVIDENCE_CONFIDENCE: "select",
    HISTORY_PROP_MAIN_RISK: "rich_text",
    HISTORY_PROP_CHANGE_REASON: "rich_text",
    HISTORY_PROP_EVIDENCE_ADDED: "rich_text",
    HISTORY_PROP_PREVIOUS_SCORE: "number",
    HISTORY_PROP_SCORE_DELTA: "number",
    HISTORY_PROP_PREVIOUS_STATUS: "select",
    HISTORY_PROP_STATUS_CHANGED: "checkbox",
    HISTORY_PROP_SNAPSHOT_TYPE: "select",
    HISTORY_PROP_ENTITY_ID: "rich_text",
    HISTORY_PROP_EVENT_ID: "rich_text",
}

SUBSCRIBER_REQUIRED_PROPERTY_TYPES = {
    SUB_PROP_NAME: "title", SUB_PROP_PRIMARY_URL: "url", SUB_PROP_SOURCE: "multi_select",
    SUB_PROP_CATEGORY: "select", SUB_PROP_ADOPTION_SCORE: "number", SUB_PROP_ADOPTION_STATUS: "select",
    SUB_PROP_EVIDENCE_CONFIDENCE: "select", SUB_PROP_PRODUCTION_READINESS: "select",
    SUB_PROP_MAIN_RISK: "rich_text", SUB_PROP_BEST_FOR: "rich_text", SUB_PROP_AVOID_FOR: "rich_text",
    SUB_PROP_SHORT_RATIONALE: "rich_text", SUB_PROP_FIRST_SEEN: "date", SUB_PROP_LAST_REVIEWED: "date",
    SUB_PROP_SCORE_CHANGE: "number", SUB_PROP_RELATED_ARTICLE: "url", SUB_PROP_EVIDENCE_URLS: "rich_text",
    SUB_PROP_ENTITY_ID: "rich_text",
}

MONTHLY_REQUIRED_PROPERTY_TYPES = {
    MONTHLY_PROP_TITLE: "title", MONTHLY_PROP_PERIOD_ID: "rich_text", MONTHLY_PROP_GENERATED_AT: "date",
    MONTHLY_PROP_CHANGE_COUNT: "number", MONTHLY_PROP_SUMMARY: "rich_text",
}


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_DECISION_INTELLIGENCE_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }


def _schema_url(data_source_id: str, database_id: str) -> str:
    if data_source_id:
        return f"https://api.notion.com/v1/data_sources/{data_source_id}"
    return f"https://api.notion.com/v1/databases/{database_id}"


def _query_url(data_source_id: str, database_id: str) -> str:
    if data_source_id:
        return f"https://api.notion.com/v1/data_sources/{data_source_id}/query"
    return f"https://api.notion.com/v1/databases/{database_id}/query"


def _parent(data_source_id: str, database_id: str) -> dict[str, str]:
    return {"data_source_id": data_source_id} if data_source_id else {"database_id": database_id}


def _validate_schema(properties: dict, expected: dict[str, str], label: str) -> None:
    missing = [name for name in expected if name not in properties]
    mismatched = []
    for name, expected_type in expected.items():
        actual = (properties.get(name) or {}).get("type")
        if actual and actual != expected_type:
            mismatched.append(f"{name}:{actual}!={expected_type}")
    if missing or mismatched:
        details = []
        if missing:
            details.append("missing=" + ", ".join(missing))
        if mismatched:
            details.append("type_mismatch=" + ", ".join(mismatched))
        raise ValueError(f"{label} schema incompatible: " + " / ".join(details))


def preflight_decision_intelligence_schema() -> None:
    """Validate both product DB schemas before any Gemini request when enabled."""
    if not ENABLE_DECISION_INTELLIGENCE_DB:
        return
    if not NOTION_DECISION_INTELLIGENCE_API_KEY:
        raise ValueError("Decision Intelligence DB有効時は NOTION_DECISION_INTELLIGENCE_API_KEY が必要です。")
    if not (NOTION_TECH_DATA_SOURCE_ID or NOTION_TECH_DATABASE_ID):
        raise ValueError("Decision Intelligence DB有効時は NOTION_TECH_DATA_SOURCE_ID または NOTION_TECH_DATABASE_ID が必要です。")
    if not (NOTION_HISTORY_DATA_SOURCE_ID or NOTION_HISTORY_DATABASE_ID):
        raise ValueError("Decision Intelligence DB有効時は NOTION_HISTORY_DATA_SOURCE_ID または NOTION_HISTORY_DATABASE_ID が必要です。")

    try:
        tech = requests.get(
            _schema_url(NOTION_TECH_DATA_SOURCE_ID, NOTION_TECH_DATABASE_ID),
            headers=_headers(), timeout=15,
        )
        tech.raise_for_status()
        history = requests.get(
            _schema_url(NOTION_HISTORY_DATA_SOURCE_ID, NOTION_HISTORY_DATABASE_ID),
            headers=_headers(), timeout=15,
        )
        history.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"Decision Intelligence Notion schema preflight failed: {exc}") from exc

    _validate_schema(tech.json().get("properties", {}), TECH_REQUIRED_PROPERTY_TYPES, "Technology Intelligence DB")
    _validate_schema(history.json().get("properties", {}), HISTORY_REQUIRED_PROPERTY_TYPES, "Decision History DB")
    if ENABLE_SUBSCRIBER_TECH_SYNC:
        if not (NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID or NOTION_SUBSCRIBER_TECH_DATABASE_ID):
            raise ValueError("Subscriber Technology sync enabled but destination DB is not configured")
        sub = requests.get(_schema_url(NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID, NOTION_SUBSCRIBER_TECH_DATABASE_ID), headers=_headers(), timeout=15)
        sub.raise_for_status()
        _validate_schema(sub.json().get("properties", {}), SUBSCRIBER_REQUIRED_PROPERTY_TYPES, "Subscriber Technology DB")
    if ENABLE_DECISION_MONTHLY_DIGEST:
        if not (NOTION_MONTHLY_DATA_SOURCE_ID or NOTION_MONTHLY_DATABASE_ID):
            raise ValueError("Decision Monthly Digest enabled but destination DB is not configured")
        monthly = requests.get(_schema_url(NOTION_MONTHLY_DATA_SOURCE_ID, NOTION_MONTHLY_DATABASE_ID), headers=_headers(), timeout=15)
        monthly.raise_for_status()
        _validate_schema(monthly.json().get("properties", {}), MONTHLY_REQUIRED_PROPERTY_TYPES, "Decision Monthly DB")
    logger.info(
        "[DECISION INTELLIGENCE PREFLIGHT OK] technology_properties=%d history_properties=%d",
        len(TECH_REQUIRED_PROPERTY_TYPES), len(HISTORY_REQUIRED_PROPERTY_TYPES),
    )


_IGNORED_QUERY_PREFIXES = ("utm_",)
_IGNORED_QUERY_KEYS = {"fbclid", "gclid", "ref", "source"}


def canonicalize_identity_url(url: str) -> str:
    if not url:
        return ""
    p = urlparse(url.strip())
    scheme = (p.scheme or "https").lower()
    host = (p.netloc or "").lower()
    if scheme == "https" and host.endswith(":443"):
        host = host[:-4]
    if scheme == "http" and host.endswith(":80"):
        host = host[:-3]
    path = p.path.rstrip("/")
    if host in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
        m = re.fullmatch(r"/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?", path, re.I)
        if m:
            scheme, host, path = "https", "arxiv.org", f"/abs/{m.group(1)}"
    query = sorted(
        (k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
        if not k.lower().startswith(_IGNORED_QUERY_PREFIXES)
        and k.lower() not in _IGNORED_QUERY_KEYS
    )
    return urlunparse((scheme, host, path, "", urlencode(query, doseq=True), ""))


def _extract_arxiv_id(url: str) -> str:
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?", url or "", re.I)
    return m.group(1) if m else ""


def _github_repo_from_url(url: str) -> str:
    p = urlparse(url or "")
    if p.netloc.lower() not in {"github.com", "www.github.com"}:
        return ""
    parts = [x for x in p.path.split("/") if x]
    if len(parts) < 2:
        return ""
    owner, repo = parts[0], parts[1]
    if owner.lower() in {"features", "topics", "orgs", "marketplace", "settings"}:
        return ""
    if repo.endswith(".git"):
        repo = repo[:-4]
    return f"{owner}/{repo}" if owner and repo else ""


def _stable_legacy_id(seed: str) -> str:
    return "legacy:" + hashlib.sha256((seed or "unknown").encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class EntityResolution:
    entity_id: str
    status: str
    primary_url: str
    aliases: tuple[str, ...]
    reason: str


def resolve_canonical_entity_id(repo: dict, source_info: dict | None = None) -> EntityResolution:
    """Resolve a conservative technology identity without fuzzy-title merging."""
    source_info = source_info or {}
    details = dict(repo.get("sourceDetails") or {})
    raw_urls: list[str] = []
    for value in (
        source_info.get("primary_url"), repo.get("primaryUrl"), repo.get("url"),
        details.get("official_url"), details.get("website"), details.get("external_url"),
        details.get("project_url"), details.get("homepage"),
    ):
        if isinstance(value, str) and value.strip():
            raw_urls.append(value.strip())
    for row in source_info.get("evidence_documents", []) or []:
        value = (row or {}).get("url")
        if isinstance(value, str) and value.strip():
            raw_urls.append(value.strip())
    aliases = tuple(dict.fromkeys(canonicalize_identity_url(x) for x in raw_urls if canonicalize_identity_url(x)))

    for u in aliases:
        gh = _github_repo_from_url(u)
        if gh:
            return EntityResolution(f"github:{gh.lower()}", "RESOLVED", u, aliases, "official GitHub repository")
    name = str(repo.get("nameWithOwner") or "").strip()
    if repo.get("source") == "GitHub" and re.fullmatch(r"[^/\s]+/[^/\s]+", name):
        return EntityResolution(f"github:{name.lower()}", "RESOLVED", canonicalize_identity_url(repo.get("url") or ""), aliases, "GitHub owner/repo")

    for u in aliases:
        arxiv_id = _extract_arxiv_id(u)
        if arxiv_id:
            return EntityResolution(f"arxiv:{arxiv_id}", "RESOLVED", f"https://arxiv.org/abs/{arxiv_id}", aliases, "arXiv paper id")

    primary = aliases[0] if aliases else ""
    if primary:
        p = urlparse(primary)
        host = p.netloc.lower()
        path = p.path.rstrip("/")
        # A generic article/news/docs URL is not, by itself, a stable Technology identity.
        # Only root-like external project/product homepages are auto-resolved here.  Deeper
        # paths remain AMBIGUOUS unless a stronger GitHub/arXiv identity was found above.
        # This prevents the Decision Intelligence DB from reproducing the legacy article store.
        discovery_hosts = {"news.ycombinator.com", "www.producthunt.com", "producthunt.com"}
        root_like = path in {"", "/en", "/home", "/index.html"}
        if host not in discovery_hosts and root_like:
            return EntityResolution(f"web:{host}/".lower(), "RESOLVED", primary, aliases, "root-like official/external project URL")

    seed = "|".join([str(repo.get("source") or ""), name, str(repo.get("url") or "")])
    return EntityResolution(_stable_legacy_id(seed), "AMBIGUOUS", primary, aliases, "stable Technology/Project identity could not be resolved conservatively")


def _rich_text_value(prop: dict) -> str:
    items = prop.get("title") or prop.get("rich_text") or []
    return "".join(
        item.get("plain_text") or ((item.get("text") or {}).get("content")) or ""
        for item in items
    ).strip()


def _select_value(prop: dict) -> str:
    return ((prop or {}).get("select") or {}).get("name") or ""


def _multi_select_values(prop: dict) -> list[str]:
    return [x.get("name") for x in ((prop or {}).get("multi_select") or []) if x.get("name")]


def _date_value(prop: dict) -> str | None:
    return ((prop or {}).get("date") or {}).get("start")


def _number_value(prop: dict) -> float | int | None:
    return (prop or {}).get("number")


def _rt(text: Any) -> dict:
    value = str(text or "")[:2000]
    return {"rich_text": [{"text": {"content": value}}]} if value else {"rich_text": []}


def _title(text: Any) -> dict:
    return {"title": [{"text": {"content": str(text or "")[:2000]}}]}


def _date(value: str | None) -> dict:
    return {"date": {"start": value}} if value else {"date": None}


def _select(value: str | None) -> dict:
    return {"select": {"name": value}} if value else {"select": None}


def _number(value: int | float | None) -> dict:
    return {"number": value if value is not None else None}


def _normalize_compare_text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value or "").strip()).lower()


def get_technology_record_by_entity_id(entity_id: str) -> dict | None:
    if not ENABLE_DECISION_INTELLIGENCE_DB or not entity_id:
        return None
    payload = {
        "filter": {"property": TECH_PROP_ENTITY_ID, "rich_text": {"equals": entity_id}},
        "page_size": 2,
    }
    res = requests.post(
        _query_url(NOTION_TECH_DATA_SOURCE_ID, NOTION_TECH_DATABASE_ID),
        json=payload, headers=_headers(), timeout=10,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Technology query failed: HTTP {res.status_code} {res.text[:500]}")
    rows = res.json().get("results", [])
    if len(rows) > 1:
        raise RuntimeError(f"Canonical Entity ID collision: {entity_id} matched {len(rows)} records")
    return rows[0] if rows else None


def _current_state(page: dict | None) -> dict:
    if not page:
        return {}
    props = page.get("properties", {})
    return {
        "page_id": page.get("id"),
        "technology_name": _rich_text_value(props.get(TECH_PROP_NAME, {})),
        "japanese_display_label": _rich_text_value(props.get(TECH_PROP_JAPANESE_DISPLAY_LABEL, {})),
        "adoption_score": _number_value(props.get(TECH_PROP_ADOPTION_SCORE, {})),
        "adoption_status": _select_value(props.get(TECH_PROP_ADOPTION_STATUS, {})),
        "production_readiness": _select_value(props.get(TECH_PROP_PRODUCTION_READINESS, {})),
        "evidence_confidence": _select_value(props.get(TECH_PROP_EVIDENCE_CONFIDENCE, {})),
        "main_risk": _rich_text_value(props.get(TECH_PROP_MAIN_RISK, {})),
        "sources": sorted(set(_multi_select_values(props.get(TECH_PROP_SOURCE, {})))),
        "entity_aliases": [x.strip() for x in _rich_text_value(props.get(TECH_PROP_ENTITY_ALIASES, {})).splitlines() if x.strip()],
        "evidence_urls": sorted(set(x.strip() for x in _rich_text_value(props.get(TECH_PROP_EVIDENCE_URLS, {})).splitlines() if x.strip())),
        "first_seen": _date_value(props.get(TECH_PROP_FIRST_SEEN, {})),
        "last_reviewed": _date_value(props.get(TECH_PROP_LAST_REVIEWED, {})),
        "last_change_at": _date_value(props.get(TECH_PROP_LAST_CHANGE_AT, {})),
        "assessment_state": _select_value(props.get(TECH_PROP_ASSESSMENT_STATE, {})),
    }


def _build_technology_properties(assessment: dict, resolution: EntityResolution, current: dict | None = None) -> dict:
    current = current or {}
    score = int(assessment["adoption_score"])
    prev_score = current.get("adoption_score")
    score_delta = score - prev_score if prev_score is not None else None
    # Technology is a durable entity.  Re-evaluation must accumulate explicit source/evidence
    # aliases instead of overwriting previous signals with only the latest discovery path.
    sources = list(dict.fromkeys(
        [str(x) for x in (current.get("sources") or []) if x]
        + [str(x) for x in (assessment.get("sources") or []) if x]
    ))
    aliases = list(dict.fromkeys(
        [str(x) for x in (current.get("entity_aliases") or []) if x]
        + [str(x) for x in resolution.aliases if x]
    ))
    evidence_urls = list(dict.fromkeys(
        [str(x) for x in (current.get("evidence_urls") or []) if x]
        + [str(x) for x in (assessment.get("evidence_urls") or []) if x]
    ))
    changed = bool(assessment.get("meaningful_change"))
    first_seen = current.get("first_seen") or assessment.get("first_seen") or assessment.get("reviewed_at")

    props = {
        TECH_PROP_NAME: _title(assessment.get("technology_name")),
        TECH_PROP_PRIMARY_URL: {"url": resolution.primary_url or assessment.get("primary_url") or None},
        TECH_PROP_SOURCE: {"multi_select": [{"name": x} for x in sources]},
        TECH_PROP_CATEGORY: _select(assessment.get("category") or "OTHER"),
        TECH_PROP_ADOPTION_SCORE: _number(score),
        TECH_PROP_ADOPTION_STATUS: _select(assessment.get("adoption_status")),
        TECH_PROP_EVIDENCE_CONFIDENCE: _select(assessment.get("evidence_confidence")),
        TECH_PROP_PRODUCTION_READINESS: _select(assessment.get("production_readiness")),
        TECH_PROP_MAIN_RISK: _rt(assessment.get("main_risk")),
        TECH_PROP_BEST_FOR: _rt(assessment.get("best_for")),
        TECH_PROP_AVOID_FOR: _rt(assessment.get("avoid_for")),
        TECH_PROP_SHORT_RATIONALE: _rt(assessment.get("short_rationale")),
        TECH_PROP_FIRST_SEEN: _date(first_seen),
        TECH_PROP_LAST_REVIEWED: _date(assessment.get("reviewed_at")),
        TECH_PROP_PREVIOUS_SCORE: _number(prev_score),
        TECH_PROP_SCORE_CHANGE: _number(score_delta),
        TECH_PROP_LAST_CHANGE_AT: _date(assessment.get("reviewed_at") if changed else current.get("last_change_at")),
        TECH_PROP_RELATED_ARTICLE: {"url": assessment.get("related_article") or None},
        TECH_PROP_EVIDENCE_URLS: _rt("\n".join(evidence_urls)),
        TECH_PROP_ENTITY_ID: _rt(resolution.entity_id),
        TECH_PROP_ENTITY_STATUS: _select(resolution.status),
        TECH_PROP_ENTITY_ALIASES: _rt("\n".join(aliases)),
        TECH_PROP_TRACKING_STATUS: _select(assessment.get("tracking_status") or "ACTIVE"),
        TECH_PROP_TRACKING_ELIGIBILITY: {"checkbox": bool(assessment.get("tracking_eligibility", True))},
        TECH_PROP_TRACKING_REASON: _rt(assessment.get("tracking_reason") or "Deep Dive / Decision Assessment completed"),
        TECH_PROP_ASSESSMENT_STATE: _select(assessment.get("assessment_state") or "ASSESSED"),
        TECH_PROP_LAST_EVIDENCE_UPDATE: _date(assessment.get("reviewed_at") if assessment.get("evidence_added") else assessment.get("last_evidence_update")),
        TECH_PROP_NEXT_REVIEW: _date(assessment.get("next_review")),
        TECH_PROP_PIPELINE_STATUS: _select(assessment.get("pipeline_status")),
        TECH_PROP_CONTENT_STATUS: _select(assessment.get("content_status")),
        TECH_PROP_ARTICLE_STATUS: _select(assessment.get("article_status")),
        TECH_PROP_SCREENING_SCORE: _number(assessment.get("screening_score")),
        TECH_PROP_SCREENING_REASON: _rt(assessment.get("screening_reason")),
        TECH_PROP_SOURCE_SUMMARY: _rt(assessment.get("source_summary")),
        TECH_PROP_PUBLISHED_AT: _date(assessment.get("published_at")),
        TECH_PROP_ANALYZED_AT: _date(assessment.get("reviewed_at")),
    }
    display_label = str(assessment.get("japanese_display_label") or current.get("japanese_display_label") or "").strip()
    if ENABLE_JAPANESE_DISPLAY_LABEL and display_label:
        props[TECH_PROP_JAPANESE_DISPLAY_LABEL] = _rt(display_label)
    return props


def _risk_category(text: str) -> str:
    value = _normalize_compare_text(text)
    categories = (
        ("SECURITY", r"security|vulnerab|attack|漏洩|脆弱|攻撃|認証|権限|セキュリティ"),
        ("COMPATIBILITY", r"compatib|migration|breaking|互換|移行|依存|integration|統合"),
        ("COST", r"cost|price|billing|費用|価格|課金|コスト"),
        ("PERFORMANCE", r"latency|performance|throughput|速度|性能|遅延|メモリ|cpu|gpu"),
        ("MATURITY", r"maturity|preview|beta|experimental|未成熟|実験的|ベータ|安定性|production"),
        ("VENDOR", r"vendor|lock[- ]?in|provider|ベンダ|ロックイン|供給"),
        ("LEGAL", r"license|legal|compliance|privacy|ライセンス|法務|規制|個人情報"),
        ("OPERATIONS", r"operat|maintain|monitor|運用|保守|監視|障害"),
        ("DATA", r"data|dataset|quality|データ|品質|汚染"),
    )
    for category, pattern in categories:
        if re.search(pattern, value, re.I): return category
    return "OTHER"


def _risk_meaningfully_changed(old_risk: str, new_risk: str) -> bool:
    old_norm = _normalize_compare_text(old_risk); new_norm = _normalize_compare_text(new_risk)
    if not old_norm or not new_norm or old_norm == new_norm: return False
    old_cat, new_cat = _risk_category(old_norm), _risk_category(new_norm)
    if old_cat != "OTHER" and new_cat != "OTHER": return old_cat != new_cat
    return SequenceMatcher(None, old_norm, new_norm).ratio() < max(0.55, RISK_TEXT_SIMILARITY_THRESHOLD - 0.20)


def _apply_status_hysteresis(current: dict, assessment: dict) -> dict:
    adjusted = dict(assessment)
    old_score = current.get("adoption_score")
    old_status = current.get("adoption_status") or ""
    new_status = adjusted.get("adoption_status") or ""
    if (old_score is not None and {old_status, new_status} == {"WATCH", "TEST"}
            and abs(int(adjusted["adoption_score"]) - int(old_score)) < STATUS_HYSTERESIS_SCORE_DELTA):
        adjusted["adoption_status"] = old_status
        adjusted["status_hysteresis_applied"] = True
    return adjusted


def _diff_assessment(current: dict, assessment: dict) -> dict:
    old_score = current.get("adoption_score")
    new_score = int(assessment["adoption_score"])
    old_status = current.get("adoption_status") or ""
    new_status = assessment.get("adoption_status") or ""
    old_readiness = current.get("production_readiness") or ""
    old_conf = current.get("evidence_confidence") or ""
    old_risk = current.get("main_risk") or ""
    old_evidence = {canonicalize_identity_url(x) or x for x in current.get("evidence_urls", []) if x}
    new_evidence = {canonicalize_identity_url(x) or x for x in assessment.get("evidence_urls", []) if x}
    evidence_added = sorted(x for x in new_evidence - old_evidence if x)
    score_delta = (new_score - old_score) if old_score is not None else None
    changes: list[str] = []
    if score_delta is not None and abs(score_delta) >= MEANINGFUL_SCORE_DELTA:
        changes.append(f"Adoption Score {old_score}→{new_score}")
    if old_status and new_status != old_status:
        changes.append(f"Adoption Status {old_status}→{new_status}")
    if old_readiness and assessment.get("production_readiness") != old_readiness:
        changes.append(f"Production Readiness {old_readiness}→{assessment.get('production_readiness')}")
    if old_conf and assessment.get("evidence_confidence") != old_conf:
        changes.append(f"Evidence Confidence {old_conf}→{assessment.get('evidence_confidence')}")
    if old_risk and _risk_meaningfully_changed(old_risk, assessment.get("main_risk", "")):
        changes.append("Main Risk changed")
    if evidence_added:
        changes.append(f"Evidence +{len(evidence_added)}")
    return {
        "meaningful_change": bool(changes),
        "change_reason": "; ".join(changes) or "No meaningful decision change",
        "evidence_added": evidence_added,
        "previous_score": old_score,
        "score_delta": score_delta,
        "previous_status": old_status,
        "status_changed": bool(old_status and new_status != old_status),
        "previous_change_at": current.get("last_change_at") or "",
    }


def _history_event_id(assessment: dict, diff: dict, snapshot_type: str) -> str:
    """Stable event identity. INITIAL is unique per Technology; CHANGE is transition-idempotent."""
    entity_id = assessment.get("canonical_entity_id") or ""
    if snapshot_type == "INITIAL":
        # A Technology can have exactly one initial assessment. This remains stable even when
        # History succeeds but the current-state PATCH fails and the next Gemini assessment differs.
        payload = {"entity_id": entity_id, "snapshot_type": "INITIAL"}
    else:
        payload = {
            "entity_id": entity_id, "snapshot_type": snapshot_type,
            "previous_score": diff.get("previous_score"), "adoption_score": assessment.get("adoption_score"),
            "previous_status": diff.get("previous_status") or "",
            "transition_anchor": (diff.get("previous_change_at") or "") if snapshot_type == "CHANGE" else "",
            "adoption_status": assessment.get("adoption_status") or "",
            "production_readiness": assessment.get("production_readiness") or "",
            "evidence_confidence": assessment.get("evidence_confidence") or "",
            "main_risk": _normalize_compare_text(str(assessment.get("main_risk") or "")),
            "evidence_added": sorted(canonicalize_identity_url(x) or x for x in (diff.get("evidence_added") or []) if x),
        }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "dih-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:28]


def _get_history_by_event_id(event_id: str) -> dict | None:
    payload = {
        "filter": {"property": HISTORY_PROP_EVENT_ID, "rich_text": {"equals": event_id}},
        "page_size": 2,
    }
    res = requests.post(
        _query_url(NOTION_HISTORY_DATA_SOURCE_ID, NOTION_HISTORY_DATABASE_ID),
        json=payload, headers=_headers(), timeout=10,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Decision History event query failed: HTTP {res.status_code} {res.text[:500]}")
    rows = res.json().get("results", [])
    if len(rows) > 1:
        raise RuntimeError(f"History Event ID collision: {event_id} matched {len(rows)} records")
    return rows[0] if rows else None


def _append_history(tech_page_id: str, assessment: dict, diff: dict, snapshot_type: str) -> str:
    event_id = _history_event_id(assessment, diff, snapshot_type)
    existing = _get_history_by_event_id(event_id)
    if existing:
        return existing.get("id") or ""
    title = f"{assessment.get('technology_name', 'Technology')} — {assessment.get('reviewed_at', '')[:10]} — {snapshot_type}"
    props = {
        HISTORY_PROP_TITLE: _title(title),
        HISTORY_PROP_TECHNOLOGY: {"relation": [{"id": tech_page_id}]},
        HISTORY_PROP_REVIEWED_AT: _date(assessment.get("reviewed_at")),
        HISTORY_PROP_ADOPTION_SCORE: _number(int(assessment["adoption_score"])),
        HISTORY_PROP_ADOPTION_STATUS: _select(assessment.get("adoption_status")),
        HISTORY_PROP_PRODUCTION_READINESS: _select(assessment.get("production_readiness")),
        HISTORY_PROP_EVIDENCE_CONFIDENCE: _select(assessment.get("evidence_confidence")),
        HISTORY_PROP_MAIN_RISK: _rt(assessment.get("main_risk")),
        HISTORY_PROP_CHANGE_REASON: _rt(diff.get("change_reason") or ("Initial assessment" if snapshot_type == "INITIAL" else snapshot_type)),
        HISTORY_PROP_EVIDENCE_ADDED: _rt("\n".join(diff.get("evidence_added") or [])),
        HISTORY_PROP_PREVIOUS_SCORE: _number(diff.get("previous_score")),
        HISTORY_PROP_SCORE_DELTA: _number(diff.get("score_delta")),
        HISTORY_PROP_PREVIOUS_STATUS: _select(diff.get("previous_status") or None),
        HISTORY_PROP_STATUS_CHANGED: {"checkbox": bool(diff.get("status_changed"))},
        HISTORY_PROP_SNAPSHOT_TYPE: _select(snapshot_type),
        HISTORY_PROP_ENTITY_ID: _rt(assessment.get("canonical_entity_id")),
        HISTORY_PROP_EVENT_ID: _rt(event_id),
    }
    res = requests.post(
        "https://api.notion.com/v1/pages",
        json={"parent": _parent(NOTION_HISTORY_DATA_SOURCE_ID, NOTION_HISTORY_DATABASE_ID), "properties": props},
        headers=_headers(), timeout=10,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Decision History append failed: HTTP {res.status_code} {res.text[:500]}")
    return res.json().get("id") or ""


def upsert_technology_intelligence(assessment: dict, resolution: EntityResolution) -> dict:
    """Upsert current technology state and append history only for meaningful changes.

    Existing records use history-first ordering: append history, then patch current state.
    This avoids silently losing a decision transition.  New records must be created first so
    the History relation can reference them; a history failure never deletes that record.
    """
    if not ENABLE_DECISION_INTELLIGENCE_DB:
        return {"enabled": False, "saved": False, "reason": "disabled"}
    if resolution.status == "AMBIGUOUS":
        return {"enabled": True, "saved": False, "reason": "entity_ambiguous", "entity_id": resolution.entity_id}

    existing_page = get_technology_record_by_entity_id(resolution.entity_id)
    current = _current_state(existing_page)
    if existing_page and current.get("adoption_score") is not None:
        assessment = _apply_status_hysteresis(current, assessment)
    diff = _diff_assessment(current, assessment) if existing_page else {
        "meaningful_change": True,
        "change_reason": "Initial assessment",
        "evidence_added": list(assessment.get("evidence_urls") or []),
        "previous_score": None,
        "score_delta": None,
        "previous_status": "",
        "status_changed": False,
    }
    assessment = dict(assessment)
    assessment.update(diff)
    assessment["canonical_entity_id"] = resolution.entity_id

    if existing_page:
        # Recover an initial record whose current page was created but whose INITIAL History
        # transaction did not fully finish. Recovery must use the values already persisted in
        # the pending current record, not a newly generated assessment. Otherwise a changed
        # assessment on the next run could silently rewrite the meaning of the INITIAL snapshot.
        recovering_initial = current.get("assessment_state") == "HISTORY_PENDING"
        legacy_initial = (
            current.get("assessment_state") in {"LEGACY_PENDING", "SCREENED"}
            and current.get("adoption_score") is None
        )
        history_ids: list[str] = []
        if legacy_initial:
            initial_diff = {
                "meaningful_change": True,
                "change_reason": "Initial assessment",
                "evidence_added": list(assessment.get("evidence_urls") or []),
                "previous_score": None,
                "score_delta": None,
                "previous_status": "",
                "status_changed": False,
                "previous_change_at": "",
            }
            initial_history_id = _append_history(existing_page["id"], assessment, initial_diff, "INITIAL")
            if initial_history_id:
                history_ids.append(initial_history_id)
            assessment.update(initial_diff)
            assessment["assessment_state"] = "ASSESSED"
        elif recovering_initial:
            pending_initial_assessment = dict(assessment)
            pending_initial_assessment.update({
                "technology_name": current.get("technology_name") or assessment.get("technology_name"),
                "adoption_score": int(current.get("adoption_score")) if current.get("adoption_score") is not None else int(assessment["adoption_score"]),
                "adoption_status": current.get("adoption_status") or assessment.get("adoption_status"),
                "production_readiness": current.get("production_readiness") or assessment.get("production_readiness"),
                "evidence_confidence": current.get("evidence_confidence") or assessment.get("evidence_confidence"),
                "main_risk": current.get("main_risk") or assessment.get("main_risk"),
                "evidence_urls": list(current.get("evidence_urls") or assessment.get("evidence_urls") or []),
                "reviewed_at": current.get("last_reviewed") or current.get("last_change_at") or assessment.get("reviewed_at"),
                "canonical_entity_id": resolution.entity_id,
            })
            initial_diff = {
                "meaningful_change": True,
                "change_reason": "Initial assessment",
                "evidence_added": list(pending_initial_assessment.get("evidence_urls") or []),
                "previous_score": None,
                "score_delta": None,
                "previous_status": "",
                "status_changed": False,
                "previous_change_at": "",
            }
            initial_history_id = _append_history(
                existing_page["id"], pending_initial_assessment, initial_diff, "INITIAL"
            )
            if initial_history_id:
                history_ids.append(initial_history_id)

            # If the newly generated assessment changed while the INITIAL transaction was
            # pending, preserve that as a separate CHANGE event after the INITIAL snapshot.
            # _diff_assessment was computed against the pending current values above.
            if diff["meaningful_change"]:
                change_history_id = _append_history(existing_page["id"], assessment, diff, "CHANGE")
                if change_history_id:
                    history_ids.append(change_history_id)
            assessment["assessment_state"] = "ASSESSED"
        elif diff["meaningful_change"]:
            # Existing transitions are history-first. If the current patch fails, the next run
            # computes the same transition and reuses the same History Event ID rather than
            # appending a duplicate row. A later repeated transition gets a new id because the
            # previous Last Change At is included as the transition anchor.
            history_id = _append_history(existing_page["id"], assessment, diff, "CHANGE")
            if history_id:
                history_ids.append(history_id)
            assessment["assessment_state"] = "ASSESSED"
        else:
            assessment["assessment_state"] = "ASSESSED"

        props = _build_technology_properties(assessment, resolution, current)
        if (recovering_initial or legacy_initial) and not diff["meaningful_change"]:
            # The first assessment has no previous score. Only clear these fields when the
            # current assessment is the same as the pending initial one. If it changed, the
            # pending score is the legitimate previous value for the CHANGE event.
            props[TECH_PROP_PREVIOUS_SCORE] = _number(None)
            props[TECH_PROP_SCORE_CHANGE] = _number(None)
        res = requests.patch(
            f"https://api.notion.com/v1/pages/{existing_page['id']}",
            json={"properties": props}, headers=_headers(), timeout=10,
        )
        if res.status_code != 200:
            raise RuntimeError(
                f"Technology current-state patch failed after history={','.join(history_ids) or 'none'}: "
                f"HTTP {res.status_code} {res.text[:500]}"
            )
        return {
            "enabled": True, "saved": True, "created": False, "page_id": existing_page["id"],
            "history_id": history_ids[-1] if history_ids else "", "history_ids": history_ids,
            "changed": bool(diff["meaningful_change"] or recovering_initial or legacy_initial),
            "entity_id": resolution.entity_id, "history_recovered": recovering_initial,
        }

    # A new current record must exist before its History relation can be created. Mark it pending
    # until INITIAL History is durably present; a later run can then reconcile any partial failure.
    pending_assessment = dict(assessment)
    pending_assessment["assessment_state"] = "HISTORY_PENDING"
    props = _build_technology_properties(pending_assessment, resolution, {})
    res = requests.post(
        "https://api.notion.com/v1/pages",
        json={"parent": _parent(NOTION_TECH_DATA_SOURCE_ID, NOTION_TECH_DATABASE_ID), "properties": props},
        headers=_headers(), timeout=10,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Technology create failed: HTTP {res.status_code} {res.text[:500]}")
    page_id = res.json().get("id") or ""
    history_id = _append_history(page_id, assessment, diff, "INITIAL")
    finalize = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        json={"properties": {TECH_PROP_ASSESSMENT_STATE: _select("ASSESSED")}},
        headers=_headers(), timeout=10,
    )
    if finalize.status_code != 200:
        raise RuntimeError(
            f"Technology initial history committed but current finalization failed: "
            f"HTTP {finalize.status_code} {finalize.text[:500]}"
        )
    return {
        "enabled": True, "saved": True, "created": True, "page_id": page_id,
        "history_id": history_id, "changed": True, "entity_id": resolution.entity_id,
    }



def query_technology_records(filter_payload: dict | None = None, sorts: list[dict] | None = None,
                             max_records: int = 5000) -> list[dict]:
    """Read Technology DB with pagination. Fail closed instead of silently truncating product state."""
    if not ENABLE_DECISION_INTELLIGENCE_DB:
        return []
    payload: dict[str, Any] = {"page_size": 100}
    if filter_payload:
        payload["filter"] = filter_payload
    if sorts:
        payload["sorts"] = sorts
    rows: list[dict] = []
    while True:
        res = requests.post(_query_url(NOTION_TECH_DATA_SOURCE_ID, NOTION_TECH_DATABASE_ID),
                            json=payload, headers=_headers(), timeout=20)
        if res.status_code != 200:
            raise RuntimeError(f"Technology query failed: HTTP {res.status_code} {res.text[:500]}")
        body = res.json()
        rows.extend(body.get("results", []))
        if len(rows) > max_records:
            raise RuntimeError(f"Technology query exceeded safety limit {max_records}; refusing partial product state")
        if not body.get("has_more"):
            return rows
        cursor = body.get("next_cursor")
        if not cursor:
            raise RuntimeError("Technology query pagination inconsistent: has_more without next_cursor")
        payload["start_cursor"] = cursor


def query_history_records(filter_payload: dict | None = None, sorts: list[dict] | None = None,
                          max_records: int = 10000) -> list[dict]:
    """Read Decision History completely; never mark a monthly product complete on truncated data."""
    if not ENABLE_DECISION_INTELLIGENCE_DB:
        return []
    payload: dict[str, Any] = {"page_size": 100}
    if filter_payload:
        payload["filter"] = filter_payload
    if sorts:
        payload["sorts"] = sorts
    rows: list[dict] = []
    while True:
        res = requests.post(_query_url(NOTION_HISTORY_DATA_SOURCE_ID, NOTION_HISTORY_DATABASE_ID),
                            json=payload, headers=_headers(), timeout=20)
        if res.status_code != 200:
            raise RuntimeError(f"Decision History query failed: HTTP {res.status_code} {res.text[:500]}")
        body = res.json()
        rows.extend(body.get("results", []))
        if len(rows) > max_records:
            raise RuntimeError(f"Decision History query exceeded safety limit {max_records}; refusing truncated monthly digest")
        if not body.get("has_more"):
            return rows
        cursor = body.get("next_cursor")
        if not cursor:
            raise RuntimeError("Decision History pagination inconsistent: has_more without next_cursor")
        payload["start_cursor"] = cursor


def technology_page_to_state(page: dict) -> dict:
    """Public helper for Phase-2 review/sync code; preserves a single parser for product state."""
    state = _current_state(page)
    props = page.get("properties", {})
    state.update({
        "primary_url": (props.get(TECH_PROP_PRIMARY_URL) or {}).get("url") or "",
        "category": _select_value(props.get(TECH_PROP_CATEGORY, {})),
        "tracking_status": _select_value(props.get(TECH_PROP_TRACKING_STATUS, {})),
        "tracking_eligibility": bool((props.get(TECH_PROP_TRACKING_ELIGIBILITY) or {}).get("checkbox")),
        "tracking_reason": _rich_text_value(props.get(TECH_PROP_TRACKING_REASON, {})),
        "next_review": _date_value(props.get(TECH_PROP_NEXT_REVIEW, {})),
        "short_rationale": _rich_text_value(props.get(TECH_PROP_SHORT_RATIONALE, {})),
        "best_for": _rich_text_value(props.get(TECH_PROP_BEST_FOR, {})),
        "avoid_for": _rich_text_value(props.get(TECH_PROP_AVOID_FOR, {})),
        "related_article": (props.get(TECH_PROP_RELATED_ARTICLE) or {}).get("url") or "",
        "canonical_entity_id": _rich_text_value(props.get(TECH_PROP_ENTITY_ID, {})),
        "entity_status": _select_value(props.get(TECH_PROP_ENTITY_STATUS, {})),
        "screening_score": _number_value(props.get(TECH_PROP_SCREENING_SCORE, {})),
        "screening_reason": _rich_text_value(props.get(TECH_PROP_SCREENING_REASON, {})),
        "source_summary": _rich_text_value(props.get(TECH_PROP_SOURCE_SUMMARY, {})),
        "score_change": _number_value(props.get(TECH_PROP_SCORE_CHANGE, {})),
    })
    return state


def history_page_to_state(page: dict) -> dict:
    props = page.get("properties", {})
    return {
        "page_id": page.get("id"),
        "reviewed_at": _date_value(props.get(HISTORY_PROP_REVIEWED_AT, {})),
        "technology_name": _rich_text_value(props.get(HISTORY_PROP_TITLE, {})).split(" — ")[0],
        "adoption_score": _number_value(props.get(HISTORY_PROP_ADOPTION_SCORE, {})),
        "adoption_status": _select_value(props.get(HISTORY_PROP_ADOPTION_STATUS, {})),
        "production_readiness": _select_value(props.get(HISTORY_PROP_PRODUCTION_READINESS, {})),
        "evidence_confidence": _select_value(props.get(HISTORY_PROP_EVIDENCE_CONFIDENCE, {})),
        "main_risk": _rich_text_value(props.get(HISTORY_PROP_MAIN_RISK, {})),
        "change_reason": _rich_text_value(props.get(HISTORY_PROP_CHANGE_REASON, {})),
        "previous_score": _number_value(props.get(HISTORY_PROP_PREVIOUS_SCORE, {})),
        "score_delta": _number_value(props.get(HISTORY_PROP_SCORE_DELTA, {})),
        "previous_status": _select_value(props.get(HISTORY_PROP_PREVIOUS_STATUS, {})),
        "status_changed": bool((props.get(HISTORY_PROP_STATUS_CHANGED) or {}).get("checkbox")),
        "snapshot_type": _select_value(props.get(HISTORY_PROP_SNAPSHOT_TYPE, {})),
        "canonical_entity_id": _rich_text_value(props.get(HISTORY_PROP_ENTITY_ID, {})),
        "event_id": _rich_text_value(props.get(HISTORY_PROP_EVENT_ID, {})),
    }


def upsert_tracking_seed(record: dict, resolution: EntityResolution) -> dict:
    """Create/update a SCREENED Technology candidate without inventing Adoption data/history."""
    if not ENABLE_DECISION_INTELLIGENCE_DB:
        return {"enabled": False, "saved": False, "reason": "disabled"}
    if resolution.status == "AMBIGUOUS":
        return {"enabled": True, "saved": False, "reason": "entity_ambiguous", "entity_id": resolution.entity_id}
    existing = get_technology_record_by_entity_id(resolution.entity_id)
    sources = list(dict.fromkeys(str(x) for x in (record.get("sources") or ([record.get("source")] if record.get("source") else [])) if x))
    aliases = list(dict.fromkeys(resolution.aliases))
    evidence_urls = list(dict.fromkeys(str(x) for x in (record.get("evidence_urls") or []) if x))
    if existing:
        current = _current_state(existing)
        # Never downgrade an assessed record back to SCREENED. Only enrich discovery/tracking metadata.
        props = existing.get("properties", {})
        merged_sources = list(dict.fromkeys(current.get("sources", []) + sources))
        merged_aliases = list(dict.fromkeys(current.get("entity_aliases", []) + aliases))
        merged_evidence = list(dict.fromkeys(current.get("evidence_urls", []) + evidence_urls))
        patch = {
            TECH_PROP_SOURCE: {"multi_select": [{"name": x} for x in merged_sources]},
            TECH_PROP_ENTITY_ALIASES: _rt("\n".join(merged_aliases)),
            TECH_PROP_EVIDENCE_URLS: _rt("\n".join(merged_evidence)),
            TECH_PROP_TRACKING_ELIGIBILITY: {"checkbox": bool(record.get("tracking_eligibility", True)) or bool((props.get(TECH_PROP_TRACKING_ELIGIBILITY) or {}).get("checkbox"))},
            TECH_PROP_TRACKING_REASON: _rt(record.get("tracking_reason") or _rich_text_value(props.get(TECH_PROP_TRACKING_REASON, {})) or "Screening tracking signal"),
            TECH_PROP_SCREENING_SCORE: _number(record.get("screening_score")),
            TECH_PROP_SCREENING_REASON: _rt(record.get("screening_reason")),
            TECH_PROP_SOURCE_SUMMARY: _rt(record.get("source_summary")),
            TECH_PROP_ANALYZED_AT: _date(record.get("analyzed_at")),
        }
        if current.get("assessment_state") in {"LEGACY_PENDING", "SCREENED", ""}:
            patch[TECH_PROP_ASSESSMENT_STATE] = _select(current.get("assessment_state") or "SCREENED")
            patch[TECH_PROP_TRACKING_STATUS] = _select("ACTIVE" if record.get("tracking_eligibility", True) else "PAUSED")
        res = requests.patch(f"https://api.notion.com/v1/pages/{existing['id']}", json={"properties": patch}, headers=_headers(), timeout=10)
        if res.status_code != 200:
            raise RuntimeError(f"Technology tracking seed patch failed: HTTP {res.status_code} {res.text[:500]}")
        return {"enabled": True, "saved": True, "created": False, "page_id": existing["id"], "entity_id": resolution.entity_id}

    props = {
        TECH_PROP_NAME: _title(record.get("name")),
        TECH_PROP_PRIMARY_URL: {"url": resolution.primary_url or record.get("url") or None},
        TECH_PROP_SOURCE: {"multi_select": [{"name": x} for x in sources]},
        TECH_PROP_CATEGORY: _select(record.get("category") or "OTHER"),
        TECH_PROP_FIRST_SEEN: _date(record.get("first_seen") or record.get("analyzed_at")),
        TECH_PROP_LAST_REVIEWED: _date(None),
        TECH_PROP_RELATED_ARTICLE: {"url": record.get("related_article") or None},
        TECH_PROP_EVIDENCE_URLS: _rt("\n".join(evidence_urls)),
        TECH_PROP_ENTITY_ID: _rt(resolution.entity_id),
        TECH_PROP_ENTITY_STATUS: _select(resolution.status),
        TECH_PROP_ENTITY_ALIASES: _rt("\n".join(aliases)),
        TECH_PROP_TRACKING_STATUS: _select("ACTIVE" if record.get("tracking_eligibility", True) else "PAUSED"),
        TECH_PROP_TRACKING_ELIGIBILITY: {"checkbox": bool(record.get("tracking_eligibility", True))},
        TECH_PROP_TRACKING_REASON: _rt(record.get("tracking_reason") or "Screening tracking signal"),
        TECH_PROP_ASSESSMENT_STATE: _select("SCREENED"),
        TECH_PROP_NEXT_REVIEW: _date(record.get("next_review")),
        TECH_PROP_PIPELINE_STATUS: _select(record.get("pipeline_status") or "Stocked"),
        TECH_PROP_CONTENT_STATUS: _select(record.get("content_status") or "Stocked"),
        TECH_PROP_ARTICLE_STATUS: _select(record.get("article_status") or "Not Planned"),
        TECH_PROP_SCREENING_SCORE: _number(record.get("screening_score")),
        TECH_PROP_SCREENING_REASON: _rt(record.get("screening_reason")),
        TECH_PROP_SOURCE_SUMMARY: _rt(record.get("source_summary")),
        TECH_PROP_PUBLISHED_AT: _date(record.get("published_at")),
        TECH_PROP_ANALYZED_AT: _date(record.get("analyzed_at")),
    }
    res = requests.post("https://api.notion.com/v1/pages", json={"parent": _parent(NOTION_TECH_DATA_SOURCE_ID, NOTION_TECH_DATABASE_ID), "properties": props}, headers=_headers(), timeout=10)
    if res.status_code != 200:
        raise RuntimeError(f"Technology tracking seed create failed: HTTP {res.status_code} {res.text[:500]}")
    return {"enabled": True, "saved": True, "created": True, "page_id": res.json().get("id") or "", "entity_id": resolution.entity_id}


def _query_external_db(data_source_id: str, database_id: str, payload: dict | None = None, max_records: int = 5000) -> list[dict]:
    body_payload = dict(payload or {})
    body_payload.setdefault("page_size", 100)
    rows: list[dict] = []
    while True:
        res = requests.post(_query_url(data_source_id, database_id), json=body_payload, headers=_headers(), timeout=20)
        if res.status_code != 200:
            raise RuntimeError(f"Notion product query failed: HTTP {res.status_code} {res.text[:500]}")
        body = res.json(); rows.extend(body.get("results", []))
        if len(rows) > max_records:
            raise RuntimeError(f"Notion product query exceeded safety limit {max_records}")
        if not body.get("has_more"):
            return rows
        cursor = body.get("next_cursor")
        if not cursor:
            raise RuntimeError("Notion product pagination inconsistent")
        body_payload["start_cursor"] = cursor


def _subscriber_values_from_internal(page: dict) -> dict:
    props = page.get("properties", {})
    return {
        "name": _rich_text_value(props.get(TECH_PROP_NAME, {})),
        "japanese_display_label": _rich_text_value(props.get(TECH_PROP_JAPANESE_DISPLAY_LABEL, {})),
        "primary_url": (props.get(TECH_PROP_PRIMARY_URL) or {}).get("url") or "",
        "sources": sorted(set(_multi_select_values(props.get(TECH_PROP_SOURCE, {})))),
        "category": _select_value(props.get(TECH_PROP_CATEGORY, {})),
        "adoption_score": _number_value(props.get(TECH_PROP_ADOPTION_SCORE, {})),
        "adoption_status": _select_value(props.get(TECH_PROP_ADOPTION_STATUS, {})),
        "evidence_confidence": _select_value(props.get(TECH_PROP_EVIDENCE_CONFIDENCE, {})),
        "production_readiness": _select_value(props.get(TECH_PROP_PRODUCTION_READINESS, {})),
        "main_risk": _rich_text_value(props.get(TECH_PROP_MAIN_RISK, {})),
        "best_for": _rich_text_value(props.get(TECH_PROP_BEST_FOR, {})),
        "avoid_for": _rich_text_value(props.get(TECH_PROP_AVOID_FOR, {})),
        "short_rationale": _rich_text_value(props.get(TECH_PROP_SHORT_RATIONALE, {})),
        "first_seen": _date_value(props.get(TECH_PROP_FIRST_SEEN, {})),
        "last_reviewed": _date_value(props.get(TECH_PROP_LAST_REVIEWED, {})),
        "score_change": _number_value(props.get(TECH_PROP_SCORE_CHANGE, {})),
        "related_article": (props.get(TECH_PROP_RELATED_ARTICLE) or {}).get("url") or "",
        "evidence_urls": sorted(set(x.strip() for x in _rich_text_value(props.get(TECH_PROP_EVIDENCE_URLS, {})).splitlines() if x.strip())),
        "entity_id": _rich_text_value(props.get(TECH_PROP_ENTITY_ID, {})),
        "assessment_state": _select_value(props.get(TECH_PROP_ASSESSMENT_STATE, {})),
        "tracking_eligibility": bool((props.get(TECH_PROP_TRACKING_ELIGIBILITY) or {}).get("checkbox")),
        "tracking_status": _select_value(props.get(TECH_PROP_TRACKING_STATUS, {})),
    }


def _subscriber_values_from_destination(page: dict) -> dict:
    p = page.get("properties", {})
    return {
        "name": _rich_text_value(p.get(SUB_PROP_NAME, {})), "japanese_display_label": _rich_text_value(p.get(SUB_PROP_JAPANESE_DISPLAY_LABEL, {})), "primary_url": (p.get(SUB_PROP_PRIMARY_URL) or {}).get("url") or "",
        "sources": sorted(set(_multi_select_values(p.get(SUB_PROP_SOURCE, {})))), "category": _select_value(p.get(SUB_PROP_CATEGORY, {})),
        "adoption_score": _number_value(p.get(SUB_PROP_ADOPTION_SCORE, {})), "adoption_status": _select_value(p.get(SUB_PROP_ADOPTION_STATUS, {})),
        "evidence_confidence": _select_value(p.get(SUB_PROP_EVIDENCE_CONFIDENCE, {})), "production_readiness": _select_value(p.get(SUB_PROP_PRODUCTION_READINESS, {})),
        "main_risk": _rich_text_value(p.get(SUB_PROP_MAIN_RISK, {})), "best_for": _rich_text_value(p.get(SUB_PROP_BEST_FOR, {})),
        "avoid_for": _rich_text_value(p.get(SUB_PROP_AVOID_FOR, {})), "short_rationale": _rich_text_value(p.get(SUB_PROP_SHORT_RATIONALE, {})),
        "first_seen": _date_value(p.get(SUB_PROP_FIRST_SEEN, {})), "last_reviewed": _date_value(p.get(SUB_PROP_LAST_REVIEWED, {})),
        "score_change": _number_value(p.get(SUB_PROP_SCORE_CHANGE, {})), "related_article": (p.get(SUB_PROP_RELATED_ARTICLE) or {}).get("url") or "",
        "evidence_urls": sorted(set(x.strip() for x in _rich_text_value(p.get(SUB_PROP_EVIDENCE_URLS, {})).splitlines() if x.strip())),
        "entity_id": _rich_text_value(p.get(SUB_PROP_ENTITY_ID, {})),
    }


def _subscriber_props(v: dict) -> dict:
    props = {
        SUB_PROP_NAME: _title(v.get("name")), SUB_PROP_PRIMARY_URL: {"url": v.get("primary_url") or None},
        SUB_PROP_SOURCE: {"multi_select": [{"name": x} for x in v.get("sources", [])]}, SUB_PROP_CATEGORY: _select(v.get("category") or "OTHER"),
        SUB_PROP_ADOPTION_SCORE: _number(v.get("adoption_score")), SUB_PROP_ADOPTION_STATUS: _select(v.get("adoption_status")),
        SUB_PROP_EVIDENCE_CONFIDENCE: _select(v.get("evidence_confidence")), SUB_PROP_PRODUCTION_READINESS: _select(v.get("production_readiness")),
        SUB_PROP_MAIN_RISK: _rt(v.get("main_risk")), SUB_PROP_BEST_FOR: _rt(v.get("best_for")), SUB_PROP_AVOID_FOR: _rt(v.get("avoid_for")),
        SUB_PROP_SHORT_RATIONALE: _rt(v.get("short_rationale")), SUB_PROP_FIRST_SEEN: _date(v.get("first_seen")),
        SUB_PROP_LAST_REVIEWED: _date(v.get("last_reviewed")), SUB_PROP_SCORE_CHANGE: _number(v.get("score_change")),
        SUB_PROP_RELATED_ARTICLE: {"url": v.get("related_article") or None}, SUB_PROP_EVIDENCE_URLS: _rt("\n".join(v.get("evidence_urls", []))),
        SUB_PROP_ENTITY_ID: _rt(v.get("entity_id")),
    }
    if ENABLE_JAPANESE_DISPLAY_LABEL:
        props[SUB_PROP_JAPANESE_DISPLAY_LABEL] = _rt(v.get("japanese_display_label"))
    return props


def sync_subscriber_technology_db() -> dict:
    """Copy only sanitized, assessed product data. Internal columns never cross the boundary."""
    if not ENABLE_SUBSCRIBER_TECH_SYNC:
        return {"enabled": False, "created": 0, "updated": 0, "archived": 0, "unchanged": 0}
    internal_pages = query_technology_records(max_records=5000)
    internal_by_id: dict[str, dict] = {}
    eligible: dict[str, dict] = {}
    for page in internal_pages:
        values = _subscriber_values_from_internal(page)
        entity_id = values.get("entity_id") or ""
        if not entity_id:
            continue
        if entity_id in internal_by_id:
            raise RuntimeError(f"Internal Technology Canonical Entity ID collision during subscriber sync: {entity_id}")
        internal_by_id[entity_id] = values
        if values.get("assessment_state") == "ASSESSED" and values.get("tracking_eligibility") and values.get("tracking_status") != "ARCHIVED":
            eligible[entity_id] = values
    destination = _query_external_db(NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID, NOTION_SUBSCRIBER_TECH_DATABASE_ID, max_records=5000)
    dest_by_id: dict[str, list[dict]] = {}
    for page in destination:
        eid = _rich_text_value((page.get("properties") or {}).get(SUB_PROP_ENTITY_ID, {}))
        if eid:
            dest_by_id.setdefault(eid, []).append(page)
    result = {"enabled": True, "created": 0, "updated": 0, "archived": 0, "unchanged": 0}
    for eid, values in eligible.items():
        pages = dest_by_id.get(eid, [])
        if pages:
            first = pages[0]
            if _subscriber_values_from_destination(first) != {k: values[k] for k in _subscriber_values_from_destination(first)}:
                res = requests.patch(f"https://api.notion.com/v1/pages/{first['id']}", json={"properties": _subscriber_props(values)}, headers=_headers(), timeout=20)
                if res.status_code != 200: raise RuntimeError(f"Subscriber Technology patch failed: {res.status_code} {res.text[:500]}")
                result["updated"] += 1
            else:
                result["unchanged"] += 1
            for dup in pages[1:]:
                res = requests.patch(f"https://api.notion.com/v1/pages/{dup['id']}", json={"archived": True}, headers=_headers(), timeout=20)
                if res.status_code != 200: raise RuntimeError("Subscriber duplicate archive failed")
                result["archived"] += 1
        else:
            res = requests.post("https://api.notion.com/v1/pages", json={"parent": _parent(NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID, NOTION_SUBSCRIBER_TECH_DATABASE_ID), "properties": _subscriber_props(values)}, headers=_headers(), timeout=20)
            if res.status_code != 200: raise RuntimeError(f"Subscriber Technology create failed: {res.status_code} {res.text[:500]}")
            result["created"] += 1
    # Archive only rows whose entity exists internally but is no longer subscriber-eligible. Unknown/manual rows are left untouched.
    for eid, pages in dest_by_id.items():
        if eid in internal_by_id and eid not in eligible:
            for page in pages:
                if page.get("archived"):
                    continue
                res = requests.patch(f"https://api.notion.com/v1/pages/{page['id']}", json={"archived": True}, headers=_headers(), timeout=20)
                if res.status_code != 200: raise RuntimeError("Subscriber revoke archive failed")
                result["archived"] += 1
    return result


def _month_bounds(period_id: str) -> tuple[str, str]:
    year, month = [int(x) for x in period_id.split("-", 1)]
    tz = ZoneInfo(PRODUCT_TIMEZONE)
    start_local = datetime(year, month, 1, tzinfo=tz)
    if month == 12: end_local = datetime(year + 1, 1, 1, tzinfo=tz)
    else: end_local = datetime(year, month + 1, 1, tzinfo=tz)
    return start_local.astimezone(timezone.utc).isoformat(), end_local.astimezone(timezone.utc).isoformat()


def _monthly_exists(period_id: str) -> bool:
    rows = _query_external_db(NOTION_MONTHLY_DATA_SOURCE_ID, NOTION_MONTHLY_DATABASE_ID, {
        "filter": {"property": MONTHLY_PROP_PERIOD_ID, "rich_text": {"equals": period_id}}, "page_size": 2,
    }, max_records=2)
    if len(rows) > 1: raise RuntimeError(f"Monthly Period ID collision: {period_id}")
    return bool(rows)


def _monthly_decision_priority(event: dict) -> tuple[int, float, int]:
    """Deterministic priority for a member-facing reconsideration brief; no new factual inference."""
    status = str(event.get("adoption_status") or "").upper()
    previous = str(event.get("previous_status") or "").upper()
    delta = float(event.get("score_delta") or 0)
    status_weight = {"AVOID": 5, "ADOPT": 4, "TEST": 3, "WATCH": 2}.get(status, 1)
    changed = 1 if event.get("status_changed") else 0
    # Status changes outrank score-only movement; larger absolute changes outrank noise.
    return (changed * 10 + status_weight, abs(delta), 1 if previous and previous != status else 0)


def _monthly_action_label(event: dict) -> str:
    status = str(event.get("adoption_status") or "").upper()
    return {
        "ADOPT": "導入判断を前へ進める候補",
        "TEST": "限定検証を検討する候補",
        "WATCH": "今は待ち、監視を続ける候補",
        "AVOID": "導入を見送る／再確認する候補",
    }.get(status, "再確認候補")


def build_monthly_decision_brief(events: list[dict], limit: int = 3) -> list[dict]:
    """Pick only meaningful existing history events; never invent new recommendations."""
    meaningful = [
        e for e in events
        if e.get("status_changed") or abs(float(e.get("score_delta") or 0)) >= MEANINGFUL_SCORE_DELTA
        or e.get("snapshot_type") == "INITIAL"
    ]
    ranked = sorted(meaningful, key=_monthly_decision_priority, reverse=True)
    return [dict(e, decision_label=_monthly_action_label(e)) for e in ranked[:max(0, limit)]]


def create_history_monthly_digest(period_id: str, generated_at: str | None = None) -> dict:
    if not ENABLE_DECISION_MONTHLY_DIGEST:
        return {"enabled": False, "created": False, "period_id": period_id}
    if _monthly_exists(period_id):
        return {"enabled": True, "created": False, "period_id": period_id, "reason": "exists"}
    start, end = _month_bounds(period_id)
    rows = query_history_records({"and": [
        {"property": HISTORY_PROP_REVIEWED_AT, "date": {"on_or_after": start}},
        {"property": HISTORY_PROP_REVIEWED_AT, "date": {"before": end}},
    ]}, sorts=[{"property": HISTORY_PROP_REVIEWED_AT, "direction": "ascending"}], max_records=10000)
    events = [history_page_to_state(x) for x in rows]
    status_changes = [e for e in events if e.get("status_changed")]
    rises = sorted([e for e in events if (e.get("score_delta") or 0) >= MEANINGFUL_SCORE_DELTA], key=lambda e: e.get("score_delta") or 0, reverse=True)
    drops = sorted([e for e in events if (e.get("score_delta") or 0) <= -MEANINGFUL_SCORE_DELTA], key=lambda e: e.get("score_delta") or 0)
    new_assessments = [e for e in events if e.get("snapshot_type") == "INITIAL"]
    decision_brief = build_monthly_decision_brief(events, limit=3)
    lines = [f"# 今月、何を再判断すべきか？ — {period_id}", "", f"意思決定イベント: {len(events)}件", f"新規評価: {len(new_assessments)}件", f"Status変更: {len(status_changes)}件", "", "## まず確認したい3件", ""]
    if not decision_brief:
        lines.append("- 今月は、既存判断を大きく変えるシグナルはありません。")
    for e in decision_brief:
        delta = e.get("score_delta")
        delta_text = f" ({delta:+.0f})" if isinstance(delta, (int, float)) else ""
        transition = f"{e.get('previous_status') or 'NEW'} → {e.get('adoption_status') or 'UNKNOWN'}"
        reason = e.get("change_reason") or e.get("main_risk") or "履歴上の変更イベント"
        lines.append(f"- **{e.get('technology_name') or e.get('canonical_entity_id')}** — {e.get('decision_label')} / {transition}{delta_text} / {reason}")
    lines.append("")
    def add_section(title: str, items: list[dict], limit: int = 20):
        lines.extend([f"## {title}", ""])
        if not items: lines.append("- 該当なし")
        for e in items[:limit]:
            delta = e.get("score_delta")
            delta_text = f" ({delta:+.0f})" if isinstance(delta, (int, float)) else ""
            lines.append(f"- {e.get('technology_name') or e.get('canonical_entity_id')}: {e.get('previous_status') or 'NEW'} → {e.get('adoption_status')}{delta_text} / {e.get('change_reason')}")
        lines.append("")
    add_section("Statusが変わったもの", status_changes)
    add_section("評価が上がったもの", rises)
    add_section("評価が下がったもの", drops)
    add_section("新規で評価したもの", new_assessments)
    summary = f"{len(decision_brief)} reconsideration picks / {len(events)} decision events / {len(status_changes)} status changes / {len(new_assessments)} new assessments"
    now = generated_at or datetime.utcnow().isoformat() + "Z"
    props = {MONTHLY_PROP_TITLE: _title(f"今月、何を再判断すべきか？ {period_id}"), MONTHLY_PROP_PERIOD_ID: _rt(period_id), MONTHLY_PROP_GENERATED_AT: _date(now), MONTHLY_PROP_CHANGE_COUNT: _number(len(events)), MONTHLY_PROP_SUMMARY: _rt(summary)}
    children = []
    full = "\n".join(lines)
    for i in range(0, len(full), 1800):
        children.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": full[i:i+1800]}}]}})
    res = requests.post("https://api.notion.com/v1/pages", json={"parent": _parent(NOTION_MONTHLY_DATA_SOURCE_ID, NOTION_MONTHLY_DATABASE_ID), "properties": props, "children": children}, headers=_headers(), timeout=30)
    if res.status_code != 200: raise RuntimeError(f"Decision monthly create failed: {res.status_code} {res.text[:500]}")
    return {"enabled": True, "created": True, "period_id": period_id, "events": len(events), "decision_brief_count": len(decision_brief), "page_id": res.json().get("id") or ""}

def build_legacy_seed_properties(record: dict, resolution: EntityResolution, migrated_at: str) -> dict:
    """Build a legacy seed without inventing Adoption Score/Status/history."""
    sources = list(dict.fromkeys(str(x) for x in (record.get("sources") or ([record.get("source")] if record.get("source") else [])) if x))
    aliases = list(dict.fromkeys(resolution.aliases))
    return {
        TECH_PROP_NAME: _title(record.get("name")),
        TECH_PROP_PRIMARY_URL: {"url": resolution.primary_url or record.get("url") or None},
        TECH_PROP_SOURCE: {"multi_select": [{"name": x} for x in sources]},
        TECH_PROP_CATEGORY: _select(record.get("category") or "OTHER"),
        TECH_PROP_FIRST_SEEN: _date(record.get("first_seen") or record.get("analyzed_at") or migrated_at),
        TECH_PROP_LAST_REVIEWED: _date(None),
        TECH_PROP_RELATED_ARTICLE: {"url": record.get("related_article") or None},
        TECH_PROP_EVIDENCE_URLS: _rt("\n".join(record.get("evidence_urls") or [])),
        TECH_PROP_ENTITY_ID: _rt(resolution.entity_id),
        TECH_PROP_ENTITY_STATUS: _select(resolution.status if resolution.status != "RESOLVED" else "RESOLVED"),
        TECH_PROP_ENTITY_ALIASES: _rt("\n".join(aliases)),
        TECH_PROP_TRACKING_STATUS: _select("PAUSED"),
        TECH_PROP_TRACKING_ELIGIBILITY: {"checkbox": False},
        TECH_PROP_TRACKING_REASON: _rt("Legacy seed only; tracking eligibility pending reassessment"),
        TECH_PROP_ASSESSMENT_STATE: _select("LEGACY_PENDING"),
        TECH_PROP_PIPELINE_STATUS: _select(record.get("pipeline_status")),
        TECH_PROP_CONTENT_STATUS: _select(record.get("content_status")),
        TECH_PROP_ARTICLE_STATUS: _select(record.get("article_status")),
        TECH_PROP_SCREENING_SCORE: _number(record.get("screening_score")),
        TECH_PROP_SCREENING_REASON: _rt(record.get("screening_reason")),
        TECH_PROP_SOURCE_SUMMARY: _rt(record.get("source_summary")),
        TECH_PROP_PUBLISHED_AT: _date(record.get("published_at")),
        TECH_PROP_ANALYZED_AT: _date(record.get("analyzed_at")),
    }


def create_legacy_seed(record: dict, resolution: EntityResolution, migrated_at: str) -> str:
    props = build_legacy_seed_properties(record, resolution, migrated_at)
    res = requests.post(
        "https://api.notion.com/v1/pages",
        json={"parent": _parent(NOTION_TECH_DATA_SOURCE_ID, NOTION_TECH_DATABASE_ID), "properties": props},
        headers=_headers(), timeout=10,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Legacy Technology seed failed: HTTP {res.status_code} {res.text[:500]}")
    return res.json().get("id") or ""
