#!/usr/bin/env python3
"""Run190: create note drafts in a persistent Google Chrome environment.

Run190 replaces the disposable GitHub-hosted Chromium execution path for real draft creation.
The actual browser job runs on an on-demand Google Compute Engine VM registered as a
self-hosted GitHub Actions runner. The VM keeps a persistent Chrome user-data directory on
its boot disk, so browser/session state survives VM stop/start cycles.

Safety contract:
- zero Gemini/model calls;
- draft creation only; the existing pipeline contains no public-release action;
- persistent browser state is never committed or uploaded as an artifact;
- NOTE_STORAGE_STATE_B64 is used only as an optional one-time note.com session bootstrap;
- Google/other-domain cookies from the bootstrap state are deliberately ignored;
- the authenticated browser must prove ownership of the exact trendhub_biz profile before mutation;
- a saved draft must also appear by the same stable draft id in note's official article list;
- existing Ready/article, header-image, persistence and Notion fail-closed guards remain.
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import note_draft_automation as base
import note_publication_reconcile as reconcile
import run185_note_ready_legacy_skip as run185
import run189_note_editor_route_gate as run189
import run193_note_official_header_upload as run193
import run187_note_editor_readiness as run187
import run417_note_body_verification as run417

PROFILE_ENV = "NOTE_CHROME_USER_DATA_DIR"
CHANNEL_ENV = "NOTE_CHROME_CHANNEL"
HEADLESS_ENV = "NOTE_CHROME_HEADLESS"
DEFAULT_PROFILE_DIR = Path.home() / ".aiif-note" / "chrome-profile"
MAX_HISTORY_CANDIDATES = 24
EXPECTED_NOTE_PROFILE_URL = "https://note.com/trendhub_biz"
PROFILE_SETTINGS_URL = "https://note.com/settings/profile"
EXPECTED_CREATOR_NAME = "AIF - AI Intelligence Factory"
CREATOR_NAME_SELECTOR = 'input[name="editNickname"][aria-label="クリエイター名"]:visible'
ARTICLE_LIST_URL = "https://note.com/notes"
_ORIGINAL_DECODE_STORAGE_STATE = base._decode_storage_state


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _profile_dir() -> Path:
    raw = os.environ.get(PROFILE_ENV, "").strip()
    path = Path(raw).expanduser() if raw else DEFAULT_PROFILE_DIR
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def _note_domain(value: str) -> bool:
    text = str(value or "").strip().lower().lstrip(".")
    return text == "note.com" or text.endswith(".note.com")


def _note_origin(value: str) -> bool:
    try:
        parsed = urlparse(str(value or ""))
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and _note_domain(parsed.hostname or "")


def _decode_bootstrap_state() -> dict[str, Any] | None:
    """Read the existing storage-state secret without ever logging its contents."""
    encoded = os.environ.get("NOTE_STORAGE_STATE_B64", "").strip()
    if not encoded:
        return None
    try:
        raw = base64.b64decode(encoded, validate=True)
        parsed = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise base.NoteAuthenticationExpired("NOTE_STORAGE_STATE_B64 is not valid base64 JSON") from exc
    if not isinstance(parsed, dict):
        raise base.NoteAuthenticationExpired("NOTE_STORAGE_STATE_B64 has an invalid structure")
    return parsed


def _compat_storage_path() -> Path:
    """Satisfy the legacy Run184 call signature without making the secret mandatory.

    When the bootstrap secret still exists, preserve the old validation/temporary-file path.
    Once the persistent Chrome profile is established, an empty private compatibility file is
    enough because Run190 never launches Chrome from this path.
    """
    if os.environ.get("NOTE_STORAGE_STATE_B64", "").strip():
        return _ORIGINAL_DECODE_STORAGE_STATE()
    fd, name = tempfile.mkstemp(prefix="note-run190-compat-", suffix=".json")
    os.close(fd)
    path = Path(name)
    path.write_text("{}", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def _seed_note_state(context: Any, page: Any) -> bool:
    """Optionally seed only note.com cookies/localStorage into the persistent profile.

    The state captured during Run184 may contain cookies from other login providers. Those
    are intentionally excluded: the cloud VM needs only the resulting note.com session.
    """
    state = _decode_bootstrap_state()
    if not state:
        return False

    cookies: list[dict[str, Any]] = []
    for item in state.get("cookies") or []:
        if not isinstance(item, dict) or not _note_domain(str(item.get("domain") or "")):
            continue
        cookie = dict(item)
        same_site = cookie.get("sameSite")
        if same_site not in {None, "Strict", "Lax", "None"}:
            cookie.pop("sameSite", None)
        cookies.append(cookie)
    if cookies:
        context.add_cookies(cookies)

    seeded_local_storage = False
    for origin in state.get("origins") or []:
        if not isinstance(origin, dict):
            continue
        origin_url = str(origin.get("origin") or "").strip()
        if not _note_origin(origin_url):
            continue
        entries = [
            {"name": str(entry.get("name") or ""), "value": str(entry.get("value") or "")}
            for entry in (origin.get("localStorage") or [])
            if isinstance(entry, dict) and entry.get("name") is not None
        ]
        if not entries:
            continue
        page.goto(origin_url, wait_until="domcontentloaded", timeout=60000)
        page.evaluate(
            """(entries) => {
                for (const item of entries) {
                    localStorage.setItem(item.name, item.value);
                }
            }""",
            entries,
        )
        seeded_local_storage = True
    return bool(cookies or seeded_local_storage)


def _copy_history_rows(history_path: Path) -> list[tuple[str, int]]:
    """Read a copy of Chrome History so a live profile is never locked or mutated."""
    temp_dir = Path(tempfile.mkdtemp(prefix="run190-history-"))
    copy_path = temp_dir / "History"
    try:
        shutil.copy2(history_path, copy_path)
        conn = sqlite3.connect(str(copy_path))
        try:
            rows = conn.execute(
                "SELECT url, last_visit_time FROM urls "
                "WHERE url LIKE 'https://%note.com/notes/%/edit%' "
                "ORDER BY last_visit_time DESC LIMIT 80"
            ).fetchall()
        finally:
            conn.close()
        return [(str(url or ""), int(last_visit or 0)) for url, last_visit in rows]
    except (OSError, sqlite3.Error):
        return []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _recent_private_edit_urls(profile_dir: Path) -> list[str]:
    """Return recent existing note edit routes for legacy in-place repair flows only."""
    weighted: list[tuple[int, str]] = []
    try:
        history_files = [p for p in profile_dir.rglob("History") if p.is_file()]
    except OSError:
        history_files = []
    for history in history_files[:12]:
        for url, last_visit in _copy_history_rows(history):
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            path = (parsed.path or "").rstrip("/")
            if (
                parsed.scheme == "https"
                and host in {"note.com", "editor.note.com"}
                and path.startswith("/notes/")
                and path.endswith("/edit")
                and path.count("/") == 3
            ):
                weighted.append((last_visit, url))
    weighted.sort(key=lambda item: item[0], reverse=True)
    seen: set[str] = set()
    result: list[str] = []
    for _, url in weighted:
        if url in seen:
            continue
        seen.add(url)
        result.append(url)
        if len(result) >= MAX_HISTORY_CANDIDATES:
            break
    return result


def _launch_persistent_context(playwright: Any) -> Any:
    profile = _profile_dir()
    channel = os.environ.get(CHANNEL_ENV, "chrome").strip() or "chrome"
    headless = _env_bool(HEADLESS_ENV, default=False)
    try:
        return playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            channel=channel,
            headless=headless,
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            viewport={"width": 1440, "height": 1100},
            args=[
                "--lang=ja-JP",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-dev-shm-usage",
            ],
        )
    except Exception as exc:
        raise base.NoteDraftError(
            "persistent Google Chrome could not be launched; verify Chrome/Xvfb and that no other process holds the profile lock"
        ) from exc


def _exact_settings_control(page: Any) -> Any:
    matches: list[Any] = []
    for tag in ("a", "button"):
        controls = page.locator(f"{tag}:visible")
        try:
            count = min(controls.count(), 80)
        except Exception:
            continue
        for index in range(count):
            control = controls.nth(index)
            try:
                text = " ".join(str(control.inner_text(timeout=500) or "").split())
            except Exception:
                continue
            if text == "設定":
                matches.append(control)
    if len(matches) != 1:
        raise base.NoteDraftError("expected note account ownership control could not be proven")
    return matches[0]


def _is_expected_profile_href(value: str) -> bool:
    """Match only the exact expected note profile URL, allowing a trailing slash."""
    try:
        parsed = urlparse(urljoin("https://note.com", str(value or "").strip()))
        expected = urlparse(EXPECTED_NOTE_PROFILE_URL)
    except Exception:
        return False
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower() == (expected.hostname or "").lower()
        and (parsed.path or "").rstrip("/") == (expected.path or "").rstrip("/")
        and not parsed.query
        and not parsed.fragment
    )


def _settings_page_has_expected_profile_link(page: Any) -> bool:
    """Read-only proof that settings belongs to the configured trendhub_biz profile."""
    try:
        hrefs = page.locator("a[href]").evaluate_all(
            "els => els.map(el => el.getAttribute('href') || '').filter(Boolean)"
        )
    except Exception:
        return False
    return any(_is_expected_profile_href(raw) for raw in (hrefs or []))


def _assert_expected_note_account(page: Any) -> None:
    """Read-only proof that the active session owns trendhub_biz and has the expected creator name."""
    page.goto(PROFILE_SETTINGS_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1200)
    if base._looks_logged_out(page):
        raise base.NoteAuthenticationExpired("note authentication is not active for the expected account")
    if not str(page.url or "").startswith(PROFILE_SETTINGS_URL):
        raise base.NoteAuthenticationExpired("note profile settings could not be opened for the expected account")

    nickname = page.locator(CREATOR_NAME_SELECTOR)
    try:
        count = nickname.count()
    except Exception as exc:
        raise base.NoteDraftError("expected note creator identity could not be inspected") from exc
    if count != 1 or not nickname.first.is_visible(timeout=2500):
        raise base.NoteDraftError("expected note creator identity could not be proven")
    actual_name = " ".join(str(nickname.first.input_value() or "").split())
    if actual_name != EXPECTED_CREATOR_NAME:
        raise base.NoteDraftError("persistent note session belongs to an unexpected creator account")

    if not _settings_page_has_expected_profile_link(page):
        raise base.NoteDraftError("persistent note session does not own the expected note profile")


def _article_list_has_draft_id(page: Any, draft_id: str) -> bool:
    try:
        hrefs = page.locator("a[href]").evaluate_all(
            "els => els.map(el => el.getAttribute('href') || '').filter(Boolean)"
        )
    except Exception:
        return False
    expected_paths = {f"/notes/{draft_id}", f"/notes/{draft_id}/edit"}
    for raw in hrefs or []:
        try:
            parsed = urlparse(urljoin("https://note.com", str(raw)))
        except Exception:
            continue
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in {"note.com", "editor.note.com"}:
            continue
        if (parsed.path or "").rstrip("/") in expected_paths:
            return True
    return False


def _verify_draft_in_article_list(page: Any, draft_url: str) -> None:
    """Require the saved stable id to appear in the authenticated account's official article list."""
    draft_id = reconcile.draft_identity_from_url(draft_url, error_type=base.NoteDraftError)
    for attempt in range(4):
        page.goto(ARTICLE_LIST_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1200 + (attempt * 500))
        if base._looks_logged_out(page):
            raise base.NoteAuthenticationExpired("note authentication expired during draft-list verification")
        parsed = urlparse(str(page.url or ""))
        if parsed.scheme != "https" or (parsed.hostname or "").lower() != "note.com" or parsed.path != "/notes":
            raise base.NoteDraftError("note official article list could not be opened")
        if _article_list_has_draft_id(page, draft_id):
            return
    raise base.NoteDraftError("saved note draft identity was not present in the official article list")


