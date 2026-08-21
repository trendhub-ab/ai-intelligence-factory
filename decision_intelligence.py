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
from datetime import datetime
from typing import Any
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

ADOPTION_STATUSES = {"WATCH", "TEST", "ADOPT", "AVOID"}
CONFIDENCE_LEVELS = {"LOW", "MEDIUM", "HIGH"}
READINESS_LEVELS = {"LOW", "MEDIUM", "HIGH"}
ENTITY_RESOLUTION_STATUSES = {"RESOLVED", "AMBIGUOUS", "LEGACY_PENDING"}
TRACKING_STATUSES = {"ACTIVE", "PAUSED", "ARCHIVED"}
ASSESSMENT_STATES = {"SCREENED", "ASSESSED", "LEGACY_PENDING", "HISTORY_PENDING"}
SNAPSHOT_TYPES = {"INITIAL", "CHANGE", "PERIODIC", "MIGRATION"}

TECH_PROP_NAME = "Technology / Project Name"
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
        if host not in {"news.ycombinator.com", "www.producthunt.com", "producthunt.com"}:
            # URL identity is intentionally conservative.  URL changes are reconciled when an
            # explicit alias (GitHub/arXiv/official URL) remains available; no title-fuzzy merge.
            return EntityResolution(f"web:{host}{p.path or '/'}".lower(), "RESOLVED", primary, aliases, "official/external primary URL")

    seed = "|".join([str(repo.get("source") or ""), name, str(repo.get("url") or "")])
    return EntityResolution(_stable_legacy_id(seed), "AMBIGUOUS", primary, aliases, "stable official entity key could not be resolved")


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
        "adoption_score": _number_value(props.get(TECH_PROP_ADOPTION_SCORE, {})),
        "adoption_status": _select_value(props.get(TECH_PROP_ADOPTION_STATUS, {})),
        "production_readiness": _select_value(props.get(TECH_PROP_PRODUCTION_READINESS, {})),
        "evidence_confidence": _select_value(props.get(TECH_PROP_EVIDENCE_CONFIDENCE, {})),
        "main_risk": _rich_text_value(props.get(TECH_PROP_MAIN_RISK, {})),
        "sources": _multi_select_values(props.get(TECH_PROP_SOURCE, {})),
        "entity_aliases": [x.strip() for x in _rich_text_value(props.get(TECH_PROP_ENTITY_ALIASES, {})).splitlines() if x.strip()],
        "evidence_urls": [x.strip() for x in _rich_text_value(props.get(TECH_PROP_EVIDENCE_URLS, {})).splitlines() if x.strip()],
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
    return props


def _diff_assessment(current: dict, assessment: dict) -> dict:
    old_score = current.get("adoption_score")
    new_score = int(assessment["adoption_score"])
    old_status = current.get("adoption_status") or ""
    old_readiness = current.get("production_readiness") or ""
    old_conf = current.get("evidence_confidence") or ""
    old_risk = current.get("main_risk") or ""
    old_evidence = {canonicalize_identity_url(x) or x for x in current.get("evidence_urls", []) if x}
    new_evidence = {canonicalize_identity_url(x) or x for x in assessment.get("evidence_urls", []) if x}
    evidence_added = sorted(x for x in new_evidence - old_evidence if x)
    changes: list[str] = []
    if old_score is not None and new_score != old_score:
        changes.append(f"Adoption Score {old_score}→{new_score}")
    if old_status and assessment.get("adoption_status") != old_status:
        changes.append(f"Adoption Status {old_status}→{assessment.get('adoption_status')}")
    if old_readiness and assessment.get("production_readiness") != old_readiness:
        changes.append(f"Production Readiness {old_readiness}→{assessment.get('production_readiness')}")
    if old_conf and assessment.get("evidence_confidence") != old_conf:
        changes.append(f"Evidence Confidence {old_conf}→{assessment.get('evidence_confidence')}")
    if old_risk and _normalize_compare_text(assessment.get("main_risk", "")) != _normalize_compare_text(old_risk):
        changes.append("Main Risk changed")
    if evidence_added:
        changes.append(f"Evidence +{len(evidence_added)}")
    return {
        "meaningful_change": bool(changes),
        "change_reason": "; ".join(changes) or "No meaningful decision change",
        "evidence_added": evidence_added,
        "previous_score": old_score,
        "score_delta": (new_score - old_score) if old_score is not None else None,
        "previous_status": old_status,
        "status_changed": bool(old_status and assessment.get("adoption_status") != old_status),
        # Retry idempotency anchor. If history append succeeds but current-state patch fails,
        # Last Change At remains unchanged, so the retry gets the same event id. If the same
        # transition happens again months later (e.g. 60→70→60→70), Last Change At has moved
        # and a distinct history event is created instead of incorrectly reusing the old row.
        "previous_change_at": current.get("last_change_at") or "",
    }


def _history_event_id(assessment: dict, diff: dict, snapshot_type: str) -> str:
    """Stable event identity. Excludes reviewed_at so a retry of the same transition is idempotent."""
    payload = {
        "entity_id": assessment.get("canonical_entity_id") or "",
        "snapshot_type": snapshot_type,
        "previous_score": diff.get("previous_score"),
        "adoption_score": assessment.get("adoption_score"),
        "previous_status": diff.get("previous_status") or "",
        # INITIAL intentionally has no transition anchor. CHANGE includes the previous
        # current-state Last Change At so retries remain idempotent while later repeated
        # transitions remain distinct historical events.
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
        history_ids: list[str] = []
        if recovering_initial:
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
        if recovering_initial and not diff["meaningful_change"]:
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
            "changed": bool(diff["meaningful_change"] or recovering_initial),
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
        TECH_PROP_TRACKING_STATUS: _select("ACTIVE"),
        TECH_PROP_TRACKING_ELIGIBILITY: {"checkbox": True},
        TECH_PROP_TRACKING_REASON: _rt("Legacy Internal Pipeline DB seed; assessment pending"),
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
