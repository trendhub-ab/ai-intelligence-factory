#!/usr/bin/env python3
"""Issue #668 stage 2: bounded verified one-shot Product Review apply.

This module connects the already-merged read-only re-review lane to the
authoritative Product Review persistence path without creating a second
review-date writer.

Safety contract:
- real source retrieval + existing Evidence gate happens first;
- only Evidence PASS candidates enter the Product Review allowlist;
- the allowlist is deduped and capped at two records;
- the existing Product Review path owns review date / score / status / history;
- unavailable and Evidence-failed candidates must remain unchanged;
- any mutation outside the verified allowlist fails closed;
- public output is aggregate-only;
- no schedule or Daily workflow is introduced here.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any, Callable

import daily_portfolio_review
import member_verified_rereview_dryrun as rr


HARD_MAX_REVIEWS = 2
HARD_REQUEST_BUDGET = 5


def validate_apply_budget(*, max_reviews: int, request_budget: int) -> None:
    if int(max_reviews) < 1 or int(max_reviews) > HARD_MAX_REVIEWS:
        raise ValueError(f"max reviews must be between 1 and {HARD_MAX_REVIEWS}")
    if int(request_budget) < 1 or int(request_budget) > HARD_REQUEST_BUDGET:
        raise ValueError(f"request budget must be between 1 and {HARD_REQUEST_BUDGET}")


def build_verified_allowlist(
    selected: list[dict[str, Any]],
    verifier: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    limit: int = HARD_MAX_REVIEWS,
) -> dict[str, Any]:
    cap = max(0, min(HARD_MAX_REVIEWS, int(limit)))
    allowlist: list[str] = []
    counts = {
        "verified": 0,
        "unavailable": 0,
        "evidence_fail": 0,
    }

    for state in selected:
        try:
            result = verifier(state)
        except Exception:
            result = {"retrieved": False, "gate_pass": False, "result": "UNAVAILABLE"}

        outcome = str(result.get("result") or "")
        if (
            outcome == "PASS"
            and bool(result.get("retrieved"))
            and bool(result.get("gate_pass"))
        ):
            sync_id = str(state.get("sync_id") or "")
            if sync_id and sync_id not in allowlist and len(allowlist) < cap:
                allowlist.append(sync_id)
                counts["verified"] += 1
        elif outcome == "EVIDENCE_FAIL":
            counts["evidence_fail"] += 1
        else:
            counts["unavailable"] += 1

    return {"allowlist": allowlist, **counts}


def _state_map(states: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(state.get("sync_id") or ""): state
        for state in states
        if str(state.get("sync_id") or "")
    }


def _protected_changed(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> bool:
    if before is None or after is None:
        return before is not after
    return rr.protected_snapshot(before) != rr.protected_snapshot(after)


def _verify_postconditions(
    *,
    before_states: list[dict[str, Any]],
    after_states: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    allowlist: list[str],
) -> dict[str, int]:
    before = _state_map(before_states)
    after = _state_map(after_states)
    allowed = set(allowlist)
    selected_ids = {
        str(state.get("sync_id") or "")
        for state in selected
        if str(state.get("sync_id") or "")
    }
    unverified_selected = selected_ids - allowed

    for sync_id in sorted(unverified_selected):
        if _protected_changed(before.get(sync_id), after.get(sync_id)):
            raise RuntimeError("unverified candidate changed during verified apply")

    out_of_allowlist_mutations = 0
    for sync_id in sorted(set(before) | set(after)):
        if sync_id in allowed:
            continue
        if _protected_changed(before.get(sync_id), after.get(sync_id)):
            out_of_allowlist_mutations += 1

    if out_of_allowlist_mutations:
        raise RuntimeError("protected state changed outside verified allowlist")

    allowed_mutations = sum(
        1
        for sync_id in allowed
        if _protected_changed(before.get(sync_id), after.get(sync_id))
    )
    return {
        "allowed_mutations": allowed_mutations,
        "out_of_allowlist_mutations": 0,
        "unverified_mutations": 0,
    }


def execute_verified_apply(
    *,
    selected: list[dict[str, Any]],
    verifier: Callable[[dict[str, Any]], dict[str, Any]],
    before_states: list[dict[str, Any]],
    reread_states: Callable[[], list[dict[str, Any]]],
    product_runner: Callable[[list[str], int, int], dict[str, Any]],
    max_reviews: int = HARD_MAX_REVIEWS,
    request_budget: int = HARD_REQUEST_BUDGET,
) -> dict[str, Any]:
    validate_apply_budget(max_reviews=max_reviews, request_budget=request_budget)

    verified = build_verified_allowlist(selected, verifier, limit=max_reviews)
    allowlist = list(verified["allowlist"])

    if not allowlist:
        after_states = reread_states()
        post = _verify_postconditions(
            before_states=before_states,
            after_states=after_states,
            selected=selected,
            allowlist=[],
        )
        return {
            "status": "PASS",
            "scope": "issue_668_stage2_verified_apply",
            "skipped": True,
            "reason": "no_verified_candidates",
            "selected_count": len(selected),
            "allowlist_count": 0,
            "verified": int(verified["verified"]),
            "unavailable": int(verified["unavailable"]),
            "evidence_fail": int(verified["evidence_fail"]),
            "max_reviews": int(max_reviews),
            "request_budget": int(request_budget),
            **post,
        }

    effective_reviews = min(int(max_reviews), len(allowlist))
    runner_result = product_runner(allowlist, effective_reviews, int(request_budget))
    after_states = reread_states()
    post = _verify_postconditions(
        before_states=before_states,
        after_states=after_states,
        selected=selected,
        allowlist=allowlist,
    )

    return {
        "status": "PASS",
        "scope": "issue_668_stage2_verified_apply",
        "skipped": bool((runner_result or {}).get("skipped")),
        "selected_count": len(selected),
        "allowlist_count": len(allowlist),
        "verified": int(verified["verified"]),
        "unavailable": int(verified["unavailable"]),
        "evidence_fail": int(verified["evidence_fail"]),
        "max_reviews": effective_reviews,
        "request_budget": int(request_budget),
        **post,
    }


def run_live(
    *,
    as_of: date,
    queue_limit: int = rr.DEFAULT_LIMIT,
    stale_days: int = rr.DEFAULT_STALE_DAYS,
    max_reviews: int = HARD_MAX_REVIEWS,
    request_budget: int = HARD_REQUEST_BUDGET,
) -> dict[str, Any]:
    validate_apply_budget(max_reviews=max_reviews, request_budget=request_budget)

    before_states = rr._read_source_states()
    selected, stale_count = rr.select_diverse_stale_queue(
        before_states,
        as_of=as_of,
        stale_days=stale_days,
        limit=queue_limit,
    )

    result = execute_verified_apply(
        selected=selected,
        verifier=rr._live_verify_one,
        before_states=deepcopy(before_states),
        reread_states=rr._read_source_states,
        product_runner=daily_portfolio_review._run_product_only,
        max_reviews=max_reviews,
        request_budget=request_budget,
    )
    result["stale_records"] = stale_count
    result["source_buckets"] = len({rr.source_bucket(state) for state in selected})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue-limit", type=int, default=rr.DEFAULT_LIMIT)
    parser.add_argument("--stale-days", type=int, default=rr.DEFAULT_STALE_DAYS)
    parser.add_argument("--max-reviews", type=int, default=HARD_MAX_REVIEWS)
    parser.add_argument("--request-budget", type=int, default=HARD_REQUEST_BUDGET)
    parser.add_argument("--as-of", default="")
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc).date()
    result = run_live(
        as_of=as_of,
        queue_limit=max(1, min(12, int(args.queue_limit))),
        stale_days=max(1, int(args.stale_days)),
        max_reviews=int(args.max_reviews),
        request_budget=int(args.request_budget),
    )
    print("ISSUE_668_STAGE2_AGGREGATE " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
