#!/usr/bin/env python3
"""Run169.1 + Run271: efficient member-visible Decision Brief body sync.

Run169.1 removed per-child deletion for generated-only pages. Run271 removes the
larger steady-state cost: reading every generated body on every sync even when
only a handful of presentation rows changed.

Run271 contract:
1. The workflow records a UTC cutoff immediately before Presentation Sync.
2. In normal operation, only destination pages whose ``last_edited_time`` is at
   or after that cutoff are eligible for body reads/writes.
3. One deterministic sentinel body is checked every delta run. If the sentinel
   does not match the currently installed body contract, the run fails open to a
   full body scan/migration so presentation-contract changes cannot be skipped.
4. Push-triggered body-contract migrations and explicit recovery runs may force a
   full scan through ``MEMBER_BODY_FORCE_FULL``.
5. If no cutoff is supplied, legacy full-scan behavior is preserved.

Manual blocks remain protected by the existing conservative replacement path.
ZERO Gemini/model requests and no Notion schema change.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import member_presentation_body_sync as body
import member_presentation_sync as mps
import member_ux_guard as guard


CHANGED_SINCE_ENV = "MEMBER_BODY_CHANGED_SINCE"
FORCE_FULL_ENV = "MEMBER_BODY_FORCE_FULL"


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _page_last_edited(page: dict[str, Any]) -> datetime | None:
    return _parse_utc(page.get("last_edited_time"))


def _select_delta_pages(
    pages: list[dict[str, Any]],
    *,
    changed_since: str | None = None,
    force_full: bool | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return the pages that need body inspection plus auditable scope metadata."""
    if force_full is None:
        force_full = _truthy(os.environ.get(FORCE_FULL_ENV))
    cutoff_raw = changed_since if changed_since is not None else os.environ.get(CHANGED_SINCE_ENV)
    cutoff = _parse_utc(cutoff_raw)

    if force_full:
        return list(pages), {
            "mode": "full_forced",
            "cutoff": str(cutoff_raw or ""),
            "force_full": True,
        }
    if cutoff is None:
        return list(pages), {
            "mode": "full_no_cutoff",
            "cutoff": str(cutoff_raw or ""),
            "force_full": False,
        }

    selected = [
        page
        for page in pages
        if (edited := _page_last_edited(page)) is not None and edited >= cutoff
    ]
    return selected, {
        "mode": "delta",
        "cutoff": cutoff.isoformat().replace("+00:00", "Z"),
        "force_full": False,
    }


def _rename_generated_callout(block: dict[str, Any], state: dict[str, Any]) -> None:
    block_id = str(block.get("id") or "").strip()
    if not block_id:
        raise RuntimeError("Generated member callout is missing block id")
    res = body._request(
        "PATCH",
        f"https://api.notion.com/v1/blocks/{block_id}",
        json_payload={"callout": body._callout_data(state)},
    )
    if res.status_code != 200:
        raise RuntimeError(
            f"Member callout label update failed {block_id}: {res.status_code} {res.text[:500]}"
        )


def _rebuild_generated_only_page(
    page_id: str,
    generated_blocks: list[dict[str, Any]],
    state: dict[str, Any],
) -> int:
    removed = 0
    for block in generated_blocks:
        block_id = str(block.get("id") or "").strip()
        if block_id:
            body._delete_block(block_id)
            removed += 1
    body._create_auto_callout(page_id, state)
    return max(0, removed - 1)


def _sentinel_requires_full(page: dict[str, Any]) -> bool:
    """Detect a global body-contract migration without scanning the whole DB."""
    state = mps._destination_state(page)
    page_id = str(state.get("page_id") or page.get("id") or "").strip()
    if not page_id or not state.get("sync_id"):
        return True

    root_blocks = body._children(page_id)
    child_cache: dict[str, list[dict[str, Any]]] = {}
    generated_blocks = guard._generated_blocks(root_blocks, child_cache)
    if len(generated_blocks) != 1:
        return True

    first = generated_blocks[0]
    first_id = str(first.get("id") or "").strip()
    if not first_id:
        return True
    first_children = child_cache.get(first_id)
    if first_children is None:
        first_children = body._children(first_id)

    label_is_clean = body._block_text(first) == guard.VISIBLE_CALLOUT_LABEL
    body_matches = body._body_matches(first_children or [], state)
    return not (label_is_clean and body_matches)


