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
- existing Ready/article, header-image, persistence and Notion fail-closed guards remain.
"""
from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import note_draft_automation as base
import run185_note_ready_legacy_skip as run185
import run189_note_editor_route_gate as run189
import run191_note_crop_dialog_resilience as run191
import run187_note_editor_readiness as run187


PROFILE_ENV = "NOTE_CHROME_USER_DATA_DIR"
CHANNEL_ENV = "NOTE_CHROME_CHANNEL"
HEADLESS_ENV = "NOTE_CHROME_HEADLESS"
DEFAULT_PROFILE_DIR = Path.home() / ".aiif-note" / "chrome-profile"
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


def _create_browser_draft(title: str, manuscript: str, eyecatch_path: Path, storage_path: Path) -> str:
    """Run the existing draft mutation/verification logic inside persistent real Chrome."""
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
            _establish_editor(page, context)
            if not run187._is_editor_url(str(page.url or "")):
                raise base.NoteDraftError("persistent Chrome did not remain on a confirmed note editor route")

            base._upload_header_image(page, eyecatch_path)
            title_field = base._set_title(page, title)
            body = base._find_body(page, title_field)
            base._paste_manuscript(page, body, manuscript)
            body = base._find_body(page, title_field)
            base._verify_body_content(body, manuscript)
            return base._save_draft_and_verify(page, title, manuscript, image_required=True)
        except Exception:
            try:
                page.screenshot(path=str(base.ARTIFACT_DIR / "failure.png"), full_page=False)
            except Exception:
                pass
            raise
        finally:
            context.close()


def install() -> None:
    # Keep all Run185-191 fail-closed patches, replacing only browser lifecycle/auth storage.
    run191.install()
    base._decode_storage_state = _compat_storage_path
    base._create_browser_draft = _create_browser_draft


def main() -> None:
    install()
    run185.main()


if __name__ == "__main__":
    main()
