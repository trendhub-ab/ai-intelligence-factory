#!/usr/bin/env python3
"""One-time local helper for creating NOTE_STORAGE_STATE_B64.

Run this only on the account owner's PC. It opens a normal headed browser, lets the user
sign in to note manually, then writes Playwright storage state as base64 to a local file.
The credential material is never printed. After copying it into the GitHub Actions secret
NOTE_STORAGE_STATE_B64, delete the generated file.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path


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
            print("noteへ手動でログインしてください。ログイン完了後、このターミナルに戻ってEnterを押してください。")
            input()
            page.goto("https://note.com/new", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)
            current = str(page.url or "").lower()
            if any(token in current for token in ("/login", "/signin", "/signup")):
                raise SystemExit("ログイン状態を確認できませんでした。noteへログインしてから再実行してください。")
            context.storage_state(path=str(state_json))
            raw = state_json.read_bytes()
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, dict) or not parsed.get("cookies"):
                raise SystemExit("有効なログインCookieを取得できませんでした。")
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
