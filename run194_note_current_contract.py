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
from typing import Any, Callable
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
    if not eyecatch_contract.current_asset_url(image_url, str(candidate.get("title") or "")):
        raise IncompletePublicationAsset(
            "Current Ready article eyecatch is stale or belongs to another public title"
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


def _wait_for_bound_dialog_hidden(
    page: Any,
    dialog: Any,
    *,
    timeout_ms: int,
    after_bind: Callable[[], None] | None = None,
) -> None:
    """Wait for the exact crop dialog that was visible before Save was clicked.

    Playwright Locators are live queries.  note may open another role=dialog immediately after
    the crop modal closes, so waiting on `[role=dialog].first` after Save can silently retarget
    to the new dialog.  Bind the current DOM element first, perform the mutation, then wait only
    for that original element to detach or become hidden.
    """
    try:
        element = dialog.element_handle(timeout=2500)
    except Exception as exc:
        raise base.NoteDraftError("note eyecatch crop dialog element was not available") from exc
    if element is None:
        raise base.NoteDraftError("note eyecatch crop dialog element was not available")
    if after_bind is not None:
        after_bind()
    page.wait_for_function(
        """el => {
            if (!el.isConnected) return true;
            const style = window.getComputedStyle(el);
            return style.display === 'none'
                || style.visibility === 'hidden'
                || el.getAttribute('aria-hidden') === 'true';
        }""",
        arg=element,
        timeout=timeout_ms,
    )


def _upload_header_image(page: Any, image_path: Path) -> None:
    add_button = base._find_header_image_add_button(page)
    if add_button is None:
        raise base.NoteDraftError("note header-image control was not found")
    add_button.click()

    upload_button = base._first_visible(
        page,
        ['button:has-text("画像をアップロード")', '[role="button"]:has-text("画像をアップロード")'],
        timeout_ms=5000,
    )
    chooser_used = False
    if upload_button is not None:
        try:
            with page.expect_file_chooser(timeout=5000) as chooser_info:
                upload_button.click()
            chooser_info.value.set_files(str(image_path))
            chooser_used = True
        except Exception:
            chooser_used = False
    if not chooser_used:
        file_input = page.locator('input[type="file"]').first
        try:
            file_input.wait_for(state="attached", timeout=7000)
            file_input.set_input_files(str(image_path))
        except Exception as exc:
            raise base.NoteDraftError("note eyecatch file chooser was not available") from exc

    page.wait_for_timeout(1200)
    dialog = page.locator('[role="dialog"]').first
    try:
        dialog_visible = dialog.is_visible(timeout=2500)
    except Exception:
        dialog_visible = False
    if dialog_visible:
        try:
            save_button = None
            discovery_deadline = base.time.time() + 10
            while base.time.time() < discovery_deadline:
                save_button = base._find_crop_save_control(dialog)
                if save_button is not None:
                    break
                page.wait_for_timeout(250)
            if save_button is None:
                raise base.NoteDraftError("note eyecatch crop save control was not found")
            deadline = base.time.time() + 20
            while base.time.time() < deadline and not save_button.is_enabled():
                page.wait_for_timeout(300)
            if not save_button.is_enabled():
                raise base.NoteDraftError("note eyecatch crop dialog never became saveable")
            _wait_for_bound_dialog_hidden(
                page,
                dialog,
                timeout_ms=15000,
                after_bind=save_button.click,
            )
        except base.NoteDraftError:
            raise
        except Exception as exc:
            raise base.NoteDraftError("note eyecatch crop/save step failed") from exc

    page.wait_for_timeout(1000)
    error_locator = page.locator('text=/アップロード.*(失敗|できません|エラー)/').first
    try:
        if error_locator.is_visible(timeout=800):
            raise base.NoteDraftError("note reported an eyecatch upload error")
    except base.NoteDraftError:
        raise
    except Exception:
        pass


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
    try:
        page.keyboard.press("Control+V")
    except Exception as exc:
        raise base.NoteDraftError("Could not issue the trusted note paste keyboard action") from exc
    page.wait_for_timeout(1200)


def _is_automatic_noop_error(exc: BaseException) -> bool:
    """Return True only for an automatic run whose safe candidate set is empty."""
    if base._normalize_sync_id(os.environ.get("NOTE_TARGET_SYNC_ID", "")):
        return False
    message = str(exc).strip()
    return message == _AUTOMATIC_NOOP_EXACT or message.startswith(_AUTOMATIC_NOOP_PREFIX)


def _write_noop_result(reason: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "no_eligible_ready",
        "zero_gemini_calls": True,
        "telegram_notified": False,
        "publication_contract": contract.CONTRACT_ID,
        "reason": str(reason or "").strip(),
    }
    result_file = os.environ.get("NOTE_DRAFT_RESULT_FILE", "").strip()
    if result_file:
        path = Path(result_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return result


def run_base_main_with_safe_noop() -> dict[str, Any] | None:
    """Convert only an empty automatic safe queue into a successful no-op."""
    try:
        base.main()
    except base.NoteDraftError as exc:
        if not _is_automatic_noop_error(exc):
            raise
        result = _write_noop_result(str(exc))
        print("[RUN198 NOTE DRAFT] no eligible publish-safe Ready article; nothing to do")
        print(json.dumps(result, ensure_ascii=False))
        return result
    return None


def install() -> None:
    run185.install()
    base._manuscript_from_blocks = _manuscript_from_blocks
    base._prepare_article = _prepare_article
    base._upload_header_image = _upload_header_image
    base._paste_manuscript = _trusted_clipboard_paste


def main() -> None:
    install()
    run_base_main_with_safe_noop()


if __name__ == "__main__":
    main()
