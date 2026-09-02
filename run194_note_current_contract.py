#!/usr/bin/env python3
"""Publish only complete Ready material produced by the current publication policy.

The note draft workflow is zero-Gemini and never regenerates content.  It therefore requires:
- a Ready block whose automatic policy fingerprint matches the checked-out production code;
- a manuscript SHA in the caption that matches the actual persisted body;
- the latest valid current-policy block when several historical regenerations exist;
- a source eyecatch before a row may reach browser mutation.

Automatic selection may skip stale/incomplete rows and continue.  Explicit sync_id requests
remain fail-closed and never silently switch to another article.  Public release remains human-only.
"""
from __future__ import annotations

from typing import Any

import note_draft_automation as base
import publication_contract as contract
import run185_note_ready_legacy_skip as run185


class StalePublicationContract(base.NoteDraftError):
    """A Ready row does not contain a byte-valid manuscript from the current policy."""


class IncompletePublicationAsset(base.NoteDraftError):
    """A current manuscript is missing a required public asset such as the eyecatch."""


def _manuscript_from_blocks(blocks: list[dict]) -> str:
    current_bodies: list[str] = []
    stale_ready_seen = False

    for block in blocks:
        parsed = base._code_block_text(block)
        if parsed is None:
            continue
        body, caption = parsed
        if not body:
            continue
        if contract.is_current_ready_block(body, caption):
            current_bodies.append(body)
            continue
        # Captionless Ready blocks, old contract versions, and current-policy captions whose
        # manuscript hash no longer matches the stored body are all stale for publication.
        if not str(caption or "").strip() or contract.is_ready_family_caption(caption):
            stale_ready_seen = True

    manuscript = (current_bodies[-1] if current_bodies else "").strip()
    if len(manuscript) < 200:
        if stale_ready_seen:
            raise StalePublicationContract(
                "Ready manuscript predates or violates the current publication contract and must be regenerated"
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
        raise IncompletePublicationAsset(
            "Current Ready article has no eyecatch in Content Intelligence"
        )

    prepared = dict(candidate)
    prepared["manuscript"] = manuscript
    prepared["eyecatch_url"] = image_url
    prepared["publication_contract"] = contract.CONTRACT_ID
    prepared["publication_policy_sha256"] = contract.policy_sha256()
    prepared["manuscript_sha256"] = contract.manuscript_sha256(manuscript)
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
    asset_skipped = 0
    paid_marker_skipped = 0

    for candidate in candidates:
        try:
            prepared = _prepare_one(candidate)
        except StalePublicationContract:
            if explicit:
                raise
            stale_skipped += 1
            print(
                "[RUN195 NOTE DRAFT] skipped stale publication-contract Ready article "
                f"sync_id={candidate['sync_id'][:8]}"
            )
            continue
        except IncompletePublicationAsset:
            if explicit:
                raise
            asset_skipped += 1
            print(
                "[RUN195 NOTE DRAFT] skipped current Ready article with incomplete public assets "
                f"sync_id={candidate['sync_id'][:8]}"
            )
            continue
        except run185.UnsafeLegacyPaidMarker:
            if explicit:
                raise
            paid_marker_skipped += 1
            print(
                "[RUN195 NOTE DRAFT] skipped paid-marker Ready article "
                f"sync_id={candidate['sync_id'][:8]}"
            )
            continue

        prepared["skipped_stale_contract_count"] = stale_skipped
        prepared["skipped_incomplete_asset_count"] = asset_skipped
        prepared["skipped_legacy_paid_marker_count"] = paid_marker_skipped
        return prepared

    raise base.NoteDraftError(
        "No complete current publication-contract Ready article is available "
        f"(stale_skipped={stale_skipped}, asset_skipped={asset_skipped}, "
        f"paid_marker_skipped={paid_marker_skipped})"
    )


def install() -> None:
    run185.install()
    base._manuscript_from_blocks = _manuscript_from_blocks
    base._prepare_article = _prepare_article


def main() -> None:
    install()
    base.main()


if __name__ == "__main__":
    main()