def _establish_editor(page: Any, context: Any) -> None:
    """Reach the editor using persistent state, bootstrapping note.com state at most once."""
    try:
        run189._ensure_editor_route(page)
        return
    except (base.NoteAuthenticationExpired, base.NoteDraftError) as first_error:
        seeded = _seed_note_state(context, page)
        if not seeded:
            raise base.NoteAuthenticationExpired(
                "the persistent cloud Chrome profile is not ready for note; initialize or refresh its note.com login state"
            ) from first_error

    try:
        page.goto("https://note.com/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(900)
        run189._ensure_editor_route(page)
    except Exception as exc:
        raise base.NoteAuthenticationExpired(
            "note.com login bootstrap did not establish an editor session in persistent cloud Chrome"
        ) from exc


def _create_browser_draft(
    title: str,
    manuscript: str,
    eyecatch_path: Path,
    storage_path: Path,
    *,
    on_stable_draft_url: Callable[[str], None] | None = None,
) -> str:
    """Run the existing draft mutation/verification logic inside persistent real Chrome."""
    body_manuscript = base._body_manuscript_for_note(title, manuscript)
    del storage_path
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for note draft creation") from exc

    base.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = _launch_persistent_context(playwright)
        pages = list(context.pages)
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto("https://note.com/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1000)
            try:
                _assert_expected_note_account(page)
            except base.NoteAuthenticationExpired as first_error:
                seeded = _seed_note_state(context, page)
                if not seeded:
                    raise base.NoteAuthenticationExpired(
                        "the persistent cloud Chrome profile is not authenticated as the expected note account"
                    ) from first_error
                page.goto("https://note.com/", wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(900)
                _assert_expected_note_account(page)

            run189._ensure_editor_route(page)
            if not run187._is_editor_url(str(page.url or "")):
                raise base.NoteDraftError("persistent Chrome did not remain on a confirmed note editor route")

            base._upload_header_image(page, eyecatch_path)
            title_field = base._set_title(page, title)
            body = base._find_body(page, title_field)
            base._paste_manuscript(page, body, body_manuscript)
            body = base._find_body(page, title_field)
            base._verify_body_content(body, body_manuscript)
            draft_url = base._save_draft_and_verify(
                page,
                title,
                body_manuscript,
                image_required=True,
                on_stable_draft_url=on_stable_draft_url,
            )
            _verify_draft_in_article_list(page, draft_url)
            return draft_url
        except Exception:
            try:
                page.screenshot(path=str(base.ARTIFACT_DIR / "failure.png"), full_page=False)
            except Exception:
                pass
            raise
        finally:
            context.close()


def install() -> None:
    # Keep all Run185-193 fail-closed patches, replacing only browser lifecycle/auth storage.
    run193.install()
    run417.install(base)
    base._decode_storage_state = _compat_storage_path
    base._create_browser_draft = _create_browser_draft


def main() -> None:
    install()
    run185.main()


if __name__ == "__main__":
    main()
