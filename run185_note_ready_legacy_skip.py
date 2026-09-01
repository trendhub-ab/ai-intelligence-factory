#!/usr/bin/env python3
"""Run185: keep note draft automation fail-closed while skipping legacy paid-marker Ready rows.

The first Run184 prepare-only production check found an older Ready manuscript that still
contained the historical paid-area control marker. Publishing across that marker would be
unsafe because it can denote material that was previously intended to sit behind a paywall.

Run185 therefore:
- keeps explicit sync_id requests fail-closed;
- for automatic selection only, skips legacy Ready rows containing an actual control-marker
  line and tries the next eligible Ready row;
- narrows marker detection to control lines instead of rejecting ordinary editorial prose
  that merely contains the words "有料エリア";
- never mutates skipped queue rows;
- adds no Gemini/model calls and does not change the human-only public release boundary.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import note_draft_automation as base


class UnsafeLegacyPaidMarker(base.NoteDraftError):
    """A Ready manuscript contains a historical paywall control marker."""


_DECORATION_RE = re.compile(r"[\s\-‐‑‒–—―_=＊*#・:：|/\\\[\]()（）【】<>＜＞]+")


def _is_paid_control_line(line: str) -> bool:
    normalized = _DECORATION_RE.sub("", str(line or ""))
    return normalized in {"有料エリア", "ここから有料エリア", "以下有料エリア"}


def _contains_paid_control_marker(manuscript: str) -> bool:
    return any(_is_paid_control_line(line) for line in str(manuscript or "").splitlines())


def _manuscript_from_blocks(blocks: list[dict]) -> str:
    """Read the persisted Ready manuscript and reject only real paywall control lines."""
    ready_chunks: list[str] = []
    legacy_chunks: list[str] = []
    for block in blocks:
        parsed = base._code_block_text(block)
        if parsed is None:
            continue
        body, caption = parsed
        if not body:
            continue
        if caption == base.READY_CAPTION:
            ready_chunks.append(body)
        elif not caption:
            legacy_chunks.append(body)

    manuscript = "".join(ready_chunks or legacy_chunks).strip()
    if len(manuscript) < 200:
        raise base.NoteDraftError("Ready manuscript is missing or unexpectedly short")
    if _contains_paid_control_marker(manuscript):
        raise UnsafeLegacyPaidMarker(
            "Ready manuscript still contains a historical paid-area control marker"
        )
    return manuscript


def _ordered_candidates(pages: list[dict], requested_sync_id: str = "") -> list[dict[str, Any]]:
    requested = base._normalize_sync_id(requested_sync_id)
    candidates = [item for item in (base._candidate_from_page(page) for page in pages) if item]

    if requested:
        matches = [item for item in candidates if item["sync_id"] == requested]
        if len(matches) != 1:
            raise base.NoteDraftError(
                "Requested sync_id is not exactly one Ready / 投稿待ち article"
            )
        return matches

    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    eligible: list[dict[str, Any]] = []
    for item in candidates:
        scheduled = base._parse_iso_date(item["scheduled_date"])
        if scheduled is not None and scheduled > today:
            continue
        eligible.append(item)
    if not eligible:
        raise base.NoteDraftError("No eligible Ready / 投稿待ち article is available")

    def sort_key(item: dict[str, Any]) -> tuple[int, str, str]:
        scheduled = base._parse_iso_date(item["scheduled_date"])
        if scheduled is not None:
            return (0, scheduled.isoformat(), item["created_time"])
        return (1, "9999-12-31", item["created_time"])

    eligible.sort(key=sort_key)
    return eligible


def _prepare_one(candidate: dict[str, Any]) -> dict[str, Any]:
    source_page = base._fetch_source_page(candidate["sync_id"])
    manuscript = _manuscript_from_blocks(base._fetch_block_children(candidate["sync_id"]))
    image_url = base._eyecatch_url(source_page)
    if not image_url:
        raise base.NoteDraftError("Ready article has no eyecatch in Content Intelligence")
    prepared = dict(candidate)
    prepared["manuscript"] = manuscript
    prepared["eyecatch_url"] = image_url
    return prepared


def _prepare_article(requested_sync_id: str = "") -> dict[str, Any]:
    if not base.ready_sync.NOTION_API_KEY:
        raise base.NoteDraftError("Notion API key is not configured")
    if not (base.ready_sync.DEST_DATA_SOURCE_ID or base.ready_sync.DEST_DATABASE_ID):
        raise base.NoteDraftError("note Ready DB is not configured")

    candidates = _ordered_candidates(base._query_ready_queue(), requested_sync_id=requested_sync_id)
    explicit = bool(base._normalize_sync_id(requested_sync_id))
    skipped: list[str] = []

    for candidate in candidates:
        try:
            prepared = _prepare_one(candidate)
        except UnsafeLegacyPaidMarker:
            # Explicit operator requests never silently move to another article.
            if explicit:
                raise
            skipped.append(candidate["sync_id"])
            print(
                "[RUN185 NOTE DRAFT] skipped legacy paid-marker Ready article "
                f"sync_id={candidate['sync_id'][:8]}"
            )
            continue
        prepared["skipped_legacy_paid_marker_count"] = len(skipped)
        return prepared

    raise base.NoteDraftError(
        "No publish-safe Ready article is available: all eligible candidates contain "
        f"legacy paid-area control markers (skipped={len(skipped)})"
    )


def install() -> None:
    base._manuscript_from_blocks = _manuscript_from_blocks
    base._prepare_article = _prepare_article


def main() -> None:
    install()
    base.main()


if __name__ == "__main__":
    main()
