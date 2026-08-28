#!/usr/bin/env python3
"""Run Daily Product Review through the Run131 profit-aligned portfolio queue.

The normal Daily article pipeline runs first with Product Review disabled. This
small second pass then:
1. reads the updated Technology Intelligence state with zero Gemini calls;
2. keeps the existing Product Review eligibility/cooldown semantics;
3. ranks eligible records with Run131 tolerance-protected portfolio diversity;
4. invokes the existing pipeline in its product-only fail-closed mode using an
   explicit ordered allowlist.

This avoids invasive edits to pipeline.py and keeps Evidence, assessment, History,
Subscriber sync and Gemini accounting under the existing authoritative code path.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import decision_intelligence
import inventory_bootstrap as ib
from technology_portfolio_policy import rank_portfolio_records


DEFAULT_MAX_REVIEWS = max(0, int(os.environ.get("DAILY_PORTFOLIO_REVIEW_MAX", "2")))
DEFAULT_REQUEST_BUDGET = max(0, int(os.environ.get("DAILY_PORTFOLIO_REQUEST_BUDGET", "3")))
DEFAULT_SCAN_LIMIT = max(1, int(os.environ.get("DAILY_PORTFOLIO_SCAN_LIMIT", "12")))
TRACKING_REVIEW_DAYS = max(1, int(os.environ.get("TRACKING_REVIEW_DAYS", "14")))


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


def daily_review_bucket(state: dict[str, Any], now: datetime | None = None) -> str | None:
    """Mirror Product Review eligibility without changing persisted product state."""
    now = now or datetime.now(timezone.utc)
    assessment = str(state.get("assessment_state") or "")
    tracking_eligible = bool(state.get("tracking_eligibility"))

    if assessment == "HISTORY_PENDING" and tracking_eligible:
        return "HISTORY_PENDING"

    if assessment == "LEGACY_PENDING":
        if str(state.get("entity_status") or "") != "RESOLVED":
            return None
        if not _is_due(state.get("next_review"), now):
            return None
        return "PORTFOLIO"

    if assessment == "SCREENED" and tracking_eligible:
        if not _is_due(state.get("next_review"), now):
            return None
        return "PORTFOLIO"

    if (
        assessment == "ASSESSED"
        and tracking_eligible
        and str(state.get("tracking_status") or "") != "ARCHIVED"
    ):
        if state.get("next_review"):
            return "PORTFOLIO" if _is_due(state.get("next_review"), now) else None
        last_reviewed = _dt(state.get("last_reviewed"))
        if last_reviewed is None or last_reviewed <= now - timedelta(days=TRACKING_REVIEW_DAYS):
            return "PORTFOLIO"
    return None


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


def plan_daily_review_allowlist(
    states: list[dict[str, Any]],
    *,
    scan_limit: int = DEFAULT_SCAN_LIMIT,
    now: datetime | None = None,
) -> list[str]:
    """Return an ordered fail-closed allowlist for the existing Product Review path.

    HISTORY_PENDING is integrity recovery and remains first. Everything else competes
    in one portfolio pool: no legacy quota, no source quota and no weak-candidate
    promotion merely to make the mix look diverse.
    """
    now = now or datetime.now(timezone.utc)
    history: list[dict[str, Any]] = []
    portfolio_states: list[dict[str, Any]] = []
    for state in states:
        bucket = daily_review_bucket(state, now=now)
        if bucket == "HISTORY_PENDING":
            history.append(state)
        elif bucket == "PORTFOLIO":
            portfolio_states.append(state)

    history.sort(key=lambda x: (str(x.get("last_reviewed") or ""), str(x.get("canonical_entity_id") or "")))
    records = [state_to_record(x) for x in portfolio_states if str(x.get("canonical_entity_id") or "")]
    ranked = rank_portfolio_records(ib, records, limit=max(0, scan_limit), now=now)

    ordered: list[str] = []
    for state in history:
        entity_id = str(state.get("canonical_entity_id") or "")
        if entity_id and entity_id not in ordered:
            ordered.append(entity_id)
    for candidate in ranked:
        if candidate.canonical_entity_id and candidate.canonical_entity_id not in ordered:
            ordered.append(candidate.canonical_entity_id)
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
    # Preserve the authoritative pipeline logs in Actions output.
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
    if DEFAULT_MAX_REVIEWS <= 0 or DEFAULT_REQUEST_BUDGET <= 0:
        print(json.dumps({"skipped": True, "reason": "daily_product_review_disabled"}))
        return 0

    pages = decision_intelligence.query_technology_records(max_records=5000)
    states = [decision_intelligence.technology_page_to_state(page) for page in pages]
    scan_limit = min(24, max(DEFAULT_SCAN_LIMIT, DEFAULT_MAX_REVIEWS * 4, DEFAULT_MAX_REVIEWS + 6))
    allowlist = plan_daily_review_allowlist(states, scan_limit=scan_limit)
    result = _run_product_only(allowlist, DEFAULT_MAX_REVIEWS, DEFAULT_REQUEST_BUDGET)
    result["ordered_allowlist"] = allowlist
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