def sync_member_page_bodies_fast() -> dict[str, Any]:
    if not body.decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY:
        raise ValueError("NOTION_DECISION_INTELLIGENCE_API_KEY is required")
    data_source_id = mps.NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID
    database_id = mps.NOTION_MEMBER_PRESENTATION_DATABASE_ID
    if not (data_source_id or database_id):
        raise ValueError("Member presentation DB is not configured")

    # All generated writes use the customer-safe visible label.
    body._auto_label = lambda _state: guard.VISIBLE_CALLOUT_LABEL

    pages = body.decision_intelligence._query_external_db(
        data_source_id, database_id, max_records=5000
    )
    target_pages, scope = _select_delta_pages(pages)
    sentinel_checked = 0
    delta_fallback_full = False

    # A code-level body contract change can leave every destination property
    # unchanged. Sample one canonical generated body before trusting the cutoff.
    if scope["mode"] == "delta" and pages:
        sentinel = next(
            (
                page
                for page in pages
                if str((mps._destination_state(page) or {}).get("sync_id") or "").strip()
            ),
            None,
        )
        if sentinel is not None:
            sentinel_checked = 1
            if _sentinel_requires_full(sentinel):
                target_pages = list(pages)
                delta_fallback_full = True
                scope = dict(scope)
                scope["mode"] = "full_contract_mismatch"

    unchanged = label_only = parent_rebuilt = fine_grained = created = 0
    duplicates_removed = manual_pages = 0

    for page in target_pages:
        state = mps._destination_state(page)
        page_id = str(state.get("page_id") or page.get("id") or "").strip()
        if not page_id or not state.get("sync_id"):
            continue

        root_blocks = body._children(page_id)
        child_cache: dict[str, list[dict[str, Any]]] = {}
        generated_blocks = guard._generated_blocks(root_blocks, child_cache)
        first = generated_blocks[0] if generated_blocks else None
        first_id = str((first or {}).get("id") or "").strip()
        first_children = child_cache.get(first_id) if first_id else None
        if first_children is None and first_id:
            first_children = body._children(first_id)

        body_matches = bool(first and body._body_matches(first_children or [], state))
        label_is_clean = bool(
            first and body._block_text(first) == guard.VISIBLE_CALLOUT_LABEL
        )

        if first and body_matches and label_is_clean:
            unchanged += 1
            for duplicate in generated_blocks[1:]:
                duplicate_id = str(duplicate.get("id") or "").strip()
                if duplicate_id:
                    body._delete_block(duplicate_id)
                    duplicates_removed += 1
            continue

        if first and body_matches:
            # Cosmetic migration only: never rewrite customer content that is
            # already correct merely to remove AUTO/hash from the heading.
            _rename_generated_callout(first, state)
            label_only += 1
            for duplicate in generated_blocks[1:]:
                duplicate_id = str(duplicate.get("id") or "").strip()
                if duplicate_id:
                    body._delete_block(duplicate_id)
                    duplicates_removed += 1
        elif first:
            non_generated = [b for b in root_blocks if b not in generated_blocks]
            if not non_generated:
                # Safe fast path: generated callout is the complete page body.
                duplicates_removed += _rebuild_generated_only_page(
                    page_id, generated_blocks, state
                )
                parent_rebuilt += 1
            else:
                # Manual notes exist; preserve their position/content exactly.
                body._replace_auto_callout(first, state)
                fine_grained += 1
                manual_pages += 1
                for duplicate in generated_blocks[1:]:
                    duplicate_id = str(duplicate.get("id") or "").strip()
                    if duplicate_id:
                        body._delete_block(duplicate_id)
                        duplicates_removed += 1
        else:
            if root_blocks:
                manual_pages += 1
            body._create_auto_callout(page_id, state)
            created += 1

        if body.REQUEST_SLEEP_SECONDS:
            body.time.sleep(body.REQUEST_SLEEP_SECONDS)

    return {
        "enabled": True,
        "zero_gemini_calls": True,
        "total": len(pages),
        "scanned_body_pages": len(target_pages),
        "skipped_by_delta": max(0, len(pages) - len(target_pages)),
        "delta_scope": scope,
        "sentinel_checked": sentinel_checked,
        "delta_fallback_full": delta_fallback_full,
        "unchanged": unchanged,
        "label_only": label_only,
        "parent_rebuilt": parent_rebuilt,
        "fine_grained": fine_grained,
        "created": created,
        "duplicates_removed": duplicates_removed,
        "manual_pages_preserved": manual_pages,
        "visible_callout_label": guard.VISIBLE_CALLOUT_LABEL,
    }


def main() -> int:
    print(json.dumps(sync_member_page_bodies_fast(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
