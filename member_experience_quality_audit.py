"""Read-only quality audit for the paid Decision DB customer experience.

The current Run307 body renderer already has a safe generated-callout cleanup
path in an explicit full Member Presentation Sync. The routine delta path
inspects just changed pages + one sentinel; it cannot certify the remaining
catalogue free of old duplicate callouts. This independent audit scans them
all without deleting *anything*, distinguishes manual/ambiguous blocks and
never infers evidence freshness from Notion's UI edit timestamp.

Usage (explicit; no schedule): python member_experience_quality_audit.py --read-only
Requires canonical Notion read credentials. Gemini/model API is not used.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import member_presentation_body_sync as body
import member_presentation_sync as mps
import member_ux_guard as guard
import run219_member_human_language_ui as run219

CANONICAL_DB = "b2787ee0-5b58-4ca7-b4eb-774f60237f1f"
CANONICAL_SOURCE = "7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404"
CURRENT_LABEL = run219.NEW_VISIBLE_CALLOUT_LABEL
LEGACY_LABEL = run219.PREVIOUS_VISIBLE_CALLOUT_LABEL
AUDIT_MAX_ROWS = 5000


def _as_date(raw: Any):
    text = str(raw or "").strip()
    try:
        return datetime.fromisoformat(text[:10]).date() if len(text) >= 10 else None
    except ValueError:
        return None


def inspect(
    pages: list[dict[str, Any]],
    read_children,
    *,
    today=None,
) -> dict[str, Any]:
    from datetime import date
    now = today or datetime.now(timezone(timedelta(hours=9))).date()
    result: dict[str, Any] = {
        "status": "READ_ONLY",
        "customer_database": CANONICAL_DB,
        "review_date": now.isoformat(),
        "page_count": len(pages),
        "duplicates_confirmed": [],
        "same_label_unclassified": [],
        "source_review_older_than_30_days": [],
        "missing_source_review_date": [],
        "no_visible_generated_body": [],
        "read_only": True,
        "gemini_provider_calls": 0,
    }
    for page in pages:
        state = mps._destination_state(page)
        page_id = str(state.get("page_id") or "").strip()
        if not page_id or not str(state.get("sync_id") or "").strip():
            continue
        name = str(state.get("name") or "").strip()
        review = _as_date(state.get("last_reviewed"))
        reference = {"name": name, "page_id": page_id}
        if review is None:
            result["missing_source_review_date"].append(reference)
        elif (now - review).days > 30:
            result["source_review_older_than_30_days"].append({
                **reference, "last_reviewed": review.isoformat(),
                "age_days": (now - review).days,
            })

        roots = read_children(page_id)
        cache: dict[str, list[dict[str, Any]]] = {}
        # The classifier is the installed/current Run219 production recognizer,
        # not label-only deletion. Manual callouts with the same title must not
        # be assumed safe to remove.
        candidates = [
            b for b in roots if b.get("type") == "callout"
            and body._block_text(b) in {CURRENT_LABEL, LEGACY_LABEL}
        ]
        known = []
        # Shared injected reader is used for both root and child blocks, so
        # tests are offline and live audits stay inside one read-only client.
        for candidate in candidates:
            block_id = str(candidate.get("id") or "")
            if block_id:
                cache[block_id] = read_children(block_id)
        for block in roots:
            label = body._block_text(block)
            if block.get("type") != "callout":
                continue
            if label.startswith(body.AUTO_PREFIX) or run219._looks_like_generated_member_callout(block, cache):
                known.append(block)
        unclassified = [b for b in candidates if b not in known]
        if unclassified:
            result["same_label_unclassified"].append({**reference, "count": len(unclassified)})
        if len(known) > 1:
            result["duplicates_confirmed"].append({**reference, "count": len(known)})
        if not known and not candidates:
            result["no_visible_generated_body"].append(reference)

    result["counts"] = {
        k: len(result[k]) for k in (
            "duplicates_confirmed", "same_label_unclassified",
            "source_review_older_than_30_days", "missing_source_review_date",
            "no_visible_generated_body",
        )
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args()
    if not args.read_only:
        raise RuntimeError("Explicit read-only mode is required")
    if not body.decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY:
        raise RuntimeError("Authoritative Notion read credential required")
    if (
        mps.NOTION_MEMBER_PRESENTATION_DATABASE_ID != CANONICAL_DB
        or mps.NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID != CANONICAL_SOURCE
    ):
        raise RuntimeError("Refusing noncanonical paid member DB")
    pages = body.decision_intelligence._query_external_db(
        CANONICAL_SOURCE, CANONICAL_DB, max_records=AUDIT_MAX_ROWS
    )
    # No snapshots imply a wrong/inaccessible database, not a clean audit.
    if not pages or len(pages) >= AUDIT_MAX_ROWS:
        raise RuntimeError("Audit needs a complete, bounded canonical DB snapshot")
    report = inspect(pages, body._children)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
