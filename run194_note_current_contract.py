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

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import note_draft_automation as base
import eyecatch_publication_contract as eyecatch_contract
import publication_contract as contract
import run185_note_ready_legacy_skip as run185


class StalePublicationContract(base.NoteDraftError):
    """A Ready row does not contain a byte-valid manuscript from the current policy."""


class IncompletePublicationAsset(base.NoteDraftError):
    """A current manuscript is missing a required public asset such as the eyecatch."""


_AUTOMATIC_NOOP_EXACT = "No eligible Ready / 投稿待ち article is available"
_AUTOMATIC_NOOP_PREFIX = "No complete current publication-contract Ready article is available"


def _manuscript_from_blocks(blocks: list[dict]) -> str:
    current_bodies: list[str] = []
    stale_ready_seen = False

    for block in blocks:
        parsed = base._code_block_text(block)
        if parsed is None:
            continue
        try:
            payload = json.loads(parsed)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("publication_readiness") != "PASS":
            continue
        if payload.get("human_appeal") == "WEAK":
            continue
        manuscript = str(payload.get("article_markdown") or "")
        if not manuscript:
            continue
        expected_sha = str(payload.get("article_sha256") or "").strip().lower()
        if not expected_sha or expected_sha != base._sha256_text(manuscript):
            continue
        if payload.get("publication_policy_fingerprint") != contract.current_publication_policy_fingerprint():
            stale_ready_seen = True
            continue
        current_bodies.append(manuscript)

    if current_bodies:
        return current_bodies[-1]
    if stale_ready_seen:
        raise StalePublicationContract("Ready article was generated under a stale publication policy")
    raise base.NoteDraftError("No byte-valid current-policy Ready manuscript was found")


def _extract_title(candidate: dict) -> str:
    title = str(candidate.get("title") or "").strip()
    if not title:
        raise base.NoteDraftError("Ready article has no title")
    return title


def _prepare_one(candidate: dict) -> dict:
    sync_id = base._normalize_sync_id(candidate.get("sync_id", ""))
    if len(sync_id) != 32:
        raise base.NoteDraftError("Ready article has no exact sync_id")
    blocks = base._query_all_blocks(sync_id)
    manuscript = _manuscript_from_blocks(blocks)
    eyecatch = eyecatch_contract.resolve_eyecatch(candidate)
    if eyecatch is None:
        raise IncompletePublicationAsset("Ready article has no current publication-contract eyecatch")
    return {
        **candidate,
        "sync_id": sync_id,
        "title": _extract_title(candidate),
        "manuscript": manuscript,
        "eyecatch_path": eyecatch,
    }


def _ordered_current_candidates(candidates: list[dict]) -> list[dict]:
    ordered: list[dict] = []
    stale_skipped = 0
    asset_skipped = 0
    paid_marker_skipped = 0
    explicit = bool(str(os.environ.get("NOTE_TARGET_SYNC_ID", "") or "").strip())

    for candidate in run185._ordered_candidates(candidates):
        try:
            prepared = _prepare_one(candidate)
        except StalePublicationContract:
            if explicit:
                raise
            stale_skipped += 1
            print(
                "[RUN195 NOTE DRAFT] skipped stale-contract Ready article "
                f"sync_id={candidate['sync_id'][:8]}"
            )
            continue
        except IncompletePublicationAsset:
            if explicit:
                raise
            asset_skipped += 1
            print(
                "[RUN195 NOTE DRAFT] skipped incomplete-asset Ready article "
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


def _trusted_clipboard_paste(page: Any, body: Any, manuscript: str) -> None:
    """Paste rich manuscript through Chromium's clipboard and a real keyboard paste.

    note's current editor ignores an untrusted synthetic ClipboardEvent while still letting
    dispatchEvent return successfully.  Write the already-approved HTML/plain payload to the
    browser clipboard, then let Chromium generate the trusted paste event from Control+V.
    Permissions are scoped to the current HTTPS note.com origin only; no private note API is used.
    """
    safe_html = base._markdown_to_safe_html(manuscript)
    base._clear_body_for_replacement(page, body)

    parsed = urlparse(str(getattr(page, "url", "") or ""))
    hostname = (parsed.hostname or "").lower()
    is_note_domain = hostname == "note.com" or hostname.endswith(".note.com")
    if parsed.scheme != "https" or not is_note_domain:
        raise base.NoteDraftError("trusted note paste requires an HTTPS note.com origin")
    origin = f"{parsed.scheme}://{parsed.netloc}"

    try:
        page.context.grant_permissions(
            ["clipboard-read", "clipboard-write"],
            origin=origin,
        )
        page.evaluate(
            """async payload => {
                if (!navigator.clipboard || typeof ClipboardItem === 'undefined') {
                    throw new Error('browser clipboard API unavailable');
                }
                const item = new ClipboardItem({
                    'text/html': new Blob([payload.html], {type: 'text/html'}),
                    'text/plain': new Blob([payload.text], {type: 'text/plain'}),
                });
                await navigator.clipboard.write([item]);
            }""",
            {"html": safe_html, "text": manuscript},
        )
    except Exception as exc:
        raise base.NoteDraftError("Could not stage the note manuscript in the browser clipboard") from exc

    body.click()
    page.keyboard.press("Control+V")
    page.wait_for_timeout(500)


def install() -> None:
    run185.install()
    base._prepare_one = _ordered_current_candidates
    base._paste_manuscript = _trusted_clipboard_paste


def run_base_main_with_safe_noop() -> None:
    install()
    try:
        base.main()
    except base.NoteDraftError as exc:
        text = str(exc)
        requested = bool(str(os.environ.get("NOTE_TARGET_SYNC_ID", "") or "").strip())
        if not requested and (text == _AUTOMATIC_NOOP_EXACT or text.startswith(_AUTOMATIC_NOOP_PREFIX)):
            print(f"[RUN194 NOTE DRAFT] {text}; no-op")
            return
        raise


if __name__ == "__main__":
    run_base_main_with_safe_noop()
