#!/usr/bin/env python3
"""One-time local helper for creating NOTE_STORAGE_STATE_B64.

Run this only on the account owner's PC. It opens a normal headed browser, lets the user
sign in to note manually, then writes Playwright storage state as base64 to a local file.
The credential material is never printed. After copying it into the GitHub Actions secret
NOTE_STORAGE_STATE_B64, delete the generated file.

OAuth note:
Google sign-in navigates the same browser page away from note.com while authentication is
in progress. This helper deliberately waits for that round-trip to finish instead of issuing
a competing navigation, which previously could raise Playwright's
"Navigation ... is interrupted by another navigation" error.
"""
from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path
from urllib.parse import urlparse


def _is_note_session_page(url: str) -> bool:
    """Return True only for a stable note page suitable for storing a login session."""
    try:
        parsed = urlparse(str(url or ""))
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    if not (host == "note.com" or host.endswith(".note.com")):
        return False
    path = (parsed.path or "/").lower()
    blocked_prefixes = ("/login", "/signin", "/signup", "/auth")
    return not any(path.startswith(prefix) for prefix in blocked_prefixes)


def _wait_for_note_return(page, timeout_seconds: int = 180) -> str:
    """Wait for Google/other OAuth to return the current page to a stable note URL."""
    deadline = time.monotonic() + timeout_seconds
    last_url = str(page.url or "")
    while time.monotonic() < deadline:
        last_url = str(page.url or "")
        if _is_note_session_page(last_url):
            # Give note's client-side navigation/cookie writes a brief moment to settle.
            page.wait_for_timeout(1200)
            last_url = str(page.url or "")
            if _is_note_session_page(last_url):
                return last_url
        page.wait_for_timeout(500)
    raise SystemExit(
        "ログイン完了を確認できませんでした。ブラウザのアドレスが note.com に戻るまで"
        "ログイン操作を完了してから、もう一度実行してください。"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="note_storage_state.b64")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("Install first: pip install playwright && python -m playwright install chromium") from exc

    output = Path(args.output).resolve()
    state_json = output.with_suffix(".json")

    with sync_playwright() as playwright:
        browser = None
        try:
            try:
                browser = playwright.chromium.launch(channel="chrome", headless=False)
            except Exception:
                browser = playwright.chromium.launch(headless=False)
            context = browser.new_context(locale="ja-JP", timezone_id="Asia/Tokyo")
            page = context.new_page()
            page.goto("https://note.com/", wait_until="domcontentloaded", timeout=60000)
            print(
                "noteへ手動でログインしてください。Googleログインの場合も最後まで進め、"
                "ブラウザのアドレスが note.com に戻ったことを確認してから、このターミナルでEnterを押してください。"
            )
            input()

            current = _wait_for_note_return(page)
            print(f"noteへの復帰を確認しました: {current}")

            # Do not navigate to /new here. During Google OAuth that extra navigation can race
            # the provider callback. The workflow itself verifies editor access before doing
            # any draft mutation, so session capture only needs a stable authenticated note page.
            context.storage_state(path=str(state_json))
            raw = state_json.read_bytes()
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, dict) or not parsed.get("cookies"):
                raise SystemExit("有効なログインCookieを取得できませんでした。")

            note_cookies = [
                cookie
                for cookie in parsed.get("cookies") or []
                if str(cookie.get("domain") or "").lstrip(".").lower().endswith("note.com")
            ]
            if not note_cookies:
                raise SystemExit("note.com のCookieを取得できませんでした。ログインを確認して再実行してください。")

            output.write_bytes(base64.b64encode(raw))
            try:
                output.chmod(0o600)
            except OSError:
                pass
        finally:
            if browser is not None:
                browser.close()
            state_json.unlink(missing_ok=True)

    print(f"作成完了: {output}")
    print("このファイルの内容をGitHub Actions Secret『NOTE_STORAGE_STATE_B64』へ登録し、登録後はローカルファイルを削除してください。")


if __name__ == "__main__":
    main()
