#!/usr/bin/env python3
"""Issue #668: bounded, aggregate-only read-only re-review dry run.

This module intentionally:
- reads the paid decision source DB but never mutates Notion;
- selects a deterministic, source-diverse queue from records older than 30 days;
- reuses the existing source resolver + Evidence gate before any model could run;
- never calls Gemini or any other model;
- re-reads the selected DB rows and fails closed if review date, score, or status changed;
- emits aggregate counts only (no paid record names, IDs, URLs, or evidence extracts).

It is a validation lane only. It does not advance review dates and does not make
the future write path implicit.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlparse

import decision_intelligence
import member_presentation_sync as member


DEFAULT_LIMIT = 5
DEFAULT_STALE_DAYS = 30
MODEL_ENV_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY")


def _date_only(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


def _score(value: Any) -> float:
    if isinstance(value, bool):
        return -1.0
    if isinstance(value, (int, float)):
        return float(value)
    return -1.0


def source_bucket(state: dict[str, Any]) -> str:
    """Collapse mixed discovery labels to a stable acquisition bucket."""
    sources = [str(x) for x in (state.get("sources") or []) if x]
    joined = " ".join(sources).casefold()
    primary = str(state.get("primary_url") or "")
    host = (urlparse(primary).hostname or "").casefold()

    if "github" in joined or host in {"github.com", "www.github.com"}:
        return "GitHub"
    if "arxiv" in joined or host.endswith("arxiv.org"):
        return "ArXiv"
    if "hacker" in joined or "ycombinator" in joined:
        return "HackerNews"
    if "officialvendor" in joined or "official vendor" in joined:
        return "OfficialVendor"
    if sources:
        return sources[0][:48]
    if host:
        return "WebPrimary"
    return "MissingSource"


def _brief_reference_ids(states: list[dict[str, Any]], limit: int = 5) -> set[str]:
    """Mirror the existing paid Brief's practical top-pick policy without writing."""
    practical = [
        s for s in states
        if s.get("classification") == "実務判断"
        and s.get("status") in {"ADOPT", "TEST"}
        and s.get("confidence") != "低"
        and _score(s.get("score")) >= 0
        and s.get("sync_id")
    ]
    practical.sort(
        key=lambda s: (
            -_score(s.get("score")),
            0 if s.get("confidence") == "高" else 1,
            0 if s.get("readiness") == "高" else 1,
            str(s.get("sync_id") or ""),
        )
    )
    return {str(s["sync_id"]) for s in practical[: max(0, limit)]}


def _queue_priority(state: dict[str, Any], brief_ids: set[str]) -> tuple:
    status_rank = {"ADOPT": 0, "TEST": 1, "WATCH": 2, "AVOID": 3}.get(
        str(state.get("status") or ""), 4
    )
    reviewed = _date_only(state.get("last_reviewed")) or date.min
    return (
        0 if str(state.get("sync_id") or "") in brief_ids else 1,
        status_rank,
        -_score(state.get("score")),
        reviewed,
        str(state.get("sync_id") or ""),
    )


def select_diverse_stale_queue(
    states: list[dict[str, Any]],
    *,
    as_of: date,
    stale_days: int = DEFAULT_STALE_DAYS,
    limit: int = DEFAULT_LIMIT,
) -> tuple[list[dict[str, Any]], int]:
    """Select a bounded stale queue, deduped by canonical sync id and source-diverse."""
    cutoff = as_of - timedelta(days=max(1, stale_days))
    deduped: dict[str, dict[str, Any]] = {}
    for state in states:
        sync_id = str(state.get("sync_id") or "")
        reviewed = _date_only(state.get("last_reviewed"))
        if not sync_id or reviewed is None or reviewed >= cutoff:
            continue
        current = deduped.get(sync_id)
        if current is None or _date_only(current.get("last_reviewed")) > reviewed:
            deduped[sync_id] = state

    stale = list(deduped.values())
    brief_ids = _brief_reference_ids(states)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for state in stale:
        buckets[source_bucket(state)].append(state)
    for rows in buckets.values():
        rows.sort(key=lambda s: _queue_priority(s, brief_ids))

    bucket_order = sorted(
        buckets,
        key=lambda bucket: (
            _queue_priority(buckets[bucket][0], brief_ids),
            bucket,
        ),
    )

    selected: list[dict[str, Any]] = []
    # First pass: one record per acquisition bucket.
    for bucket in bucket_order:
        if len(selected) >= limit:
            break
        if buckets[bucket]:
            selected.append(buckets[bucket].pop(0))

    # Fill remaining capacity globally by the same value/age policy.
    remainder = [row for rows in buckets.values() for row in rows]
    remainder.sort(key=lambda s: _queue_priority(s, brief_ids))
    selected.extend(remainder[: max(0, limit - len(selected))])
    return selected[: max(0, limit)], len(stale)


