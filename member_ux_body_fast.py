#!/usr/bin/env python3
"""Run169.1: efficient migration of member-visible Decision Brief bodies.

The original body sync rewrites every child block when a generated callout label
changes. For a catalog-sized migration that turns one cosmetic change into
thousands of Notion API requests. This wrapper keeps the same customer contract
while applying the smallest safe mutation:

1. Body already matches -> rename only the generated callout label.
2. Body differs and the page contains only generated callouts -> archive the
   generated parent block(s) and recreate one clean block (children disappear
   with the parent; no per-child delete loop).
3. Manual blocks coexist -> retain the conservative fine-grained replacement so
   manual ordering/content is preserved.
4. Partial/interrupted generated bodies are treated as mismatches and rebuilt.

ZERO Gemini/model requests.
"""
from __future__ import annotations

import json
from typing import Any

import member_presentation_body_sync as body
import member_presentation_sync as mps
import member_ux_guard as guard


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
    unchanged = label_only = parent_rebuilt = fine_grained = created = 0
    duplicates_removed = manual_pages = 0

    for page in pages:
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
