#!/usr/bin/env python3
"""AI Intelligence Factory — Subscriber Inventory Bootstrap (Run109 patch kit).

Design goals
------------
* Normal Daily behavior is unchanged. This command is manual-only.
* `plan` is read-only and uses zero Gemini calls.
* Screening Score is NEVER treated as Adoption Score.
* Existing Phase-2 Product Review remains the authority for assessment, Evidence,
  History, Technology upsert, and Subscriber sync.
* `apply` only accelerates that existing path under strict caps and fails closed if
  article-acquisition Gemini calls appear.
* Inventory targets are goals, never forced quotas. Evidence/quality can stop the run.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import requests

ARTIFACT_DIR = Path(os.environ.get("INVENTORY_BOOTSTRAP_ARTIFACT_DIR", "inventory_bootstrap_artifacts"))
DEFAULT_TARGET = int(os.environ.get("INVENTORY_BOOTSTRAP_TARGET", "30"))
DEFAULT_MIN_SELLABLE = int(os.environ.get("INVENTORY_BOOTSTRAP_MIN_SELLABLE", "24"))
NOTION_VERSION = os.environ.get("NOTION_API_VERSION", "2026-03-11")
CONFIRM_TEXT = "CONFIRM_BOOTSTRAP"

# These are launch heuristics, not Adoption rules. Keep them configurable.
DEFAULT_MIN_STATUS_DIVERSITY = int(os.environ.get("INVENTORY_BOOTSTRAP_MIN_STATUS_DIVERSITY", "3"))
DEFAULT_MIN_CATEGORY_DIVERSITY = int(os.environ.get("INVENTORY_BOOTSTRAP_MIN_CATEGORY_DIVERSITY", "4"))
DEFAULT_MIN_SOURCE_DIVERSITY = int(os.environ.get("INVENTORY_BOOTSTRAP_MIN_SOURCE_DIVERSITY", "2"))
DEFAULT_MIN_CONFIDENCE_RATIO = float(os.environ.get("INVENTORY_BOOTSTRAP_MIN_CONFIDENCE_RATIO", "0.80"))
DEFAULT_MIN_RECENT_RATIO = float(os.environ.get("INVENTORY_BOOTSTRAP_MIN_RECENT_RATIO", "0.80"))
DEFAULT_RECENT_DAYS = int(os.environ.get("INVENTORY_BOOTSTRAP_RECENT_DAYS", "30"))

NEWS_HOSTS = {
    "wired.com", "www.wired.com", "tomshardware.com", "www.tomshardware.com",
    "techcrunch.com", "www.techcrunch.com", "theverge.com", "www.theverge.com",
}
DURABLE_HOST_HINTS = (
    "github.com", "arxiv.org", "docs.", "developer.", "developers.",
    "readthedocs.", "huggingface.co", "platform.",
)
NEWS_EVENT_PATTERNS = (
    r"\bincident\b", r"\boutage\b", r"\bcompromise(?:d)?\b", r"\bhack(?:ed|ing)?\b",
    r"\bcharges?\b", r"\bprices?\b", r"\bjoining\b", r"\bacquired\b",
    r"\bask hn\b", r"\brant\b", r"\bfeels like\b",
)


@dataclass(frozen=True)
class TechnologyRecord:
    page_id: str
    name: str
    canonical_entity_id: str
    primary_url: str
    source: tuple[str, ...]
    category: str
    screening_score: float | None
    source_summary: str
    published_at: str | None
    analyzed_at: str | None
    next_review: str | None
    assessment_state: str
    entity_resolution_status: str
    tracking_status: str
    tracking_eligibility: bool
    adoption_score: float | None
    adoption_status: str
    evidence_confidence: str
    production_readiness: str
    main_risk: str
    best_for: str
    avoid_for: str
    short_rationale: str
    primary_evidence_urls: str
    last_reviewed: str | None


@dataclass(frozen=True)
class PlannedCandidate:
    canonical_entity_id: str
    name: str
    primary_url: str
    source: tuple[str, ...]
    category: str
    planning_category: str
    candidate_lane: str
    screening_score: float | None
    bootstrap_priority: float
    product_utility_score: float
    portfolio_priority: float
    reasons: tuple[str, ...]


PLANNING_CATEGORY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("SECURITY", ("security", "attack", "vulnerability", "exploit", "malware", "threat", "injection", "auth", "identity", "privacy", "governance", "safety", "guardrail")),
    ("AGENT", ("agent", "agentic", "multi-agent", "mcp", "tool use", "orchestration", "harness")),
    ("MULTIMODAL", ("multimodal", "vision", "image", "video", "speech", "audio", "voice", "vlm")),
    ("DATA", ("dataset", "data version", "database", "vector", "retrieval", "rag", "knowledge graph", "embedding", "recommendation")),
    ("INFRA", ("inference", "serving", "runtime", "gpu", "distributed", "kubernetes", "deployment", "compute", "cache", "scheduler", "pipeline engine")),
    ("DEVTOOLS", ("developer", "devtool", "sdk", "cli", "ide", "coding", "code", "mlops", "experiment", "observability", "workflow", "pipeline", "framework", "library", "repository")),
    ("MODEL", ("model", "llm", "language model", "transformer", "training", "fine-tun", "distillation", "post-training", "reasoning")),
)

PRACTICAL_TERMS = (
    "sdk", "api", "cli", "server", "platform", "tool", "framework", "library", "runtime",
    "database", "dataset", "pipeline", "deployment", "serving", "orchestration", "mlops",
    "developer", "workflow", "ide", "repository", "self-host", "open source", "open-source",
)
RESEARCH_TERMS = ("paper", "study", "benchmark", "empirical", "analysis", "theorem", "method", "model")
RISK_TERMS = ("security", "attack", "vulnerability", "exploit", "threat", "malware", "injection", "governance", "safety", "privacy")
OPINION_TERMS = ("opinion", "essay", "rant", "feels like", "thoughts on", "why i", "ask hn")

IMPLEMENTATION_ARTIFACT_HOSTS = (
    "github.com", "gitlab.com", "codeberg.org", "huggingface.co", "pypi.org", "npmjs.com",
)
IMPLEMENTATION_ARTIFACT_PHRASES = (
    "code available at", "source code at", "official implementation", "github repository",
    "implementation repository", "pip install", "npm install",
)


def has_implementation_artifact(record: TechnologyRecord) -> tuple[bool, tuple[str, ...]]:
    """Return strong, planning-only evidence that an inspectable implementation exists.

    Run111 deliberately uses a conservative test for ArXiv candidates. Merely sounding
    practical (SDK/platform/deployment terminology) is not enough: an ArXiv record must
    point to an implementation artifact through its URL/evidence/summary. This affects
    review order only and never mutates the authoritative assessment.
    """
    evidence = " ".join((record.primary_url or "", record.primary_evidence_urls or "", record.source_summary or "")).lower()
    for host in IMPLEMENTATION_ARTIFACT_HOSTS:
        if host in evidence:
            return True, (f"implementation_artifact_host:{host}",)
    for phrase in IMPLEMENTATION_ARTIFACT_PHRASES:
        if phrase in evidence and ("http://" in evidence or "https://" in evidence):
            return True, (f"implementation_artifact_phrase:{phrase}",)
    return False, ("implementation_artifact_missing",)


def infer_planning_category(record: TechnologyRecord) -> tuple[str, tuple[str, ...]]:
    """Infer a planning-only category without mutating the authoritative assessment category.

    Legacy rows are frequently OTHER because they predate the product taxonomy. The
    inferred value is used only to diversify which records are reviewed first.
    """
    if record.category and record.category != "OTHER":
        return record.category, ("authoritative_category",)
    text = f"{record.name} {record.source_summary}".lower()
    scores: list[tuple[int, int, str]] = []
    for order, (category, terms) in enumerate(PLANNING_CATEGORY_PATTERNS):
        hits = sum(1 for term in terms if term in text)
        if hits:
            scores.append((hits, -order, category))
    if not scores:
        return "OTHER", ("planning_category_unresolved",)
    _, _, category = max(scores)
    return category, (f"planning_category:{category}",)


def candidate_lane(record: TechnologyRecord, planning_category: str | None = None) -> tuple[str, tuple[str, ...]]:
    """Classify candidate intent for portfolio planning only.

    This is intentionally not an Adoption decision. A security paper can be RISK, an
    ArXiv systems paper can be RESEARCH, and a GitHub product can be PRACTICAL.
    """
    text = f"{record.name} {record.source_summary}".lower()
    if any(term in text for term in RISK_TERMS):
        return "RISK", ("lane:RISK",)
    if any(re.search(p, text, re.I) for p in NEWS_EVENT_PATTERNS) or any(term in text for term in OPINION_TERMS):
        return "DISCOVERY", ("lane:DISCOVERY",)
    if "ArXiv" in set(record.source):
        has_artifact, artifact_reasons = has_implementation_artifact(record)
        if has_artifact:
            return "PRACTICAL", ("lane:PRACTICAL_ARXIV_IMPLEMENTATION", *artifact_reasons)
        return "RESEARCH", ("lane:RESEARCH_ARXIV_NO_IMPLEMENTATION", *artifact_reasons)
    if "GitHub" in set(record.source) or any(term in text for term in PRACTICAL_TERMS):
        return "PRACTICAL", ("lane:PRACTICAL",)
    if any(term in text for term in RESEARCH_TERMS):
        return "RESEARCH", ("lane:RESEARCH",)
    if planning_category and planning_category != "OTHER":
        return "PRACTICAL", ("lane:PRACTICAL_BY_CATEGORY",)
    return "DISCOVERY", ("lane:DISCOVERY_FALLBACK",)


def product_utility_score(record: TechnologyRecord, planning_category: str | None = None, lane: str | None = None) -> tuple[float, tuple[str, ...]]:
    """Estimate paid-database usefulness for *review order*, not final Adoption.

    The score rewards concrete things a subscriber can evaluate or deploy and mildly
    defers pure research in the launch bootstrap. Research and risk remain eligible.
    """
    planning_category = planning_category or infer_planning_category(record)[0]
    lane = lane or candidate_lane(record, planning_category)[0]
    text = f"{record.name} {record.source_summary}".lower()
    score = 0.0
    reasons: list[str] = []
    if lane == "PRACTICAL":
        score += 14; reasons.append("practical_technology:+14")
    elif lane == "RISK":
        score += 9; reasons.append("decision_risk_value:+9")
    elif lane == "RESEARCH":
        score -= 3; reasons.append("research_launch_deferral:-3")
    elif lane == "DISCOVERY":
        score -= 8; reasons.append("discovery_only:-8")

    practical_hits = sum(1 for term in PRACTICAL_TERMS if term in text)
    if practical_hits >= 3:
        score += 8; reasons.append("concrete_capability_terms:+8")
    elif practical_hits >= 1:
        score += 4; reasons.append("concrete_capability_terms:+4")

    if planning_category == "OTHER":
        score -= 6; reasons.append("planning_category_other:-6")
    else:
        score += 3; reasons.append(f"planning_category_resolved:{planning_category}:+3")

    host = (urlparse(record.primary_url).hostname or "").lower()
    if host == "github.com" or host.endswith(".github.com"):
        score += 5; reasons.append("inspectable_repo:+5")
    if any(term in text for term in OPINION_TERMS):
        score -= 8; reasons.append("opinion_signal:-8")
    return round(max(-25.0, min(25.0, score)), 2), tuple(reasons)


class NotionClient:
    def __init__(self, token: str, notion_version: str = NOTION_VERSION, timeout: int = 20):
        if not token:
            raise ValueError("NOTION_DECISION_INTELLIGENCE_API_KEY is required")
        self.token = token
        self.version = notion_version
        self.timeout = timeout

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Notion-Version": self.version,
        }

    def query_data_source(self, data_source_id: str) -> list[dict[str, Any]]:
        """Query a Notion data source, with a legacy database-ID fallback.

        Phase 2 prefers Data Source IDs. Some installations still provide only the
        database ID, so plan/apply must not silently fail just because the newer
        endpoint rejects that identifier. The fallback is read-only and preserves
        the same 10k-row fail-closed bound.
        """
        if not data_source_id:
            raise ValueError("Notion data source/database ID is required")
        raw_id = str(data_source_id).strip()
        if raw_id.startswith("collection://"):
            raw_id = raw_id.split("collection://", 1)[1]

        endpoints = [
            f"https://api.notion.com/v1/data_sources/{raw_id}/query",
            f"https://api.notion.com/v1/databases/{raw_id}/query",
        ]
        last_error = ""
        for endpoint_index, url in enumerate(endpoints):
            rows: list[dict[str, Any]] = []
            cursor: str | None = None
            for page_index in range(100):  # 10k-row safety bound at page_size=100
                payload: dict[str, Any] = {"page_size": 100}
                if cursor:
                    payload["start_cursor"] = cursor
                res = requests.post(url, headers=self.headers, json=payload, timeout=self.timeout)
                if res.status_code != 200:
                    last_error = f"HTTP {res.status_code}: {res.text[:500]}"
                    # Only fall back before any page was accepted. A mid-pagination
                    # error must fail closed rather than mixing two query surfaces.
                    if endpoint_index == 0 and page_index == 0 and res.status_code in {400, 404}:
                        break
                    raise RuntimeError(f"Notion query failed {last_error}")
                data = res.json()
                batch = data.get("results") or []
                rows.extend(batch)
                if len(rows) > 10_000:
                    raise RuntimeError("Notion query exceeded 10,000-row safety limit")
                if not data.get("has_more"):
                    return rows
                cursor = data.get("next_cursor")
                if not cursor:
                    raise RuntimeError("Notion has_more=true without next_cursor")
            else:
                raise RuntimeError("Notion pagination exceeded safety iteration limit")
        raise RuntimeError(f"Notion query failed on data-source and database endpoints: {last_error}")


def _plain_text(items: Iterable[dict[str, Any]]) -> str:
    return "".join((x.get("plain_text") or (x.get("text") or {}).get("content") or "") for x in items).strip()


def _prop(page: dict[str, Any], name: str) -> Any:
    p = (page.get("properties") or {}).get(name) or {}
    t = p.get("type")
    if t == "title":
        return _plain_text(p.get("title") or [])
    if t == "rich_text":
        return _plain_text(p.get("rich_text") or [])
    if t == "url":
        return p.get("url") or ""
    if t == "number":
        return p.get("number")
    if t == "select":
        return ((p.get("select") or {}).get("name") or "")
    if t == "multi_select":
        return [x.get("name") for x in (p.get("multi_select") or []) if x.get("name")]
    if t == "checkbox":
        return bool(p.get("checkbox"))
    if t == "date":
        return ((p.get("date") or {}).get("start"))
    # Tests and exported normalized dictionaries may already be flat.
    return page.get(name)


def normalize_technology_page(page: dict[str, Any]) -> TechnologyRecord:
    def val(name: str, default: Any = "") -> Any:
        v = _prop(page, name)
        return default if v is None else v

    raw_source = val("Source", [])
    if isinstance(raw_source, str):
        raw_source = [raw_source] if raw_source else []
    return TechnologyRecord(
        page_id=page.get("id") or str(val("id", "")),
        name=str(val("Technology / Project Name", "")),
        canonical_entity_id=str(val("Canonical Entity ID", "")),
        primary_url=str(val("Primary URL", "")),
        source=tuple(str(x) for x in raw_source),
        category=str(val("Category", "")),
        screening_score=_as_float(val("Screening Score", None)),
        source_summary=str(val("Source Summary", "")),
        published_at=_as_optional_str(val("Published At", None)),
        analyzed_at=_as_optional_str(val("Analyzed At", None)),
        next_review=_as_optional_str(val("Next Review", None)),
        assessment_state=str(val("Assessment State", "")),
        entity_resolution_status=str(val("Entity Resolution Status", "")),
        tracking_status=str(val("Tracking Status", "")),
        tracking_eligibility=bool(val("Tracking Eligibility", False)),
        adoption_score=_as_float(val("Adoption Score", None)),
        adoption_status=str(val("Adoption Status", "")),
        evidence_confidence=str(val("Evidence Confidence", "")),
        production_readiness=str(val("Production Readiness", "")),
        main_risk=str(val("Main Risk", "")),
        best_for=str(val("Best For", "")),
        avoid_for=str(val("Avoid For", "")),
        short_rationale=str(val("Short Rationale", "")),
        primary_evidence_urls=str(val("Primary Evidence URLs", "")),
        last_reviewed=_as_optional_str(val("Last Reviewed", None)),
    )


def _as_float(v: Any) -> float | None:
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def _as_optional_str(v: Any) -> str | None:
    if v is None or v == "":
        return None
    return str(v)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    s = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def is_bootstrap_eligible(record: TechnologyRecord, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if record.assessment_state != "LEGACY_PENDING":
        return False
    if record.entity_resolution_status != "RESOLVED":
        return False
    if record.tracking_status == "ARCHIVED":
        return False
    if not record.primary_url.startswith(("http://", "https://")):
        return False
    due = _parse_dt(record.next_review)
    if due and due > now:
        return False
    return True


def _age_days(record: TechnologyRecord, now: datetime) -> int | None:
    dt = _parse_dt(record.published_at) or _parse_dt(record.analyzed_at)
    if not dt:
        return None
    return max(0, (now - dt).days)


def _source_bucket(record: TechnologyRecord) -> str:
    return record.source[0] if record.source else "Unknown"


def bootstrap_priority(record: TechnologyRecord, now: datetime | None = None) -> tuple[float, tuple[str, ...]]:
    """Return a planning score. This is intentionally NOT Adoption Score."""
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    screening = max(0.0, min(100.0, record.screening_score or 0.0))
    score = screening * 0.45
    reasons.append(f"screening_component={screening * 0.45:.1f}")

    sources = set(record.source)
    if "GitHub" in sources:
        score += 18
        reasons.append("durable_source:GitHub:+18")
    elif "ArXiv" in sources:
        score += 16
        reasons.append("durable_source:ArXiv:+16")
    elif "ProductHunt" in sources:
        score += 6
        reasons.append("discovery_source:ProductHunt:+6")
    elif "HackerNews" in sources:
        score += 2
        reasons.append("discovery_source:HackerNews:+2")

    host = (urlparse(record.primary_url).hostname or "").lower()
    if any(hint in host for hint in DURABLE_HOST_HINTS):
        score += 10
        reasons.append("durable_primary_url:+10")
    if host in NEWS_HOSTS:
        score -= 10
        reasons.append("news_host:-10")
    if "news.ycombinator.com" in host:
        score -= 12
        reasons.append("hn_only_url:-12")

    summary_len = len(record.source_summary.strip())
    if summary_len >= 180:
        score += 8
        reasons.append("rich_source_summary:+8")
    elif summary_len >= 70:
        score += 4
        reasons.append("usable_source_summary:+4")
    elif summary_len < 20:
        score -= 6
        reasons.append("thin_source_summary:-6")

    age = _age_days(record, now)
    if age is not None:
        if age <= 30:
            score += 10
            reasons.append("fresh<=30d:+10")
        elif age <= 90:
            score += 7
            reasons.append("fresh<=90d:+7")
        elif age <= 365:
            score += 3
            reasons.append("fresh<=365d:+3")
        elif age > 730:
            score -= 5
            reasons.append("stale>730d:-5")

    text = f"{record.name} {record.source_summary}".lower()
    pattern_hits = sum(bool(re.search(p, text, re.I)) for p in NEWS_EVENT_PATTERNS)
    if pattern_hits:
        penalty = min(18, 8 + (pattern_hits - 1) * 5)
        score -= penalty
        reasons.append(f"event_or_opinion_pattern:-{penalty}")

    # A resolved canonical entity is necessary but not a quality bonus; avoid double-counting migration confidence.
    return round(max(0.0, min(100.0, score)), 2), tuple(reasons)


def plan_candidates(records: Iterable[TechnologyRecord], limit: int = 30,
                    max_source_share: float = 0.60, now: datetime | None = None) -> list[PlannedCandidate]:
    """Rank a paid-product review queue with soft portfolio diversification.

    No fixed source/category quota determines assessment outcomes. Instead, every next
    position receives a marginal concentration penalty. The source-share limit is also
    prefix-aware, fixing Run109's failure where the first four could all be ArXiv even
    though the overall top-50 satisfied a 60% cap.
    """
    now = now or datetime.now(timezone.utc)
    pool: list[dict[str, Any]] = []
    for r in records:
        if not is_bootstrap_eligible(r, now=now):
            continue
        base, base_reasons = bootstrap_priority(r, now=now)
        pcat, cat_reasons = infer_planning_category(r)
        lane, lane_reasons = candidate_lane(r, pcat)
        utility, utility_reasons = product_utility_score(r, pcat, lane)
        pool.append({
            "record": r, "base": base, "utility": utility, "planning_category": pcat, "lane": lane,
            "reasons": base_reasons + cat_reasons + lane_reasons + utility_reasons,
        })
    if limit <= 0 or not pool:
        return []

    max_share = max(0.10, min(1.0, max_source_share))
    selected: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    lane_counts: Counter[str] = Counter()
    remaining = list(pool)

    while remaining and len(selected) < limit:
        position = len(selected) + 1
        # Prefix-aware cap: at position 4 and share .60, one source can occupy at most 3 slots.
        prefix_cap = max(1, math.ceil(position * max_share))
        feasible = [x for x in remaining if source_counts[_source_bucket(x["record"])] < prefix_cap]
        # If the corpus cannot satisfy the diversity constraint, fail soft rather than hide all remaining candidates.
        choice_pool = feasible or remaining

        def marginal(item: dict[str, Any]) -> tuple[float, float, float, str]:
            r = item["record"]
            source = _source_bucket(r)
            pcat = item["planning_category"]
            lane = item["lane"]
            # Repetition penalties are deliberately soft: a genuinely stronger candidate can still win.
            concentration_penalty = (source_counts[source] * 5.0) + (category_counts[pcat] * 2.5) + (lane_counts[lane] * 3.5)
            # OTHER gets an additional repeated penalty because legacy rows often lack taxonomy, but is never excluded.
            if pcat == "OTHER":
                concentration_penalty += 2.0 + category_counts[pcat] * 1.5
            score = item["base"] + item["utility"] - concentration_penalty
            return (score, item["base"] + item["utility"], r.screening_score or 0.0, r.name.lower())

        chosen = max(choice_pool, key=marginal)
        chosen = dict(chosen)
        chosen["portfolio_priority"] = round(marginal(chosen)[0], 2)
        selected.append(chosen)
        r = chosen["record"]
        source_counts[_source_bucket(r)] += 1
        category_counts[chosen["planning_category"]] += 1
        lane_counts[chosen["lane"]] += 1
        # remove by record object identity from the original pool item
        for idx, item in enumerate(remaining):
            if item["record"] is r:
                remaining.pop(idx)
                break

    return [
        PlannedCandidate(
            canonical_entity_id=x["record"].canonical_entity_id,
            name=x["record"].name,
            primary_url=x["record"].primary_url,
            source=x["record"].source,
            category=x["record"].category,
            planning_category=x["planning_category"],
            candidate_lane=x["lane"],
            screening_score=x["record"].screening_score,
            bootstrap_priority=x["base"],
            product_utility_score=x["utility"],
            portfolio_priority=x["portfolio_priority"],
            reasons=x["reasons"],
        ) for x in selected[:limit]
    ]


def is_sellable(record: TechnologyRecord) -> bool:
    """Count only a complete paid-product assessment, not merely an ASSESSED state."""
    return (
        record.assessment_state == "ASSESSED"
        and record.tracking_eligibility
        and record.tracking_status != "ARCHIVED"
        and bool(record.canonical_entity_id)
        and record.primary_url.startswith(("http://", "https://"))
        and record.adoption_status in {"ADOPT", "TEST", "WATCH", "AVOID"}
        and record.adoption_score is not None
        and record.evidence_confidence in {"LOW", "MEDIUM", "HIGH"}
        and record.production_readiness in {"LOW", "MEDIUM", "HIGH"}
        and bool(record.short_rationale.strip())
        and bool(record.main_risk.strip())
        and bool(record.best_for.strip())
        and bool(record.avoid_for.strip())
        and bool(record.primary_evidence_urls.strip())
    )


def is_complete_subscriber_row(page: dict[str, Any]) -> bool:
    """Subscriber-visible inventory must be a complete sanitized product row.

    Do not count blank/manual placeholder rows toward launch readiness.
    """
    canonical = str(_prop(page, "Canonical Entity ID") or "").strip()
    name = str(_prop(page, "Technology / Project Name") or "").strip()
    primary_url = str(_prop(page, "Primary URL") or "").strip()
    status = str(_prop(page, "Adoption Status") or "").strip()
    score = _as_float(_prop(page, "Adoption Score"))
    evidence = str(_prop(page, "Evidence Confidence") or "").strip()
    readiness = str(_prop(page, "Production Readiness") or "").strip()
    required_text = [
        _prop(page, "Short Rationale"),
        _prop(page, "Main Risk"),
        _prop(page, "Best For"),
        _prop(page, "Avoid For"),
        _prop(page, "Primary Evidence URLs"),
    ]
    return (
        bool(canonical and name)
        and primary_url.startswith(("http://", "https://"))
        and status in {"ADOPT", "TEST", "WATCH", "AVOID"}
        and score is not None
        and evidence in {"LOW", "MEDIUM", "HIGH"}
        and readiness in {"LOW", "MEDIUM", "HIGH"}
        and all(bool(str(x or "").strip()) for x in required_text)
    )


def _recent(record: TechnologyRecord, now: datetime, recent_days: int) -> bool:
    dt = _parse_dt(record.last_reviewed)
    return bool(dt and (now - dt).days <= recent_days)


def evaluate_readiness(records: Iterable[TechnologyRecord], *, target: int = DEFAULT_TARGET,
                       min_sellable: int = DEFAULT_MIN_SELLABLE,
                       min_status_diversity: int = DEFAULT_MIN_STATUS_DIVERSITY,
                       min_category_diversity: int = DEFAULT_MIN_CATEGORY_DIVERSITY,
                       min_source_diversity: int = DEFAULT_MIN_SOURCE_DIVERSITY,
                       min_confidence_ratio: float = DEFAULT_MIN_CONFIDENCE_RATIO,
                       min_recent_ratio: float = DEFAULT_MIN_RECENT_RATIO,
                       recent_days: int = DEFAULT_RECENT_DAYS,
                       subscriber_visible_count: int | None = None,
                       now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    sellable = [r for r in records if is_sellable(r)]
    n = len(sellable)
    statuses = sorted({r.adoption_status for r in sellable if r.adoption_status})
    categories = sorted({r.category for r in sellable if r.category})
    sources = sorted({s for r in sellable for s in r.source if s})
    confident = sum(r.evidence_confidence in {"HIGH", "MEDIUM"} for r in sellable)
    recent = sum(_recent(r, now, recent_days) for r in sellable)
    confidence_ratio = confident / n if n else 0.0
    recent_ratio = recent / n if n else 0.0

    blockers: list[str] = []
    if n < min_sellable:
        blockers.append(f"sellable<{min_sellable} ({n})")
    if len(statuses) < min_status_diversity:
        blockers.append(f"status_diversity<{min_status_diversity} ({len(statuses)})")
    if len(categories) < min_category_diversity:
        blockers.append(f"category_diversity<{min_category_diversity} ({len(categories)})")
    if len(sources) < min_source_diversity:
        blockers.append(f"source_diversity<{min_source_diversity} ({len(sources)})")
    if confidence_ratio < min_confidence_ratio:
        blockers.append(f"evidence_medium_high_ratio<{min_confidence_ratio:.2f} ({confidence_ratio:.2f})")
    if recent_ratio < min_recent_ratio:
        blockers.append(f"recent_review_ratio<{min_recent_ratio:.2f} ({recent_ratio:.2f})")

    inventory_ready = not blockers
    launch_blockers = list(blockers)
    if subscriber_visible_count is None:
        launch_blockers.append("subscriber_visible_count_unverified")
    elif subscriber_visible_count < min_sellable:
        launch_blockers.append(f"subscriber_visible<{min_sellable} ({subscriber_visible_count})")

    return {
        "target": target,
        "min_sellable": min_sellable,
        "sellable_count": n,
        "target_reached": n >= target,
        "status_values": statuses,
        "category_values": categories,
        "source_values": sources,
        "evidence_medium_high_ratio": round(confidence_ratio, 4),
        "recent_review_ratio": round(recent_ratio, 4),
        "recent_days": recent_days,
        "inventory_ready": inventory_ready,
        "inventory_blockers": blockers,
        "subscriber_visible_count": subscriber_visible_count,
        "launch_ready": not launch_blockers,
        "launch_blockers": launch_blockers,
    }


def subscriber_visible_count(client: NotionClient, data_source_id: str | None) -> int | None:
    if not data_source_id:
        return None
    return sum(is_complete_subscriber_row(page) for page in client.query_data_source(data_source_id))


def product_only_environment(max_reviews: int, product_request_budget: int) -> dict[str, str]:
    if not 1 <= max_reviews <= 6:
        raise ValueError("max_reviews must be between 1 and 6")
    if not 1 <= product_request_budget <= 9:
        raise ValueError("product_request_budget must be between 1 and 9")
    return {
        "INVENTORY_BOOTSTRAP_ACTIVE": "true",
        "ENABLE_REVENUE_PRODUCT_PHASE2": "true",
        "ENABLE_DECISION_INTELLIGENCE_DB": "true",
        "ENABLE_SUBSCRIBER_TECH_SYNC": "true",
        # Disable acquisition work. Unknown keys are harmless on older baselines.
        "GITHUB_FETCH_LIMIT": "0",
        "HN_FETCH_LIMIT": "0",
        "ARXIV_FETCH_LIMIT": "0",
        "PRODUCTHUNT_FETCH_LIMIT": "0",
        "MAX_SCREENING_CANDIDATES": "0",
        "ENABLE_GLOBAL_CALIBRATION": "false",
        "TOP_N_FOR_DEEP_DIVE": "0",
        "MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS": "0",
        "GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET": "0",
        "PENDING_RETRY_MAX_PER_RUN": "0",
        "DEFERRED_DEEP_DIVE_MAX_PER_RUN": "0",
        "ENABLE_SOURCE_ROI_LEARNING": "false",
        "SOURCE_ROI_MIN_FETCH_PER_SOURCE": "0",
        # No unrelated product/report/history artifacts should be emitted by the
        # manual inventory accelerator. Technology/History writes caused by the
        # Product Review transaction itself remain enabled.
        "ENABLE_DECISION_MONTHLY_DIGEST": "false",
        "ENABLE_MONTHLY_DIGEST": "false",
        "ENABLE_OBSERVED_HISTORY": "false",
        # Existing Phase-2 Product Review is the sole Gemini path.
        "PRODUCT_REVIEW_MAX_PER_RUN": str(max_reviews),
        "LEGACY_BOOTSTRAP_MAX_PER_RUN": str(max_reviews),
        # Evidence preflight is zero Gemini. Inspect enough ordered candidates to fill the
        # paid review slots even when some rows are unresolvable, but keep network work bounded.
        "PRODUCT_REVIEW_PREFLIGHT_SCAN_LIMIT": str(min(24, max(max_reviews * 4, max_reviews + 6))),
        "GEMINI_PRODUCT_REVIEW_PER_RUN_REQUEST_BUDGET": str(product_request_budget),
    }


def detect_unsafe_pipeline_activity(log_text: str) -> list[str]:
    problems: list[str] = []
    patterns = {
        "screening_gemini_call": r"(?:kind=screening(?:_|\b)|\[.*SCREENING.*GEMINI|screening_batch=[1-9]\d*)",
        "calibration_gemini_call": r"(?:kind=global_calibration|global_calibration=[1-9]\d*)",
        "deep_dive_gemini_call": r"(?:\[GEMINI DEEP DIVE CALL\]|kind=deep_dive(?:_|\b)|deep_dive=[1-9]\d*)",
        "quality_retry_call": r"(?:kind=quality_retry|quality_retry=[1-9]\d*)",
    }
    for name, pattern in patterns.items():
        if re.search(pattern, log_text, re.I):
            problems.append(name)
    return problems


def _write_artifacts(prefix: str, data: dict[str, Any], markdown: str) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    jp = ARTIFACT_DIR / f"{stamp}_{prefix}.json"
    mp = ARTIFACT_DIR / f"{stamp}_{prefix}.md"
    jp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    mp.write_text(markdown, encoding="utf-8")
    return jp, mp


def _plan_markdown(readiness: dict[str, Any], planned: list[PlannedCandidate]) -> str:
    lines = [
        "# Subscriber Inventory Bootstrap Plan",
        "",
        "> Bootstrap Priorityは初期在庫の評価順を決める0-API補助値です。Adoption Scoreではありません。",
        "",
        "## Current readiness",
        f"- Sellable: **{readiness['sellable_count']}** / target {readiness['target']}",
        f"- Inventory ready: **{readiness['inventory_ready']}**",
        f"- Launch ready: **{readiness['launch_ready']}**",
        f"- Blockers: {', '.join(readiness['launch_blockers']) or 'none'}",
        "",
        "## Planned legacy candidates",
        "",
        "| # | Portfolio | Utility | Base | Screening | Lane | Planning Category | Source | Technology |",
        "|---:|---:|---:|---:|---:|---|---|---|---|",
    ]
    for i, c in enumerate(planned, 1):
        src = ", ".join(c.source) or "Unknown"
        lines.append(f"| {i} | {c.portfolio_priority:.2f} | {c.product_utility_score:+.2f} | {c.bootstrap_priority:.2f} | {c.screening_score if c.screening_score is not None else ''} | {c.candidate_lane} | {c.planning_category} | {src} | {c.name.replace('|', '/')} |")
    return "\n".join(lines) + "\n"


def run_plan(args: argparse.Namespace) -> dict[str, Any]:
    token = os.environ.get("NOTION_DECISION_INTELLIGENCE_API_KEY", "")
    tech_ds = os.environ.get("NOTION_TECH_DATA_SOURCE_ID", "") or os.environ.get("NOTION_TECH_DATABASE_ID", "")
    sub_ds = os.environ.get("NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID", "") or os.environ.get("NOTION_SUBSCRIBER_TECH_DATABASE_ID", "")
    client = NotionClient(token)
    records = [normalize_technology_page(x) for x in client.query_data_source(tech_ds)]
    visible = subscriber_visible_count(client, sub_ds)
    readiness = evaluate_readiness(records, target=args.target, min_sellable=args.min_sellable,
                                   subscriber_visible_count=visible)
    planned = plan_candidates(records, limit=args.plan_limit, max_source_share=args.max_source_share)
    data = {
        "mode": "plan",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "zero_gemini_calls": True,
        "readiness": readiness,
        "eligible_legacy_count": sum(is_bootstrap_eligible(r) for r in records),
        "planned": [asdict(x) for x in planned],
    }
    j, m = _write_artifacts("inventory_bootstrap_plan", data, _plan_markdown(readiness, planned))
    print(json.dumps({"artifact_json": str(j), "artifact_md": str(m), **data}, ensure_ascii=False, indent=2))
    return data


def should_skip_apply(readiness: dict[str, Any]) -> bool:
    """Skip only when both stretch target and actual launch readiness are satisfied."""
    return bool(readiness.get("target_reached") and readiness.get("launch_ready"))


def run_apply(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRM_TEXT:
        raise RuntimeError(f"apply requires --confirm {CONFIRM_TEXT}")
    if not Path(args.pipeline).is_file():
        raise FileNotFoundError(f"pipeline not found: {args.pipeline}")

    token = os.environ.get("NOTION_DECISION_INTELLIGENCE_API_KEY", "")
    tech_ds = os.environ.get("NOTION_TECH_DATA_SOURCE_ID", "") or os.environ.get("NOTION_TECH_DATABASE_ID", "")
    sub_ds = os.environ.get("NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID", "") or os.environ.get("NOTION_SUBSCRIBER_TECH_DATABASE_ID", "")
    if not sub_ds:
        raise RuntimeError("Subscriber DB ID is required for apply; refusing to create hidden internal-only inventory")
    client = NotionClient(token)
    before_records = [normalize_technology_page(x) for x in client.query_data_source(tech_ds)]
    before_visible = subscriber_visible_count(client, sub_ds)
    before = evaluate_readiness(before_records, target=args.target, min_sellable=args.min_sellable,
                                subscriber_visible_count=before_visible)
    if should_skip_apply(before):
        data = {"mode": "apply", "skipped": True, "reason": "target_and_launch_readiness_already_reached", "before": before, "after": before}
        _write_artifacts("inventory_bootstrap_apply_skipped", data, "# Bootstrap Apply\n\nTarget already reached; no model call made.\n")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return data

    # Recompute the zero-API Plan against the same before-snapshot and propagate its ordered
    # canonical IDs into the authoritative Run108 Product Review selector. This closes the gap
    # where a human reviewed one Plan but apply used the old Screening-Score legacy order.
    apply_plan = plan_candidates(
        before_records,
        limit=max(args.target, args.max_reviews),
        max_source_share=getattr(args, "max_source_share", 0.60),
    )
    env = os.environ.copy()
    env.update(product_only_environment(args.max_reviews, args.product_request_budget))
    env["INVENTORY_BOOTSTRAP_ENTITY_IDS"] = ",".join(x.canonical_entity_id for x in apply_plan if x.canonical_entity_id)
    cmd = [sys.executable, args.pipeline]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=args.timeout)
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    unsafe = detect_unsafe_pipeline_activity(combined)
    # A generic budget summary exists even when zero reviews ran, so it is not
    # sufficient proof that the Product Review stage was actually reached.
    product_review_seen = bool(re.search(r"\[PRODUCT REVIEW(?:\]|\s)", combined, re.I))

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = ARTIFACT_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_inventory_bootstrap_pipeline.log"
    log_path.write_text(combined, encoding="utf-8")

    if proc.returncode != 0:
        raise RuntimeError(f"product-only pipeline exited {proc.returncode}; see {log_path}")
    if unsafe:
        raise RuntimeError(f"bootstrap safety violation: {unsafe}; see {log_path}")

    after_records = [normalize_technology_page(x) for x in client.query_data_source(tech_ds)]
    after_visible = subscriber_visible_count(client, sub_ds)
    after = evaluate_readiness(after_records, target=args.target, min_sellable=args.min_sellable,
                               subscriber_visible_count=after_visible)
    sellable_delta = after["sellable_count"] - before["sellable_count"]
    visible_delta = (after_visible - before_visible) if after_visible is not None and before_visible is not None else None
    subscriber_sync_progress = bool(visible_delta and visible_delta > 0)
    if not product_review_seen and not subscriber_sync_progress and not after["launch_ready"]:
        raise RuntimeError(
            "existing pipeline did not expose Product Review activity or Subscriber sync progress "
            f"in product-only mode; refusing to claim bootstrap progress. See {log_path}"
        )

    data = {
        "mode": "apply",
        "skipped": False,
        "pipeline_returncode": proc.returncode,
        "unsafe_activity": unsafe,
        "product_review_path_seen": product_review_seen,
        "max_reviews": args.max_reviews,
        "product_request_budget": args.product_request_budget,
        "ordered_allowlist_count": len(apply_plan),
        "ordered_allowlist": [x.canonical_entity_id for x in apply_plan],
        "before": before,
        "after": after,
        "sellable_delta": sellable_delta,
        "subscriber_visible_delta": visible_delta,
        "progress_made": bool(sellable_delta > 0 or subscriber_sync_progress),
        "pipeline_log": str(log_path),
    }
    md = (
        "# Subscriber Inventory Bootstrap Apply\n\n"
        f"- Sellable: {before['sellable_count']} → {after['sellable_count']}\n"
        f"- Subscriber visible: {before_visible} → {after_visible}\n"
        f"- Inventory ready: {after['inventory_ready']}\n"
        f"- Launch ready: {after['launch_ready']}\n"
        f"- Remaining blockers: {', '.join(after['launch_blockers']) or 'none'}\n"
    )
    j, m = _write_artifacts("inventory_bootstrap_apply", data, md)
    data["artifact_json"] = str(j)
    data["artifact_md"] = str(m)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return data


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Manual subscriber inventory bootstrap; plan is read-only by default")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("plan", "apply"):
        sp = sub.add_parser(name)
        sp.add_argument("--target", type=int, default=DEFAULT_TARGET)
        sp.add_argument("--min-sellable", type=int, default=DEFAULT_MIN_SELLABLE)
        if name == "plan":
            sp.add_argument("--plan-limit", type=int, default=50)
            sp.add_argument("--max-source-share", type=float, default=0.60)
        else:
            sp.add_argument("--confirm", default="")
            sp.add_argument("--max-reviews", type=int, default=4)
            sp.add_argument("--product-request-budget", type=int, default=6)
            sp.add_argument("--pipeline", default="pipeline.py")
            sp.add_argument("--timeout", type=int, default=1800)
            sp.add_argument("--max-source-share", type=float, default=0.60)
    return p


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "plan":
            run_plan(args)
        else:
            run_apply(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
