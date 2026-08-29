#!/usr/bin/env python3
"""Run Daily Product Review through the profit-aligned portfolio queue.

The normal Daily article pipeline runs first with Product Review disabled. This
small second pass then:
1. reads the updated Technology Intelligence state with zero Gemini calls;
2. applies bounded, change-driven review eligibility before any Gemini request;
3. ranks eligible records with the existing profit-aligned portfolio policy;
4. invokes the authoritative pipeline in product-only fail-closed mode using an
   explicit ordered allowlist;
5. runs Context-First enrichment with zero additional Gemini requests.

Run162 scaling contract:
- article/entity volume must not make Gemini usage grow linearly;
- fresh evidence can immediately promote an assessed entity for review;
- unchanged assessed entities use deterministic HIGH/NORMAL/LOW review cadence;
- HISTORY_PENDING integrity recovery remains first;
- existing daily max-review and request-budget hard caps remain authoritative;
- no new Notion properties and no Gemini calls are introduced by this planner.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import context_first_enrichment
import decision_intelligence
import inventory_bootstrap as ib
from technology_portfolio_policy import rank_portfolio_records


DEFAULT_MAX_REVIEWS = max(0, int(os.environ.get("DAILY_PORTFOLIO_REVIEW_MAX", "2")))
DEFAULT_REQUEST_BUDGET = max(0, int(os.environ.get("DAILY_PORTFOLIO_REQUEST_BUDGET", "3")))
DEFAULT_SCAN_LIMIT = max(1, int(os.environ.get("DAILY_PORTFOLIO_SCAN_LIMIT", "12")))
TRACKING_REVIEW_DAYS = max(1, int(os.environ.get("TRACKING_REVIEW_DAYS", "14")))
REVIEW_TIER_HIGH_DAYS = max(1, int(os.environ.get("REVIEW_TIER_HIGH_DAYS", str(TRACKING_REVIEW_DAYS))))
REVIEW_TIER_NORMAL_DAYS = max(REVIEW_TIER_HIGH_DAYS, int(os.environ.get("REVIEW_TIER_NORMAL_DAYS", "30")))
REVIEW_TIER_LOW_DAYS = max(REVIEW_TIER_NORMAL_DAYS, int(os.environ.get("REVIEW_TIER_LOW_DAYS", "60")))


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _is_due(value: Any, now: datetime) -> bool:
    parsed = _dt(value)
    return parsed is None or parsed <= now


def technology_page_to_review_state(page: dict[str, Any]) -> dict[str, Any]:
    """Read the authoritative product state plus the evidence-change timestamp.

    ``technology_page_to_state`` intentionally predates the event-driven planner
    and does not currently expose Last Evidence Update. Read that already-existing
    canonical property directly here rather than changing the shared parser/schema.
    Missing/malformed property shapes remain empty and therefore fail closed.
    """
    state = decision_intelligence.technology_page_to_state(page)
    props = page.get("properties", {}) if isinstance(page, dict) else {}
    evidence_prop = props.get(decision_intelligence.TECH_PROP_LAST_EVIDENCE_UPDATE, {}) or {}
    evidence_date = evidence_prop.get("date") or {}
    state["last_evidence_update"] = evidence_date.get("start") or ""
    return state


def review_priority_tier(state: dict[str, Any]) -> str:
    """Derive review cadence with zero API calls and no persisted schema changes.

    HIGH is deliberately narrow: high-value/high-confidence deployed candidates.
    NORMAL covers useful TEST/WATCH inventory and mid/high scores.
    LOW is the long tail. A LOW entity is never permanently suppressed because
    fresh evidence bypasses cadence in ``daily_review_reason``.
    """
    status = str(state.get("adoption_status") or "").upper()
    confidence = str(state.get("evidence_confidence") or "").upper()
    readiness = str(state.get("production_readiness") or "").upper()
    try:
        score = int(state.get("adoption_score"))
    except (TypeError, ValueError):
        score = 0

    if status == "ADOPT" or score >= 85 or (status == "TEST" and confidence == "HIGH" and readiness == "HIGH"):
        return "HIGH"
    if status in {"TEST", "WATCH"} or score >= 65:
        return "NORMAL"
    return "LOW"


def review_interval_days(state: dict[str, Any]) -> int:
    tier = review_priority_tier(state)
    if tier == "HIGH":
        return REVIEW_TIER_HIGH_DAYS
    if tier == "NORMAL":
        return REVIEW_TIER_NORMAL_DAYS
    return REVIEW_TIER_LOW_DAYS


def has_fresh_evidence(state: dict[str, Any]) -> bool:
    """Return True only when evidence was updated after the last Product Review.

    Missing/invalid timestamps fail closed to False so malformed metadata cannot
    force extra Gemini consumption. A never-reviewed entity is handled separately
    by the ordinary due logic.
    """
    last_evidence = _dt(state.get("last_evidence_update"))
    last_reviewed = _dt(state.get("last_reviewed"))
    return bool(last_evidence and last_reviewed and last_evidence > last_reviewed)


def daily_review_reason(state: dict[str, Any], now: datetime | None = None) -> str | None:
    """Return the zero-API reason an entity may enter the Product Review queue."""
    now = now or datetime.now(timezone.utc)
    assessment = str(state.get("assessment_state") or "")
    tracking_eligible = bool(state.get("tracking_eligibility"))

    if assessment == "HISTORY_PENDING" and tracking_eligible:
        return "HISTORY_PENDING"

    if assessment == "LEGACY_PENDING":
        if str(state.get("entity_status") or "") != "RESOLVED":
            return None
        return "SCHEDULED" if _is_due(state.get("next_review"), now) else None

    if assessment == "SCREENED" and tracking_eligible:
        return "SCHEDULED" if _is_due(state.get("next_review"), now) else None

    if (
        assessment == "ASSESSED"
        and tracking_eligible
        and str(state.get("tracking_status") or "") != "ARCHIVED"
    ):
        if has_fresh_evidence(state):
            return "FRESH_EVIDENCE"
        if state.get("next_review"):
            return "SCHEDULED" if _is_due(state.get("next_review"), now) else None
        last_reviewed = _dt(state.get("last_reviewed"))
        if last_reviewed is None:
            return "NEVER_REVIEWED"
        if last_reviewed <= now - timedelta(days=review_interval_days(state)):
            return "TIER_DUE"
    return None


def daily_review_bucket(state: dict[str, Any], now: datetime | None = None) -> str | None:
    """Compatibility wrapper used by existing callers/tests."""
    reason = daily_review_reason(state, now=now)
    if reason == "HISTORY_PENDING":
        return "HISTORY_PENDING"
    return "PORTFOLIO" if reason else None


def _infer_sources(state: dict[str, Any]) -> tuple[str, ...]:
    raw = state.get("sources") or state.get("source") or []
    if isinstance(raw, str):
        raw = [raw]
    sources = tuple(dict.fromkeys(str(x) for x in raw if x))
    if sources:
        return sources
    host = (urlparse(str(state.get("primary_url") or "")).hostname or "").lower()
    if host == "github.com":
        return ("GitHub",)
    if host.endswith("arxiv.org"):
        return ("ArXiv",)
    if "producthunt.com" in host:
        return ("ProductHunt",)
    if host == "news.ycombinator.com":
        return ("HackerNews",)
    return ()


def state_to_record(state: dict[str, Any]) -> ib.TechnologyRecord:
    """Adapt a Technology state to the existing zero-API portfolio scoring contract."""
    sources = _infer_sources(state)
    evidence = state.get("evidence_urls") or state.get("primary_evidence_urls") or ""
    if isinstance(evidence, (list, tuple)):
        evidence = "\n".join(str(x) for x in evidence if x)
    return ib.TechnologyRecord(
        page_id=str(state.get("page_id") or ""),
        name=str(state.get("technology_name") or state.get("name") or "Technology"),
        canonical_entity_id=str(state.get("canonical_entity_id") or ""),
        primary_url=str(state.get("primary_url") or ""),
        source=sources,
        category=str(state.get("category") or "OTHER"),
        screening_score=state.get("screening_score"),
        source_summary=str(state.get("source_summary") or state.get("short_rationale") or ""),
        published_at=state.get("published_at") or state.get("first_seen"),
        analyzed_at=state.get("analyzed_at") or state.get("last_reviewed"),
        next_review=state.get("next_review"),
        assessment_state=str(state.get("assessment_state") or ""),
        entity_resolution_status=str(state.get("entity_status") or ""),
        tracking_status=str(state.get("tracking_status") or ""),
        tracking_eligibility=bool(state.get("tracking_eligibility")),
        adoption_score=state.get("adoption_score"),
        adoption_status=str(state.get("adoption_status") or ""),
        evidence_confidence=str(state.get("evidence_confidence") or ""),
        production_readiness=str(state.get("production_readiness") or ""),
        main_risk=str(state.get("main_risk") or ""),
        best_for=str(state.get("best_for") or ""),
        avoid_for=str(state.get("avoid_for") or ""),
        short_rationale=str(state.get("short_rationale") or ""),
        primary_evidence_urls=str(evidence),
        last_reviewed=state.get("last_reviewed"),
    )


def _rank_states(states: list[dict[str, Any]], limit: int, now: datetime) -> list[str]:
    records = [state_to_record(x) for x in states if str(x.get("canonical_entity_id") or "")]
    ranked = rank_portfolio_records(ib, records, limit=max(0, limit), now=now)
    return [x.canonical_entity_id for x in ranked if x.canonical_entity_id]


def plan_daily_review_allowlist(
    states: list[dict[str, Any]],
    *,
    scan_limit: int = DEFAULT_SCAN_LIMIT,
    now: datetime | None = None,
) -> list[str]:
    """Return an ordered fail-closed allowlist for the existing Product Review path.

    Priority order is integrity recovery -> fresh evidence -> periodic portfolio.
    Within fresh/periodic groups the established profit-aligned ranking remains
    authoritative. The scan limit and downstream Gemini budget remain hard caps.
    """
    now = now or datetime.now(timezone.utc)
    history: list[dict[str, Any]] = []
    fresh: list[dict[str, Any]] = []
    periodic: list[dict[str, Any]] = []
    for state in states:
        reason = daily_review_reason(state, now=now)
        if reason == "HISTORY_PENDING":
            history.append(state)
        elif reason == "FRESH_EVIDENCE":
            fresh.append(state)
        elif reason:
            periodic.append(state)

    history.sort(key=lambda x: (str(x.get("last_reviewed") or ""), str(x.get("canonical_entity_id") or "")))

    ordered: list[str] = []
    for state in history:
        entity_id = str(state.get("canonical_entity_id") or "")
        if entity_id and entity_id not in ordered:
            ordered.append(entity_id)

    remaining = max(0, scan_limit - len(ordered))
    for entity_id in _rank_states(fresh, remaining, now):
        if entity_id not in ordered:
            ordered.append(entity_id)
    remaining = max(0, scan_limit - len(ordered))
    for entity_id in _rank_states(periodic, remaining, now):
        if entity_id not in ordered:
            ordered.append(entity_id)
    return ordered[: max(0, scan_limit)]


def _run_product_only(allowlist: list[str], max_reviews: int, request_budget: int, timeout: int = 1800) -> dict[str, Any]:
    if not allowlist or max_reviews <= 0 or request_budget <= 0:
        return {"skipped": True, "reason": "no_due_candidates_or_budget", "allowlist_count": len(allowlist)}

    env = os.environ.copy()
    env.update(ib.product_only_environment(max_reviews, request_budget))
    env["INVENTORY_BOOTSTRAP_ENTITY_IDS"] = ",".join(allowlist)
    proc = subprocess.run(
        [sys.executable, "pipeline.py"], env=env, capture_output=True, text=True, timeout=timeout
    )
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="" if proc.stderr.endswith("\n") else "\n")

    unsafe = ib.detect_unsafe_pipeline_activity(combined)
    if proc.returncode != 0:
        raise RuntimeError(f"Daily portfolio Product Review exited {proc.returncode}")
    if unsafe:
        raise RuntimeError(f"Daily portfolio Product Review safety violation: {unsafe}")
    if not re_product_review_seen(combined):
        raise RuntimeError("Daily portfolio Product Review path was not observed; refusing silent success")
    return {
        "skipped": False,
        "returncode": proc.returncode,
        "allowlist_count": len(allowlist),
        "max_reviews": max_reviews,
        "request_budget": request_budget,
    }


def re_product_review_seen(text: str) -> bool:
    return "[PRODUCT REVIEW" in (text or "").upper()


def main() -> int:
    if not decision_intelligence.ENABLE_DECISION_INTELLIGENCE_DB:
        print(json.dumps({"skipped": True, "reason": "decision_intelligence_disabled"}))
        return 0

    context_first_enrichment.preflight_context_first_schema()

    pages = decision_intelligence.query_technology_records(max_records=5000)
    states = [technology_page_to_review_state(page) for page in pages]
    previous_reviewed = {
        str(state.get("canonical_entity_id")): state.get("last_reviewed")
        for state in states
        if str(state.get("canonical_entity_id") or "")
    }

    scan_limit = min(24, max(DEFAULT_SCAN_LIMIT, DEFAULT_MAX_REVIEWS * 4, DEFAULT_MAX_REVIEWS + 6))
    allowlist = plan_daily_review_allowlist(states, scan_limit=scan_limit)
    result = _run_product_only(allowlist, DEFAULT_MAX_REVIEWS, DEFAULT_REQUEST_BUDGET)
    result["ordered_allowlist"] = allowlist
    result["review_policy"] = {
        "high_days": REVIEW_TIER_HIGH_DAYS,
        "normal_days": REVIEW_TIER_NORMAL_DAYS,
        "low_days": REVIEW_TIER_LOW_DAYS,
        "max_reviews": DEFAULT_MAX_REVIEWS,
        "request_budget": DEFAULT_REQUEST_BUDGET,
    }

    result["context_first"] = context_first_enrichment.enrich_context_first(previous_reviewed)

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
