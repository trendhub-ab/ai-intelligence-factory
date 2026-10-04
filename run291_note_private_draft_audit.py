#!/usr/bin/env python3
"""Read-only audit for an already-created private note draft.

Run291 never creates, edits, saves, publishes, or withdraws a note. It:
- requires an exact current-quality / 投稿準備中 queue row;
- reconstructs the already-approved note-editor presentation manuscript;
- requires the persisted opaque note下書きID bound to the exact queue row;
- reconstructs one canonical private edit route and opens only that route read-only;
- verifies persisted title/body/eyecatch and presentation structure;
- returns only non-content audit metrics. The draft URL and unpublished body are never printed.

ZERO Gemini/model calls. No public-release action. No screenshot or unpublished-content artifact.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import note_draft_automation as note_base
import note_publication_reconcile as note_lifecycle
import note_ready_sync as ready_sync
import run187_note_editor_readiness as run187
import run190_note_persistent_cloud as run190
import run222_note_presentation_integrity as run222

CONFIRM_TOKEN = "AUDIT_NOTE_DRAFT"
PREPARING_STATUS = "投稿準備中"
READY_STATUS = "Ready"
_EDIT_PATH = re.compile(r"^/notes/[^/?#]+/edit/?$", re.I)
_READER_FIRST_LABELS = ("どんな内容？", "なぜ重要？", "結論は？", "元情報")


class PrivateDraftAuditError(RuntimeError):
    def __init__(self, message: str, *, safe_metrics: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.safe_metrics = dict(safe_metrics or {})


def _normalize_sync_id(value: str) -> str:
    return re.sub(r"[^0-9a-fA-F]", "", str(value or "")).lower()


def _prop_date(prop: dict | None) -> str:
    return str((((prop or {}).get("date") or {}).get("start")) or "").strip()



def _is_note_edit_url(value: str) -> bool:
    """Validate one existing private note edit route; never performs discovery."""
    try:
        parsed = urlparse(str(value or ""))
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in {"note.com", "editor.note.com"}:
        return False
    return bool(_EDIT_PATH.fullmatch(parsed.path or ""))


def _destination_row(sync_id: str) -> dict[str, Any]:
    sid = _normalize_sync_id(sync_id)
    if len(sid) != 32:
        raise PrivateDraftAuditError("Run291 requires an exact 32-hex sync_id")
    pages = ready_sync._query_db(
        ready_sync.DEST_DATA_SOURCE_ID,
        ready_sync.DEST_DATABASE_ID,
        payload={"filter": {"property": "同期ID", "rich_text": {"equals": sid}}},
    )
    exact = [
        page
        for page in pages
        if _normalize_sync_id(ready_sync._text((page.get("properties") or {}).get("同期ID"))) == sid
    ]
    if len(exact) != 1:
        raise PrivateDraftAuditError("Run291 expected exactly one destination row for the requested sync_id")
    page = exact[0]
    props = page.get("properties") or {}
    quality = ready_sync._select(props.get("品質状態"))
    posting = ready_sync._select(props.get("投稿状態"))
    if quality != READY_STATUS or posting != PREPARING_STATUS:
        raise PrivateDraftAuditError("Requested row is not current Ready / 投稿準備中")
    if ready_sync._url(props.get("note公開URL")) or _prop_date(props.get("投稿日")):
        raise PrivateDraftAuditError("Requested row already has public-post evidence; private-draft audit refuses it")
    title = ready_sync._text(props.get("記事タイトル"))
    if not title:
        raise PrivateDraftAuditError("Destination row has no title")
    draft_id = ready_sync._text(props.get(note_lifecycle.DRAFT_ID_PROPERTY))
    if not draft_id:
        raise PrivateDraftAuditError("Destination row has no stable private draft identity")
    draft_url = _draft_edit_url(draft_id)
    validated_draft_id = note_lifecycle.draft_identity_from_url(
        draft_url, error_type=PrivateDraftAuditError
    )
    return {
        "destination_page_id": str(page.get("id") or ""),
        "sync_id": sid,
        "title": title,
        "draft_id": validated_draft_id,
    }


def _expected_article(sync_id: str) -> dict[str, Any]:
    row = _destination_row(sync_id)
    response = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{row['sync_id']}")
    if response.status_code != 200:
        raise PrivateDraftAuditError("Content Intelligence source page could not be read")
    source_page = response.json()
    state = ready_sync._source_state(source_page)
    if state is None or state.get("sync_id") != row["sync_id"]:
        raise PrivateDraftAuditError("Content Intelligence source is not an active Ready source")
    if str(state.get("title") or "").strip() != row["title"].strip():
        raise PrivateDraftAuditError("Source and destination titles do not match")
    manuscript = ready_sync._source_current_ready_manuscript(row["sync_id"])
    if not manuscript:
        raise PrivateDraftAuditError("No byte-valid current Publication Contract manuscript exists")
    if not state.get("eyecatch_url"):
        raise PrivateDraftAuditError("Current Ready source has no eyecatch")
    presented = run222.prepare_note_editor_manuscript(manuscript, row["title"])
    if len(presented) < 200:
        raise PrivateDraftAuditError("Prepared note presentation is unexpectedly short")
    row["manuscript"] = presented
    return row



def _title_value(page: Any) -> str:
    field = note_base._find_title(page)
    try:
        tag = str(field.evaluate("el => el.tagName.toLowerCase()"))
        if tag in {"input", "textarea"}:
            return str(field.input_value() or "").strip()
        return str(field.inner_text() or "").strip()
    except Exception as exc:
        raise PrivateDraftAuditError("Could not read the private draft title") from exc


def _normalized_visible(value: str) -> str:
    text = str(value or "").replace("\u3000", " ")
    text = re.sub(r"[•●◦▪︎■□]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _body_text_metrics(actual_text: str, expected_markdown: str, title: str) -> dict[str, Any]:
    actual = _normalized_visible(actual_text)
    expected = _normalized_visible(note_base._plain_manuscript_text(expected_markdown))
    if not expected or not actual:
        raise PrivateDraftAuditError("Private draft body is empty")
    prefix = expected[: min(64, len(expected))]
    suffix = expected[-min(64, len(expected)) :]
    ratio = len(actual) / max(1, len(expected))
    prefix_ok = prefix in actual
    suffix_ok = suffix in actual
    heading_cardinality_ok = all(
        actual.count(label) == expected.count(label)
        for label in _READER_FIRST_LABELS
    )
    if (
        not prefix_ok
        or not suffix_ok
        or not 0.88 <= ratio <= 1.12
        or not heading_cardinality_ok
    ):
        raise PrivateDraftAuditError("Private draft visible body does not match the approved presentation")

    source_index = actual.find(run222.SOURCE_HEADING)
    cta_positions = [actual.find(label) for label in run222.CTA_HEADINGS]
    cta_positions = [pos for pos in cta_positions if pos >= 0]
    cta_index = min(cta_positions) if cta_positions else -1
    if source_index < 0 or cta_index < 0 or source_index >= cta_index:
        raise PrivateDraftAuditError("Private draft footer order is not Sources/Evidence then CTA")

    normalized_title = _normalized_visible(title)
    duplicate_title_prefix = bool(normalized_title and actual.startswith(normalized_title))
    if duplicate_title_prefix:
        raise PrivateDraftAuditError("Private draft body still duplicates the title at the top")

    return {
        "body_visible_chars": len(actual),
        "expected_visible_chars": len(expected),
        "visible_length_ratio": round(ratio, 4),
        "prefix_match": prefix_ok,
        "suffix_match": suffix_ok,
        "sources_before_cta": True,
        "duplicate_title_prefix": False,
    }


def _box(locator: Any) -> dict[str, int] | None:
    try:
        raw = locator.bounding_box()
    except Exception:
        return None
    if not raw:
        return None
    return {key: int(round(float(raw.get(key, 0)))) for key in ("x", "y", "width", "height")}


def _audit_current_page(page: Any, title: str, manuscript: str) -> dict[str, Any]:
    if note_base._looks_logged_out(page):
        raise PrivateDraftAuditError("note authentication is not active")
    if not run187._is_editor_url(str(page.url or "")):
        raise PrivateDraftAuditError("Matched page is not a confirmed note editor route")
    title_field = note_base._find_title(page)
    persisted_title = _title_value(page)
    if persisted_title != title.strip():
        raise PrivateDraftAuditError("Private draft title does not match the requested article")
    body = note_base._find_body(page, title_field)
    try:
        actual_text = str(body.inner_text(timeout=5000) or "")
    except Exception as exc:
        raise PrivateDraftAuditError("Could not read private draft body") from exc
    text_metrics = _body_text_metrics(actual_text, manuscript, title)

    try:
        body_h1_count = int(body.locator("h1").count())
        heading_count = int(body.locator("h2,h3,h4").count())
        paragraph_count = int(body.locator("p").count())
        list_item_count = int(body.locator("li").count())
        link_count = int(body.locator("a[href]").count())
        blockquote_count = int(body.locator("blockquote").count())
    except Exception as exc:
        raise PrivateDraftAuditError("Could not inspect private draft semantic structure") from exc
    if body_h1_count != 0:
        raise PrivateDraftAuditError("Private draft contains a body-level H1")
    if heading_count < 2:
        raise PrivateDraftAuditError("Private draft lost its expected heading structure")

    image_control = page.locator(
        'button[aria-label="画像を変更"], button[aria-label*="見出し画像を変更"]'
    ).first
    try:
        eyecatch_present = bool(image_control.count()) and image_control.is_visible(timeout=2500)
    except Exception:
        eyecatch_present = False
    if not eyecatch_present:
        raise PrivateDraftAuditError("Private draft eyecatch persistence could not be confirmed")

    title_box = _box(title_field)
    body_box = _box(body)
    if title_box is None or body_box is None:
        raise PrivateDraftAuditError("Private draft editor geometry is unavailable")
    if body_box["width"] < 360 or title_box["width"] < 360:
        raise PrivateDraftAuditError("Private draft editor content width is unexpectedly narrow")

    metrics: dict[str, Any] = {
        "title_match": True,
        "body_h1_count": body_h1_count,
        "heading_count": heading_count,
        "paragraph_count": paragraph_count,
        "list_item_count": list_item_count,
        "link_count": link_count,
        "blockquote_count": blockquote_count,
        "eyecatch_present": True,
        "title_box": title_box,
        "body_box": body_box,
    }
    metrics.update(text_metrics)
    return metrics


def _draft_edit_url(draft_id: str) -> str:
    raw = str(draft_id or "")
    if not raw or raw != raw.strip():
        raise PrivateDraftAuditError("Stable private draft identity is malformed")
    candidate = f"https://note.com/notes/{raw}/edit"
    identity = note_lifecycle.draft_identity_from_url(
        candidate, error_type=PrivateDraftAuditError
    )
    if identity != raw:
        raise PrivateDraftAuditError("Stable private draft identity is malformed")
    return candidate


def _browser_audit(article: dict[str, Any], *, page_auditor: Any | None = None) -> dict[str, Any]:
    private_url = _draft_edit_url(str(article.get("draft_id") or ""))
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PrivateDraftAuditError("Playwright is required for Run291") from exc

    audit_page = page_auditor or _audit_current_page
    with sync_playwright() as playwright:
        context = run190._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            try:
                page.goto(private_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1200)
            except Exception as exc:
                raise PrivateDraftAuditError("Stable private draft route could not be opened") from exc

            if note_base._looks_logged_out(page):
                seeded = bool(run190._seed_note_state(context, page))
                if seeded:
                    try:
                        page.goto(private_url, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(1200)
                    except Exception as exc:
                        raise PrivateDraftAuditError("Stable private draft route could not be reopened") from exc
            if note_base._looks_logged_out(page):
                raise PrivateDraftAuditError("note authentication is not active")
            if not run187._is_editor_url(str(page.url or "")):
                raise PrivateDraftAuditError("Stable private draft did not resolve to a confirmed editor route")
            persisted_title = _title_value(page)
            if persisted_title != str(article["title"]).strip():
                raise PrivateDraftAuditError("Stable private draft title does not match the requested article")
            return audit_page(page, str(article["title"]), str(article["manuscript"]))
        finally:
            context.close()


def run(*, confirm: str, sync_id: str, prepare_only: bool = False) -> dict[str, Any]:
    if confirm != CONFIRM_TOKEN:
        raise PrivateDraftAuditError(f"Confirmation must equal {CONFIRM_TOKEN}")
    article = _expected_article(sync_id)
    result: dict[str, Any] = {
        "success": True,
        "status": "audit_ready" if prepare_only else "audit_passed",
        "zero_gemini_calls": True,
        "read_only": True,
        "public_release": False,
        "draft_mutation": False,
        "sync_id": article["sync_id"],
    }
    if prepare_only:
        result["should_start_vm"] = True
        return result
    result.update(_browser_audit(article))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-id", default=os.environ.get("NOTE_TARGET_SYNC_ID", ""))
    parser.add_argument("--confirm", default=os.environ.get("NOTE_AUDIT_CONFIRM", ""))
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        default=os.environ.get("NOTE_AUDIT_PREPARE_ONLY", "false").lower() in {"1", "true", "yes", "on"},
    )
    parser.add_argument("--result-file", default=os.environ.get("NOTE_AUDIT_RESULT_FILE", ""))
    args = parser.parse_args()
    result = run(confirm=args.confirm, sync_id=args.sync_id, prepare_only=args.prepare_only)
    if args.result_file:
        target = Path(args.result_file)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
