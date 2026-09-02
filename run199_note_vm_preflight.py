#!/usr/bin/env python3
"""Zero-browser preflight for note draft creation.

This module validates the exact current publication contract before any GCP Chrome VM is
started. Automatic empty-safe-queue is a successful no-op. A valid candidate is pinned by
sync_id and handed to the VM job so a later queue reorder cannot switch the article.

Safety:
- zero Gemini/model calls;
- zero browser/Playwright calls;
- zero note mutation;
- explicit sync_id remains fail-closed;
- Notion/configuration failures remain fail-closed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run194_note_current_contract as current


def _write_result(result: dict[str, Any]) -> None:
    target = os.environ.get("NOTE_DRAFT_RESULT_FILE", "").strip()
    if not target:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def preflight(requested_sync_id: str = "") -> dict[str, Any]:
    """Return a VM-start decision after the full publish-safe source validation."""
    current.install()
    requested = base._normalize_sync_id(requested_sync_id)
    try:
        prepared = current._prepare_article(requested)
    except base.NoteDraftError as exc:
        if requested or not current._is_automatic_noop_error(exc):
            raise
        result = current._write_noop_result(str(exc))
        result["should_start_vm"] = False
        result["selected_sync_id"] = ""
        _write_result(result)
        return result

    selected = base._normalize_sync_id(prepared.get("sync_id", ""))
    if len(selected) != 32:
        raise base.NoteDraftError("Preflight selected an invalid sync_id")

    result: dict[str, Any] = {
        "status": "eligible_ready",
        "should_start_vm": True,
        "selected_sync_id": selected,
        "zero_gemini_calls": True,
        "telegram_notified": False,
        "publication_contract": prepared.get("publication_contract", ""),
        "publication_policy_sha256": prepared.get("publication_policy_sha256", ""),
        "manuscript_sha256": prepared.get("manuscript_sha256", ""),
        "skipped_stale_contract_count": prepared.get("skipped_stale_contract_count", 0),
        "skipped_incomplete_asset_count": prepared.get("skipped_incomplete_asset_count", 0),
        "skipped_legacy_paid_marker_count": prepared.get("skipped_legacy_paid_marker_count", 0),
    }
    _write_result(result)
    return result


def main() -> None:
    confirm = os.environ.get("NOTE_DRAFT_CONFIRM", "").strip()
    if confirm != base.CONFIRM_TOKEN:
        raise base.NoteDraftError("Explicit note draft confirmation token is required")
    result = preflight(os.environ.get("NOTE_TARGET_SYNC_ID", ""))
    print("[RUN199 NOTE PREFLIGHT] " + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
