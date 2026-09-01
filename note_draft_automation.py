#!/usr/bin/env python3
"""Create one note draft from the existing Ready queue through note's web editor.

Safety contract:
- ZERO Gemini/model calls.
- Manual workflow only; a literal confirmation token is required.
- Reads only 品質状態=Ready / 投稿状態=投稿待ち rows from the note Ready DB.
- Reads the already-approved Ready manuscript and eyecatch from Content Intelligence.
- Uses Playwright against the normal note web editor. No private/internal posting API.
- Creates a draft only. This module contains no public-release action.
- Reloads the created draft and verifies title/body persistence before marking the Notion
  queue row 投稿準備中.
- Authentication state is supplied only through NOTE_STORAGE_STATE_B64 and is never
  written to the repository or printed to logs.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import tempfile
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse
from zoneinfo import ZoneInfo

import requests

import note_ready_sync as ready_sync


NOTE_NEW_URL = os.environ.get("NOTE_NEW_URL", "https://note.com/new").strip() or "https://note.com/new"
CONFIRM_TOKEN = "CREATE_NOTE_DRAFT"
READY_CAPTION = "AIIF_MANUSCRIPT:READY"
READY_QUALITY = "Ready"
WAITING_STATUS = "投稿待ち"
PREPARING_STATUS = "投稿準備中"
EYECATCH_PROPERTY = "アイキャッチ"
MAX_EYECATCH_BYTES = 10 * 1024 * 1024
ARTIFACT_DIR = Path(os.environ.get("NOTE_DRAFT_ARTIFACT_DIR", ".runtime/note_draft"))


class NoteDraftError(RuntimeError):
    pass


class NoteAuthenticationExpired(NoteDraftError):
    pass


def _plain_text(values: list[dict] | None) -> str:
    return "".join(
        str(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
        for item in (values or [])
    ).strip()


def _prop_text(prop: dict | None) -> str:
    prop = prop or {}
    if prop.get("title") is not None:
        return _plain_text(prop.get("title"))
    if prop.get("rich_text") is not None:
        return _plain_text(prop.get("rich_text"))
    return ""


def _prop_select(prop: dict | None) -> str:
    return str(((prop or {}).get("select") or {}).get("name") or "").strip()


def _prop_date(prop: dict | None) -> str:
    return str((((prop or {}).get("date") or {}).get("start")) or "").strip()


def _normalize_sync_id(value: str) -> str:
    return re.sub(r"[^0-9a-fA-F]", "", str(value or "")).lower()


def _candidate_from_page(page: dict) -> dict[str, Any] | None:
    props = page.get("properties") or {}
    if _prop_select(props.get("品質状態")) != READY_QUALITY:
        return None
    if _prop_select(props.get("投稿状態")) != WAITING_STATUS:
        return None
    sync_id = _normalize_sync_id(_prop_text(props.get("同期ID")))
    title = _prop_text(props.get("記事タイトル"))
    if len(sync_id) != 32 or not title:
        return None
    return {
        "destination_page_id": str(page.get("id") or ""),
        "sync_id": sync_id,
        "title": title,
        "scheduled_date": _prop_date(props.get("投稿予定日")),
        "created_time": str(page.get("created_time") or ""),
    }


def _parse_iso_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _select_candidate(pages: list[dict], requested_sync_id: str = "", today: date | None = None) -> dict[str, Any]:
    requested = _normalize_sync_id(requested_sync_id)
    candidates = [item for item in (_candidate_from_page(page) for page in pages) if item]
    if requested:
        matches = [item for item in candidates if item["sync_id"] == requested]
        if len(matches) != 1:
            raise NoteDraftError("Requested sync_id is not exactly one Ready / 投稿待ち article")
        return matches[0]

    today = today or datetime.now(ZoneInfo("Asia/Tokyo")).date()
    eligible: list[dict[str, Any]] = []
    for item in candidates:
        scheduled = _parse_iso_date(item["scheduled_date"])
        if scheduled is not None and scheduled > today:
            continue
        eligible.append(item)
    if not eligible:
        raise NoteDraftError("No eligible Ready / 投稿待ち article is available")

    def sort_key(item: dict[str, Any]) -> tuple[int, str, str]:
        scheduled = _parse_iso_date(item["scheduled_date"])
        if scheduled is not None:
            return (0, scheduled.isoformat(), item["created_time"])
        return (1, "9999-12-31", item["created_time"])

    eligible.sort(key=sort_key)
    return eligible[0]


def _query_ready_queue() -> list[dict]:
    return ready_sync._query_db(
        ready_sync.DEST_DATA_SOURCE_ID,
        ready_sync.DEST_DATABASE_ID,
        payload={
            "filter": {
                "and": [
                    {"property": "品質状態", "select": {"equals": READY_QUALITY}},
                    {"property": "投稿状態", "select": {"equals": WAITING_STATUS}},
                ]
            }
        },
    )


def _fetch_source_page(sync_id: str) -> dict:
    response = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{sync_id}")
    if response.status_code != 200:
        raise NoteDraftError(f"Content Intelligence page fetch failed: HTTP {response.status_code}")
    value = response.json()
    if not isinstance(value, dict):
        raise NoteDraftError("Content Intelligence page response is invalid")
    return value


def _fetch_block_children(block_id: str) -> list[dict]:
    results: list[dict] = []
    cursor = ""
    for _ in range(30):
        query = {"page_size": 100}
        if cursor:
            query["start_cursor"] = cursor
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?{urlencode(query)}"
        response = ready_sync._request("GET", url)
        if response.status_code != 200:
            raise NoteDraftError(f"Notion manuscript block fetch failed: HTTP {response.status_code}")
        payload = response.json()
        results.extend(payload.get("results") or [])
        if not payload.get("has_more"):
            return results
        cursor = str(payload.get("next_cursor") or "")
        if not cursor:
            return results
    raise NoteDraftError("Notion manuscript pagination exceeded safety limit")


def _code_block_text(block: dict) -> tuple[str, str] | None:
    if block.get("type") != "code":
        return None
    code = block.get("code") or {}
    body = _plain_text(code.get("rich_text"))
    caption = _plain_text(code.get("caption"))
    return body, caption


def _manuscript_from_blocks(blocks: list[dict]) -> str:
    ready_chunks: list[str] = []
    legacy_chunks: list[str] = []
    for block in blocks:
        parsed = _code_block_text(block)
        if parsed is None:
            continue
        body, caption = parsed
        if not body:
            continue
        if caption == READY_CAPTION:
            ready_chunks.append(body)
        elif not caption:
            legacy_chunks.append(body)
    chunks = ready_chunks or legacy_chunks
    manuscript = "".join(chunks).strip()
    if len(manuscript) < 200:
        raise NoteDraftError("Ready manuscript is missing or unexpectedly short")
    if re.search(r"有料\s*エリア", manuscript, flags=re.I):
        raise NoteDraftError("Ready manuscript still contains an internal paid-area control marker")
    return manuscript


def _eyecatch_url(source_page: dict) -> str:
    prop = ((source_page.get("properties") or {}).get(EYECATCH_PROPERTY) or {})
    files = prop.get("files") or []
    if not files:
        return ""
    first = files[0] or {}
    if first.get("type") == "external":
        return str((first.get("external") or {}).get("url") or "").strip()
    if first.get("type") == "file":
        return str((first.get("file") or {}).get("url") or "").strip()
    return ""


def _download_eyecatch(url: str, sync_id: str) -> Path:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise NoteDraftError("Eyecatch URL must use HTTPS")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    target = ARTIFACT_DIR / f"{sync_id}.png"
    with requests.get(url, timeout=45, stream=True) as response:
        if response.status_code != 200:
            raise NoteDraftError(f"Eyecatch download failed: HTTP {response.status_code}")
        total = 0
        with target.open("wb") as handle:
            for chunk in response.iter_content(1024 * 256):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_EYECATCH_BYTES:
                    target.unlink(missing_ok=True)
                    raise NoteDraftError("Eyecatch exceeds the 10MB safety limit")
                handle.write(chunk)
    if total < 1024:
        target.unlink(missing_ok=True)
        raise NoteDraftError("Downloaded eyecatch is unexpectedly small")
    return target


def _inline_markdown(value: str) -> str:
    value = html.escape(value, quote=False)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", value)

    def link_repl(match: re.Match[str]) -> str:
        label, url = match.group(1), html.unescape(match.group(2)).strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return f"{label} ({html.escape(url, quote=False)})"
        safe_url = html.escape(url, quote=True)
        return f'<a href="{safe_url}">{label}</a>'

    value = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", link_repl, value)
    return value


def _markdown_to_safe_html(markdown_text: str) -> str:
    """Convert the article's limited editorial Markdown to safe paste HTML.

    Raw HTML is escaped first. The converter intentionally supports the structures used by
    AIIF public manuscripts and avoids executing arbitrary markup in the browser context.
    """
    lines = str(markdown_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    paragraph: list[str] = []
    list_kind = ""
    in_code = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            body = "<br>".join(_inline_markdown(line) for line in paragraph)
            out.append(f"<p>{body}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            out.append(f"</{list_kind}>")
            list_kind = ""

    for raw in lines:
        line = raw.rstrip()
        if line.strip().startswith("```"):
            flush_paragraph()
            close_list()
            if not in_code:
                in_code = True
                code_lines = []
            else:
                out.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                in_code = False
                code_lines = []
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line.strip():
            flush_paragraph()
            close_list()
            continue
        if re.fullmatch(r"\s*-{3,}\s*", line):
            flush_paragraph()
            close_list()
            out.append("<hr>")
            continue
        heading = re.match(r"^\s*(#{2,4})\s+(.+?)\s*$", line)
        if heading:
            flush_paragraph()
            close_list()
            level = min(4, max(2, len(heading.group(1))))
            out.append(f"<h{level}>{_inline_markdown(heading.group(2))}</h{level}>")
            continue
        quote = re.match(r"^\s*>\s?(.*)$", line)
        if quote:
            flush_paragraph()
            close_list()
            out.append(f"<blockquote>{_inline_markdown(quote.group(1))}</blockquote>")
            continue
        unordered = re.match(r"^\s*[-*]\s+(.+)$", line)
        ordered = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if unordered or ordered:
            flush_paragraph()
            desired = "ul" if unordered else "ol"
            if list_kind != desired:
                close_list()
                list_kind = desired
                out.append(f"<{list_kind}>")
            text = (unordered or ordered).group(1)
            out.append(f"<li>{_inline_markdown(text)}</li>")
            continue
        if list_kind:
            close_list()
        paragraph.append(line)

    if in_code:
        out.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
    flush_paragraph()
    close_list()
    return "\n".join(out)


def _plain_manuscript_text(markdown_text: str) -> str:
    text = re.sub(r"```.*?```", " ", markdown_text, flags=re.S)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[#>*_`~\-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _first_visible(page: Any, selectors: list[str], timeout_ms: int = 2500) -> Any | None:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if locator.is_visible(timeout=timeout_ms):
                return locator
        except Exception:
            continue
    return None


def _set_title(page: Any, title: str) -> Any:
    selectors = [
        'textarea[placeholder*="タイトル"]',
        'input[placeholder*="タイトル"]',
        '[data-testid="note-title"]',
        '[aria-label*="タイトル"]',
        'div[data-placeholder*="タイトル"]',
        'h1[contenteditable="true"]',
    ]
    field = _first_visible(page, selectors, timeout_ms=4000)
    if field is None:
        raise NoteDraftError("note title field was not found")
    tag = str(field.evaluate("el => el.tagName.toLowerCase()"))
    if tag in {"input", "textarea"}:
        field.fill(title)
    else:
        field.click()
        page.keyboard.press("Control+A")
        page.keyboard.insert_text(title)
    return field


def _find_body(page: Any, title_field: Any | None = None) -> Any:
    title_y = -1.0
    if title_field is not None:
        try:
            box = title_field.bounding_box()
            title_y = float((box or {}).get("y", -1))
        except Exception:
            pass
    selectors = [
        'div[contenteditable="true"][role="textbox"]',
        '[data-placeholder*="本文"][contenteditable="true"]',
        '[aria-label*="本文"][contenteditable="true"]',
        '#note-body[contenteditable="true"]',
        'div[contenteditable="true"]',
    ]
    seen: set[str] = set()
    options: list[tuple[float, Any]] = []
    for selector in selectors:
        locator = page.locator(selector)
        try:
            count = min(locator.count(), 12)
        except Exception:
            continue
        for index in range(count):
            item = locator.nth(index)
            try:
                if not item.is_visible(timeout=800):
                    continue
                handle_key = str(item.evaluate("el => el.outerHTML.slice(0,180)"))
                if handle_key in seen:
                    continue
                seen.add(handle_key)
                tag = str(item.evaluate("el => el.tagName.toLowerCase()"))
                if tag == "h1":
                    continue
                box = item.bounding_box() or {}
                y = float(box.get("y", 0))
                if title_y >= 0 and y <= title_y + 10:
                    continue
                options.append((y, item))
            except Exception:
                continue
    if not options:
        raise NoteDraftError("note body editor was not found")
    options.sort(key=lambda pair: pair[0])
    return options[0][1]


def _paste_manuscript(page: Any, body: Any, manuscript: str) -> None:
    safe_html = _markdown_to_safe_html(manuscript)
    body.click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    body.evaluate(
        """(el, payload) => {
            el.focus();
            const data = new DataTransfer();
            data.setData('text/html', payload.html);
            data.setData('text/plain', payload.text);
            const event = new ClipboardEvent('paste', {
                bubbles: true, cancelable: true, clipboardData: data
            });
            el.dispatchEvent(event);
        }""",
        {"html": safe_html, "text": manuscript},
    )
    page.wait_for_timeout(1200)


def _verify_body_content(body: Any, manuscript: str) -> None:
    expected = _plain_manuscript_text(manuscript)
    try:
        actual = re.sub(r"\s+", " ", str(body.inner_text(timeout=5000) or "")).strip()
    except Exception as exc:
        raise NoteDraftError("Could not read note body after insertion") from exc
    if not expected:
        raise NoteDraftError("Prepared manuscript has no visible text")
    sample = expected[: min(32, len(expected))]
    minimum = min(120, max(30, len(expected) // 8))
    if len(actual) < minimum or sample not in actual:
        raise NoteDraftError("note body insertion verification failed; refusing to save a malformed draft")


def _topmost_visible(locator: Any) -> Any | None:
    best: tuple[float, Any] | None = None
    try:
        count = min(locator.count(), 12)
    except Exception:
        return None
    for index in range(count):
        item = locator.nth(index)
        try:
            if not item.is_visible(timeout=700):
                continue
            box = item.bounding_box()
            if not box:
                continue
            y = float(box.get("y", 999999))
            if best is None or y < best[0]:
                best = (y, item)
        except Exception:
            continue
    return best[1] if best else None


def _upload_header_image(page: Any, image_path: Path) -> None:
    add_candidates = page.locator(
        'button[aria-label="画像を追加"], button[aria-label*="見出し画像"], button:has-text("画像を追加")'
    )
    add_button = _topmost_visible(add_candidates)
    if add_button is None:
        raise NoteDraftError("note header-image control was not found")
    add_button.click()

    upload_button = _first_visible(
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
            raise NoteDraftError("note eyecatch file chooser was not available") from exc

    page.wait_for_timeout(1200)
    dialog = page.locator('[role="dialog"]').first
    try:
        dialog_visible = dialog.is_visible(timeout=2500)
    except Exception:
        dialog_visible = False
    if dialog_visible:
        save_button = dialog.get_by_role("button", name=re.compile(r"^保存$")).first
        try:
            save_button.wait_for(state="visible", timeout=10000)
            deadline = time.time() + 20
            while time.time() < deadline and not save_button.is_enabled():
                page.wait_for_timeout(300)
            if not save_button.is_enabled():
                raise NoteDraftError("note eyecatch crop dialog never became saveable")
            save_button.click()
            dialog.wait_for(state="hidden", timeout=15000)
        except NoteDraftError:
            raise
        except Exception as exc:
            raise NoteDraftError("note eyecatch crop/save step failed") from exc

    page.wait_for_timeout(1000)
    error_locator = page.locator('text=/アップロード.*(失敗|できません|エラー)/').first
    try:
        if error_locator.is_visible(timeout=800):
            raise NoteDraftError("note reported an eyecatch upload error")
    except NoteDraftError:
        raise
    except Exception:
        pass


def _looks_logged_out(page: Any) -> bool:
    current = str(page.url or "").lower()
    if any(token in current for token in ("/login", "/signin", "/signup")):
        return True
    for selector in ('input[type="email"]', 'input[name="email"]', 'input[name="password"]'):
        try:
            if page.locator(selector).first.is_visible(timeout=700):
                return True
        except Exception:
            continue
    return False


def _wait_for_draft_url(page: Any, timeout_seconds: int = 35) -> str:
    deadline = time.time() + timeout_seconds
    pattern = re.compile(r"https://(?:editor\.)?note\.com/notes/[^/?#]+/edit(?:[?#].*)?$", re.I)
    while time.time() < deadline:
        current = str(page.url or "")
        if pattern.match(current):
            return current
        page.wait_for_timeout(700)
    raise NoteDraftError("note did not expose a stable draft edit URL after autosave")


def _save_draft_and_verify(page: Any, title: str, manuscript: str, image_required: bool = True) -> str:
    save_button = _first_visible(
        page,
        ['button:has-text("下書き保存")', '[aria-label*="下書き保存"]'],
        timeout_ms=1000,
    )
    if save_button is not None:
        try:
            if save_button.is_enabled():
                save_button.click()
        except Exception:
            pass
    page.wait_for_timeout(1800)
    draft_url = _wait_for_draft_url(page)

    # Persistence proof: reopen the draft. DOM-only injection that was not accepted by
    # note's document model disappears here and therefore never advances the queue row.
    page.goto(draft_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1200)
    if _looks_logged_out(page):
        raise NoteAuthenticationExpired("note session expired while reopening the draft")
    title_field = _set_title(page, title)
    # _set_title is idempotent but writing it again would hide a title persistence bug. Read it.
    try:
        tag = str(title_field.evaluate("el => el.tagName.toLowerCase()"))
        if tag in {"input", "textarea"}:
            persisted_title = str(title_field.input_value() or "").strip()
        else:
            persisted_title = str(title_field.inner_text() or "").strip()
    except Exception as exc:
        raise NoteDraftError("Could not verify persisted note title") from exc
    if persisted_title != title.strip():
        raise NoteDraftError("note title persistence verification failed")

    body = _find_body(page, title_field)
    _verify_body_content(body, manuscript)
    if image_required:
        changed = page.locator('button[aria-label="画像を変更"], button[aria-label*="見出し画像を変更"]').first
        try:
            if changed.count() and not changed.is_visible(timeout=2500):
                raise NoteDraftError("note eyecatch persistence verification failed")
        except NoteDraftError:
            raise
        except Exception:
            # Some note UI revisions do not expose the change control. Upload success plus
            # title/body persistence remains sufficient; do not invent a false failure.
            pass
    return draft_url


def _decode_storage_state() -> Path:
    encoded = os.environ.get("NOTE_STORAGE_STATE_B64", "").strip()
    if not encoded:
        raise NoteAuthenticationExpired("NOTE_STORAGE_STATE_B64 is not configured")
    try:
        raw = base64.b64decode(encoded, validate=True)
        parsed = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise NoteAuthenticationExpired("NOTE_STORAGE_STATE_B64 is not valid base64 JSON") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("cookies"), list):
        raise NoteAuthenticationExpired("note storage state has an invalid structure")
    fd, name = tempfile.mkstemp(prefix="note-storage-", suffix=".json")
    os.close(fd)
    path = Path(name)
    path.write_bytes(raw)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def _create_browser_draft(title: str, manuscript: str, eyecatch_path: Path, storage_path: Path) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise NoteDraftError("Playwright is required for note draft creation") from exc

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--lang=ja-JP"])
        context = browser.new_context(
            storage_state=str(storage_path),
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            viewport={"width": 1440, "height": 1100},
        )
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto(NOTE_NEW_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1200)
            if _looks_logged_out(page):
                raise NoteAuthenticationExpired("note session has expired; refresh the storage-state secret")
            _upload_header_image(page, eyecatch_path)
            title_field = _set_title(page, title)
            body = _find_body(page, title_field)
            _paste_manuscript(page, body, manuscript)
            body = _find_body(page, title_field)
            _verify_body_content(body, manuscript)
            return _save_draft_and_verify(page, title, manuscript, image_required=True)
        except Exception:
            try:
                page.screenshot(path=str(ARTIFACT_DIR / "failure.png"), full_page=False)
            except Exception:
                pass
            raise
        finally:
            context.close()
            browser.close()


def _mark_draft_created(destination_page_id: str) -> None:
    response = ready_sync._request(
        "PATCH",
        f"https://api.notion.com/v1/pages/{destination_page_id}",
        json={"properties": {"投稿状態": {"select": {"name": PREPARING_STATUS}}}},
    )
    if response.status_code != 200:
        raise NoteDraftError(f"Draft was created but Notion status update failed: HTTP {response.status_code}")


def _send_telegram_draft_notice(draft_url: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False
    text = "📝 noteの下書きを作成しました。\nスマートフォンで内容を確認して、問題なければ公開してください。\n" + draft_url
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=15,
        )
        return response.status_code == 200
    except requests.RequestException:
        return False


def _prepare_article(requested_sync_id: str = "") -> dict[str, Any]:
    if not ready_sync.NOTION_API_KEY:
        raise NoteDraftError("Notion API key is not configured")
    if not (ready_sync.DEST_DATA_SOURCE_ID or ready_sync.DEST_DATABASE_ID):
        raise NoteDraftError("note Ready DB is not configured")
    queue_pages = _query_ready_queue()
    candidate = _select_candidate(queue_pages, requested_sync_id=requested_sync_id)
    source_page = _fetch_source_page(candidate["sync_id"])
    manuscript = _manuscript_from_blocks(_fetch_block_children(candidate["sync_id"]))
    image_url = _eyecatch_url(source_page)
    if not image_url:
        raise NoteDraftError("Ready article has no eyecatch in Content Intelligence")
    candidate["manuscript"] = manuscript
    candidate["eyecatch_url"] = image_url
    return candidate


def run(*, confirm: str, requested_sync_id: str = "", prepare_only: bool = False) -> dict[str, Any]:
    if confirm != CONFIRM_TOKEN:
        raise NoteDraftError(f"Confirmation must equal {CONFIRM_TOKEN}")
    article = _prepare_article(requested_sync_id)
    result: dict[str, Any] = {
        "success": True,
        "zero_gemini_calls": True,
        "sync_id": article["sync_id"],
        "status": "prepared" if prepare_only else "draft_created",
        "telegram_notified": False,
    }
    if prepare_only:
        return result

    eyecatch_path = _download_eyecatch(article["eyecatch_url"], article["sync_id"])
    storage_path = _decode_storage_state()
    try:
        draft_url = _create_browser_draft(article["title"], article["manuscript"], eyecatch_path, storage_path)
    finally:
        storage_path.unlink(missing_ok=True)
    _mark_draft_created(article["destination_page_id"])
    result["draft_url"] = draft_url
    result["telegram_notified"] = _send_telegram_draft_notice(draft_url)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-id", default=os.environ.get("NOTE_TARGET_SYNC_ID", ""))
    parser.add_argument("--confirm", default=os.environ.get("NOTE_DRAFT_CONFIRM", ""))
    parser.add_argument("--prepare-only", action="store_true", default=os.environ.get("NOTE_PREPARE_ONLY", "false").lower() in {"1", "true", "yes", "on"})
    parser.add_argument("--result-file", default=os.environ.get("NOTE_DRAFT_RESULT_FILE", ""))
    args = parser.parse_args()

    result = run(confirm=args.confirm, requested_sync_id=args.sync_id, prepare_only=args.prepare_only)
    if args.result_file:
        target = Path(args.result_file)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    # Never print the private draft URL to a public GitHub Actions log.
    safe = {key: value for key, value in result.items() if key != "draft_url"}
    print(json.dumps(safe, ensure_ascii=False))


if __name__ == "__main__":
    main()
