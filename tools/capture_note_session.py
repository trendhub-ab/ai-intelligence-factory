#!/usr/bin/env python3
"""One-time local helper for creating NOTE_STORAGE_STATE_B64.

This version deliberately does NOT launch the login browser through Playwright. Google may
reject OAuth sign-in from an automation-launched browser as an unsafe browser. Instead we
launch the user's installed Google Chrome as a normal process with a temporary, isolated
Chrome profile and a local DevTools endpoint. The user completes note/Google login manually
inside that real Chrome window. Only after login succeeds does Playwright attach over CDP
and export the resulting note.com storage state.

Security:
- the normal Chrome profile is never touched;
- the temporary profile is repository-ignored and removed after a successful capture;
- credential material is never printed;
- the resulting base64 file must be stored only as GitHub Actions secret
  NOTE_STORAGE_STATE_B64 and then deleted locally.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

DEFAULT_CDP_PORT = 9222


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


def _chrome_candidates() -> list[Path]:
    values = []
    for root in (
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("LOCALAPPDATA"),
    ):
        if not root:
            continue
        values.append(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe")
    return values


def _find_chrome() -> Path:
    for candidate in _chrome_candidates():
        if candidate.is_file():
            return candidate
    raise SystemExit(
        "Google Chrome が見つかりませんでした。通常版Chromeをインストールしてから再実行してください。"
    )


def _wait_for_cdp(port: int, timeout_seconds: int = 20) -> None:
    endpoint = f"http://127.0.0.1:{port}/json/version"
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(endpoint, timeout=1.0) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.25)
    raise SystemExit(
        "通常版Chromeのセッション取得ポートを開始できませんでした。Chromeをすべて閉じてから再実行してください。"
    )


def _launch_real_chrome(chrome: Path, profile_dir: Path, port: int) -> subprocess.Popen:
    profile_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(chrome),
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://note.com/",
    ]
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(command, creationflags=creationflags)


def _select_note_context(browser):
    for context in browser.contexts:
        for page in context.pages:
            if _is_note_session_page(str(page.url or "")):
                return context, page
    # A successfully logged-in user may leave the current tab elsewhere. The note cookies
    # still live in the same default CDP context, so accept the first available context and
    # validate the exported note.com cookies below.
    if browser.contexts:
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else None
        return context, page
    raise SystemExit("Chromeのブラウザコンテキストを取得できませんでした。")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="note_storage_state.b64")
    parser.add_argument("--port", type=int, default=DEFAULT_CDP_PORT)
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("Install first: pip install playwright") from exc

    output = Path(args.output).resolve()
    state_json = output.with_suffix(".json")
    profile_dir = (Path.cwd() / ".note-session-chrome").resolve()
    chrome = _find_chrome()

    print("通常版Google Chromeを専用プロファイルで開きます。")
    print("このChrome内でnoteへログインしてください。Googleログインを使って構いません。")
    print("ログイン後、note.com のトップやマイページが表示されたことを確認してください。")

    process = _launch_real_chrome(chrome, profile_dir, args.port)
    try:
        _wait_for_cdp(args.port)
        input("ログインが完了したら、このPowerShellに戻ってEnterを押してください。\n")

        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{args.port}")
            try:
                context, page = _select_note_context(browser)
                if page is not None:
                    current = str(page.url or "")
                    print(f"Chrome接続を確認しました: {current}")

                context.storage_state(path=str(state_json))
                raw = state_json.read_bytes()
                parsed = json.loads(raw.decode("utf-8"))
                if not isinstance(parsed, dict) or not parsed.get("cookies"):
                    raise SystemExit("有効なCookieを取得できませんでした。")

                note_cookies = [
                    cookie
                    for cookie in parsed.get("cookies") or []
                    if str(cookie.get("domain") or "").lstrip(".").lower().endswith("note.com")
                ]
                if not note_cookies:
                    raise SystemExit(
                        "note.com のログインCookieを取得できませんでした。noteへログインできていることを確認して再実行してください。"
                    )

                output.write_bytes(base64.b64encode(raw))
                try:
                    output.chmod(0o600)
                except OSError:
                    pass
            finally:
                browser.close()
    finally:
        state_json.unlink(missing_ok=True)
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    # The temporary Chrome profile contains the same authenticated session and is no longer
    # needed after storage-state export. Remove it best-effort; if Chrome still has a file
    # handle open, leave the ignored local directory and tell the user to delete it manually.
    try:
        shutil.rmtree(profile_dir, ignore_errors=False)
    except Exception:
        print(f"注意: 一時Chromeプロファイルを削除できませんでした。Chromeを閉じた後に削除してください: {profile_dir}")

    print(f"作成完了: {output}")
    print("このファイルの内容をGitHub Actions Secret『NOTE_STORAGE_STATE_B64』へ登録し、登録後はローカルファイルを削除してください。")


if __name__ == "__main__":
    main()