def protected_snapshot(state: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (
        state.get("last_reviewed"),
        state.get("score"),
        state.get("status"),
    )


def _split_evidence_urls(value: str) -> list[str]:
    return [x.strip() for x in str(value or "").splitlines() if x.strip()]


def build_repo_for_existing_evidence(state: dict[str, Any]) -> dict[str, Any]:
    evidence_urls = _split_evidence_urls(str(state.get("evidence") or ""))
    primary = str(state.get("primary_url") or "")
    if not primary and evidence_urls:
        primary = evidence_urls[0]
    sources = [str(x) for x in (state.get("sources") or []) if x]
    source = sources[0] if sources else source_bucket(state)
    return {
        "nameWithOwner": str(state.get("name") or "Existing paid decision record"),
        "description": str(state.get("plain_summary") or ""),
        "source": source,
        "primaryUrl": primary,
        "url": primary,
        "sourceContext": "",
        "sourceContextVerified": False,
        "sourceDetails": {},
        "canonicalEntityId": str(state.get("sync_id") or ""),
    }


def _live_verify_one(state: dict[str, Any]) -> dict[str, Any]:
    """Run the exact zero-model evidence preflight used before Product Review."""
    # Suppress existing source-resolver URL/name logs because this repository is public.
    logging.disable(logging.CRITICAL)
    import pipeline

    repo = build_repo_for_existing_evidence(state)
    if not repo["primaryUrl"]:
        return {"retrieved": False, "gate_pass": False, "result": "UNAVAILABLE"}

    try:
        source_info = pipeline.prepare_source_context(repo)
        evidence = pipeline.assess_evidence_sufficiency(source_info)
        if evidence.get("state") == pipeline.EVIDENCE_SUPPLEMENT_REQUIRED:
            source_info = pipeline.supplement_source_evidence(source_info)
            evidence = pipeline.assess_evidence_sufficiency(source_info)

        docs = source_info.get("evidence_documents") or []
        retrieved = any(bool(doc.get("retrieved")) for doc in docs)
        authority_failures = pipeline._primary_source_authority_failures(source_info)
        gate_pass = bool(
            retrieved
            and not authority_failures
            and evidence.get("state") != pipeline.EVIDENCE_INSUFFICIENT
            and evidence.get("decision_scope_safe")
        )
        return {
            "retrieved": retrieved,
            "gate_pass": gate_pass,
            "result": "PASS" if gate_pass else ("EVIDENCE_FAIL" if retrieved else "UNAVAILABLE"),
        }
    except Exception:
        return {"retrieved": False, "gate_pass": False, "result": "UNAVAILABLE"}


def run_verification_batch(
    selected: list[dict[str, Any]],
    verifier: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    counts = {
        "queue": len(selected),
        "retrieved": 0,
        "unavailable": 0,
        "evidence_pass": 0,
        "evidence_fail": 0,
        "model_calls": 0,
        "notion_writes": 0,
        "paid_detail_publications": 0,
    }
    for state in selected:
        try:
            result = verifier(state)
        except Exception:
            result = {"retrieved": False, "gate_pass": False, "result": "UNAVAILABLE"}
        if result.get("retrieved"):
            counts["retrieved"] += 1
        if result.get("result") == "PASS":
            counts["evidence_pass"] += 1
        elif result.get("result") == "EVIDENCE_FAIL":
            counts["evidence_fail"] += 1
        else:
            counts["unavailable"] += 1
    return counts


def _read_source_states() -> list[dict[str, Any]]:
    data_source_id = os.environ.get("NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID", "").strip()
    database_id = os.environ.get("NOTION_SUBSCRIBER_TECH_DATABASE_ID", "").strip()
    if not (data_source_id or database_id):
        raise RuntimeError("paid decision source DB is not configured")
    pages = decision_intelligence._query_external_db(
        data_source_id,
        database_id,
        max_records=5000,
    )
    return [
        state
        for state in (member._source_state(page) for page in pages)
        if state and state.get("sync_id")
    ]


def _install_notion_write_guard() -> None:
    """Allow Notion query POSTs but fail closed on all Notion mutation endpoints."""
    original_post = decision_intelligence.requests.post
    original_patch = decision_intelligence.requests.patch

    def guarded_post(url, *args, **kwargs):
        text = str(url)
        if text.startswith("https://api.notion.com/") and "/query" not in text:
            raise RuntimeError("Notion write blocked by Issue #668 dry-run guard")
        return original_post(url, *args, **kwargs)

    def guarded_patch(url, *args, **kwargs):
        if str(url).startswith("https://api.notion.com/"):
            raise RuntimeError("Notion write blocked by Issue #668 dry-run guard")
        return original_patch(url, *args, **kwargs)

    decision_intelligence.requests.post = guarded_post
    decision_intelligence.requests.patch = guarded_patch


def run_live(*, as_of: date, limit: int, stale_days: int) -> dict[str, Any]:
    if any(os.environ.get(key) for key in MODEL_ENV_KEYS):
        raise RuntimeError("model credential present; refusing zero-model dry run")

    _install_notion_write_guard()
    before_states = _read_source_states()
    selected, stale_count = select_diverse_stale_queue(
        before_states,
        as_of=as_of,
        stale_days=stale_days,
        limit=limit,
    )
    before = {str(s["sync_id"]): protected_snapshot(s) for s in selected}

    counts = run_verification_batch(selected, _live_verify_one)

    # Re-read the DB and prove the dry run did not alter protected decision state.
    after_states = _read_source_states()
    after_by_id = {str(s.get("sync_id") or ""): s for s in after_states}
    mutation_detected = 0
    missing_after = 0
    for sync_id, snap in before.items():
        current = after_by_id.get(sync_id)
        if current is None:
            missing_after += 1
            continue
        if protected_snapshot(current) != snap:
            mutation_detected += 1

    result = {
        "status": "PASS" if mutation_detected == 0 and missing_after == 0 else "FAIL_CLOSED",
        "scope": "issue_668_initial_read_only_rereview",
        "stale_records": stale_count,
        "source_buckets": len({source_bucket(s) for s in selected}),
        **counts,
        "protected_state_mutations": mutation_detected,
        "selected_missing_after_reread": missing_after,
        "prior_16_pass_reused": False,
        "review_dates_advanced": 0,
    }
    if result["status"] != "PASS":
        raise RuntimeError("protected paid decision state changed during read-only re-review")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS)
    parser.add_argument("--as-of", default="")
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc).date()
    result = run_live(
        as_of=as_of,
        limit=max(1, min(12, int(args.limit))),
        stale_days=max(1, int(args.stale_days)),
    )
    print("ISSUE_668_READ_ONLY_AGGREGATE " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
