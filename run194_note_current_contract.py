#!/usr/bin/env python3
"""Run194: publish only Ready manuscripts produced by the current production contract.

The note draft workflow is intentionally zero-Gemini and never regenerates content.  It must
therefore distinguish current Ready inventory from historical Ready rows that predate later
article-quality and eyecatch policy layers.

Automatic selection skips stale publication-contract rows and continues to the next candidate.
An explicit sync_id remains fail-closed and never silently switches articles.  The historical
paid-area marker guard from Run185 remains active.  No public-release action is added.
"""
from __future__ import annotations

from typing import Any

import note_draft_automation as base
import publication_contract as contract
import run185_note_ready_legacy_skip as run185


class StalePublicationContract(base.NoteDraftError):
    """A Ready row does not contain a manuscript from the current production contract."""


def _manuscript_from_blocks(blocks: list[dict]) -> str:
    current_chunks: list[str] = []
    stale_ready_seen = False

    for block in blocks:
        parsed = base._code_block_text(block)
        if parsed is None:
            continue
        body, caption = parsed
        if not body:
            continue
        if contract.is_current_ready_caption(caption):
            current_chunks.append(body)
            continue
        # Captionless Ready blocks and any prior Ready-family version are historical.
        if not str(caption or "").strip() or contract.is_ready_family_caption(caption):
            stale_ready_seen = True

    manuscript = "".join(current_chunks).strip()
    if len(manuscript) < 200:
        if stale_ready_seen:
            raise StalePublicationContract(
                "Ready manuscript predates the current publication contract and must be regenerated"
            )
        raise base.NoteDraftError("Current Ready manuscript is missing or unexpectedly short")

    if run185._contains_paid_control_marker(manuscript):
        raise run185.UnsafeLegacyPaidMarker(
            "Current Ready manuscript still contains a historical paid-area control marker"
        )
    return manuscript


def _prepare_one(candidate: dict[str, Any]) -> dict[str, Any]:
    source_page = base._fetch_source_page(candidate["sync_id"])
    manuscript = _manuscript_from_blocks(base._fetch_block_children(candidate["sync_id"]))
    image_url = base._eyecatch_url(source_page)
    if not image_url:
        raise base.NoteDraftError("Current Ready article has no eyecatch in Content Intelligence")

    prepared = dict(candidate)
    prepared["manuscript"] = manuscript
    prepared["eyecatch_url"] = image_url
    prepared["publication_contract"] = contract.CONTRACT_ID
    return prepared


def _prepare_article(requested_sync_id: str = "") -> dict[str, Any]:
    if not base.ready_sync.NOTION_API_KEY:
        raise base.NoteDraftError("Notion API key is not configured")
    if not (base.ready_sync.DEST_DATA_SOURCE_ID or base.ready_sync.DEST_DATABASE_ID):
        raise base.NoteDraftError("note Ready DB is not configured")

    candidates = run185._ordered_candidates(
        base._query_ready_queue(), requested_sync_id=requested_sync_id
    )
    explicit = bool(base._normalize_sync_id(requested_sync_id))
    stale_skipped = 0
    paid_marker_skipped = 0

    for candidate in candidates:
        try:
            prepared = _prepare_one(candidate)
        except StalePublicationContract:
            if explicit:
                raise
            stale_skipped += 1
            print(
                "[RUN194 NOTE DRAFT] skipped stale publication-contract Ready article "
                f"sync_id={candidate['sync_id'][:8]}"
            )
            continue
        except run185.UnsafeLegacyPaidMarker:
            if explicit:
                raise
            paid_marker_skipped += 1
            print(
                "[RUN194 NOTE DRAFT] skipped paid-marker Ready article "
                f"sync_id={candidate['sync_id'][:8]}"
            )
            continue

        prepared["skipped_stale_contract_count"] = stale_skipped
        prepared["skipped_legacy_paid_marker_count"] = paid_marker_skipped
        return prepared

    raise base.NoteDraftError(
        "No current publication-contract Ready article is available "
        f"(stale_skipped={stale_skipped}, paid_marker_skipped={paid_marker_skipped})"
    )


def install() -> None:
    # Install Run185 first so its paid-control-line detection stays authoritative, then replace
    # only the manuscript/current-contract selection surface.
    run185.install()
    base._manuscript_from_blocks = _manuscript_from_blocks
    base._prepare_article = _prepare_article


def main() -> None:
    install()
    base.main()


if __name__ == "__main__":
    main()
