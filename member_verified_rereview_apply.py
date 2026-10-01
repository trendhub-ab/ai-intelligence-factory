#!/usr/bin/env python3
"""Issue #668 stage 2: bounded verified write one-shot.

Safety contract:
- queue comes from the existing paid Subscriber decision DB and is capped;
- canonical Technology Intelligence state is authoritative;
- only records that re-fetch primary material and PASS the existing zero-model
  Evidence preflight may advance the review date;
- unavailable/failed records keep their original review date and receive only a
  private retry reason on the internal Technology record;
- adoption score/status, evidence URLs, copy, and model-backed decisions are never
  mutated by this stage;
- successful canonical writes are mirrored to the matching Subscriber row only
  after canonical state is safely updated;
- public output is aggregate-only and contains no names, IDs, URLs, or extracts.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from typing import Any

import requests

import decision_intelligence as di
import member_presentation_sync as member
import member_verified_rereview_dryrun as dry


RETRY_PROP = "再検証再試行理由（内部）"
DEFAULT_LIMIT = 5
DEFAULT_STALE_DAYS = 30
MODEL_ENV_KEYS = dry.MODEL_ENV_KEYS


def _rt(value: str) -> dict[str, Any]:
    value = str(value or "")[:1800]
    if not value:
        return {"rich_text": []}
    return {"rich_text": [{"type": "text", "text": {"content": value}}]}


def _date_prop(value: str | None) -> dict[str, Any]:
    return {"date": {"start": value}} if value else {"date": None}


def _source_snapshot(state: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (state.get("last_reviewed"), state.get("score"), state.get("status"))


def _internal_snapshot(state: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (state.get("last_reviewed"), state.get("adoption_score"), state.get("adoption_status"))


def _ensure_retry_property() -> bool:
    ds = str(di.NOTION_TECH_DATA_SOURCE_ID or "").strip()
    if not ds:
        raise RuntimeError("NOTION_TECH_DATA_SOURCE_ID missing")
    url = f"https://api.notion.com/v1/data_sources/{ds}"
    r = requests.get(url, headers=di._headers(), timeout=15)
    r.raise_for_status()
    props = r.json().get("properties") or {}
    if RETRY_PROP in props:
        actual = (props.get(RETRY_PROP) or {}).get("type")
        if actual != "rich_text":
            raise RuntimeError(f"{RETRY_PROP} type mismatch: {actual}")
        return False
    u = requests.patch(
        url,
        headers=di._headers(),
        json={"properties": {RETRY_PROP: {"rich_text": {}}}},
        timeout=20,
    )
    u.raise_for_status()
    return True


def _read_subscriber_states() -> list[dict[str, Any]]:
    ds = str(di.NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID or "").strip()
    db = str(di.NOTION_SUBSCRIBER_TECH_DATABASE_ID or "").strip()
    if not (ds or db):
        raise RuntimeError("Subscriber Technology DB is not configured")
    pages = di._query_external_db(ds, db, max_records=5000)
    rows: list[dict[str, Any]] = []
    for page in pages:
        state = member._source_state(page)
        if not state or not state.get("sync_id"):
            continue
        state = dict(state)
        state["page_id"] = str(page.get("id") or "")
        rows.append(state)
    return rows


def _get_page(page_id: str) -> dict[str, Any]:
    r = requests.get(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=di._headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def _retry_code(state: dict[str, Any], verification: dict[str, Any]) -> str:
    repo = dry.build_repo_for_existing_evidence(state)
    if not repo.get("primaryUrl"):
        return "MISSING_PRIMARY_SOURCE"
    if verification.get("result") == "EVIDENCE_FAIL":
        return "EVIDENCE_GATE_FAILED"
    return "PRIMARY_SOURCE_UNAVAILABLE"


def _private_retry_text(code: str, at: str) -> str:
    return f"{at} {code}"


def _patch_internal_retry(page_id: str, code: str, verified_at: str) -> None:
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=di._headers(),
        json={"properties": {RETRY_PROP: _rt(_private_retry_text(code, verified_at))}},
        timeout=15,
    )
    r.raise_for_status()


def _patch_internal_success(page_id: str, verified_at: str) -> None:
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=di._headers(),
        json={
            "properties": {
                di.TECH_PROP_LAST_REVIEWED: _date_prop(verified_at),
                RETRY_PROP: _rt(""),
            }
        },
        timeout=15,
    )
    r.raise_for_status()


def _patch_subscriber_review_date(page_id: str, verified_at: str) -> None:
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=di._headers(),
        json={"properties": {di.SUB_PROP_LAST_REVIEWED: _date_prop(verified_at)}},
        timeout=15,
    )
    r.raise_for_status()


def _canonical_state(entity_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    page = di.get_technology_record_by_entity_id(entity_id)
    if not page:
        return None, None
    return page, di.technology_page_to_state(page)


def _canonical_matches_subscriber(internal: dict[str, Any], subscriber: dict[str, Any]) -> bool:
    return (
        internal.get("last_reviewed") == subscriber.get("last_reviewed")
        and internal.get("adoption_score") == subscriber.get("score")
        and internal.get("adoption_status") == subscriber.get("status")
    )


def run_apply(*, as_of: date, limit: int, stale_days: int, verified_at: str) -> dict[str, Any]:
    if any(os.environ.get(key) for key in MODEL_ENV_KEYS):
        raise RuntimeError("model credential present; refusing zero-model stage-2 write")
    if not di.ENABLE_DECISION_INTELLIGENCE_DB:
        raise RuntimeError("ENABLE_DECISION_INTELLIGENCE_DB must be true")
    if not di.NOTION_DECISION_INTELLIGENCE_API_KEY:
        raise RuntimeError("NOTION_DECISION_INTELLIGENCE_API_KEY missing")

    schema_added = _ensure_retry_property()
    subscriber_states = _read_subscriber_states()
    selected, stale_count = dry.select_diverse_stale_queue(
        subscriber_states,
        as_of=as_of,
        stale_days=stale_days,
        limit=limit,
    )

    out = {
        "status": "PASS",
        "scope": "issue_668_stage2_small_write",
        "stale_records_before": stale_count,
        "queue": len(selected),
        "source_buckets": len({dry.source_bucket(s) for s in selected}),
        "evidence_pass": 0,
        "unavailable": 0,
        "evidence_fail": 0,
        "canonical_missing": 0,
        "canonical_mismatch": 0,
        "canonical_dates_advanced": 0,
        "subscriber_dates_advanced": 0,
        "subscriber_sync_deferred": 0,
        "retry_reasons_written": 0,
        "protected_state_mutations": 0,
        "schema_added": bool(schema_added),
        "model_calls": 0,
        "decision_mutations": 0,
        "score_mutations": 0,
        "notion_writes": 1 if schema_added else 0,
        "paid_detail_publications": 0,
    }

    for selected_state in selected:
        entity_id = str(selected_state.get("sync_id") or "")
        sub_page_id = str(selected_state.get("page_id") or "")
        if not entity_id or not sub_page_id:
            out["canonical_missing"] += 1
            continue

        internal_page, internal_state = _canonical_state(entity_id)
        if not internal_page or not internal_state:
            out["canonical_missing"] += 1
            continue
        internal_page_id = str(internal_page.get("id") or "")
        if not _canonical_matches_subscriber(internal_state, selected_state):
            out["canonical_mismatch"] += 1
            continue

        initial_internal_snapshot = _internal_snapshot(internal_state)
        initial_sub_snapshot = _source_snapshot(selected_state)

        verification = dry._live_verify_one(selected_state)
        result = str(verification.get("result") or "UNAVAILABLE")
        if result == "PASS":
            out["evidence_pass"] += 1
        elif result == "EVIDENCE_FAIL":
            out["evidence_fail"] += 1
        else:
            out["unavailable"] += 1

        # Re-read canonical state after network verification so a concurrent Daily
        # update cannot be overwritten by this one-shot.
        current_internal_page, current_internal_state = _canonical_state(entity_id)
        if not current_internal_page or not current_internal_state:
            out["canonical_missing"] += 1
            continue
        if _internal_snapshot(current_internal_state) != initial_internal_snapshot:
            out["canonical_mismatch"] += 1
            continue

        if result != "PASS":
            code = _retry_code(selected_state, verification)
            _patch_internal_retry(internal_page_id, code, verified_at)
            out["retry_reasons_written"] += 1
            out["notion_writes"] += 1

            after_page, after_state = _canonical_state(entity_id)
            if not after_page or not after_state or _internal_snapshot(after_state) != initial_internal_snapshot:
                out["protected_state_mutations"] += 1
                out["status"] = "FAIL_CLOSED"
            continue

        # PASS: advance only the canonical review date and clear any old retry reason.
        _patch_internal_success(internal_page_id, verified_at)
        out["canonical_dates_advanced"] += 1
        out["notion_writes"] += 1

        after_internal_page, after_internal_state = _canonical_state(entity_id)
        expected_internal = (verified_at, initial_internal_snapshot[1], initial_internal_snapshot[2])
        if (
            not after_internal_page
            or not after_internal_state
            or _internal_snapshot(after_internal_state) != expected_internal
        ):
            out["protected_state_mutations"] += 1
            out["status"] = "FAIL_CLOSED"
            continue

        # Mirror the genuine review date to the sanitized paid source only if its
        # pre-write state still matches the selected snapshot.
        current_sub_page = _get_page(sub_page_id)
        current_sub_state = member._source_state(current_sub_page)
        if not current_sub_state or _source_snapshot(current_sub_state) != initial_sub_snapshot:
            out["subscriber_sync_deferred"] += 1
            continue

        _patch_subscriber_review_date(sub_page_id, verified_at)
        out["subscriber_dates_advanced"] += 1
        out["notion_writes"] += 1

        after_sub_page = _get_page(sub_page_id)
        after_sub_state = member._source_state(after_sub_page)
        expected_sub = (verified_at, initial_sub_snapshot[1], initial_sub_snapshot[2])
        if not after_sub_state or _source_snapshot(after_sub_state) != expected_sub:
            out["protected_state_mutations"] += 1
            out["status"] = "FAIL_CLOSED"

    if out["protected_state_mutations"]:
        raise RuntimeError("protected decision state changed during Issue #668 stage-2 write")

    # Recount backlog from the paid source after successful mirrored writes.
    after_states = _read_subscriber_states()
    _, stale_after = dry.select_diverse_stale_queue(
        after_states,
        as_of=as_of,
        stale_days=stale_days,
        limit=max(1, limit),
    )
    out["stale_records_after"] = stale_after
    out["backlog_reduced_by"] = max(0, stale_count - stale_after)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS)
    parser.add_argument("--as-of", default="")
    args = parser.parse_args()
    if not args.apply:
        raise RuntimeError("explicit --apply is required")
    as_of = date.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc).date()
    verified_at = datetime.now(timezone.utc).isoformat()
    result = run_apply(
        as_of=as_of,
        limit=max(1, min(5, int(args.limit))),
        stale_days=max(1, int(args.stale_days)),
        verified_at=verified_at,
    )
    print("ISSUE_668_STAGE2_AGGREGATE " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
