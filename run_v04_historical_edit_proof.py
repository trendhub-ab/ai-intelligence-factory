"""Read-only v0.4 reconciliation of one previously visited note edit route.

Never logs candidate URLs, opaque note IDs, account contents, manuscript
or HTML. A history visit is only a lead, not proof of a saved draft.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
from urllib.parse import urlsplit

_ROUTE_PATH = re.compile(r"/notes/[A-Za-z0-9_-]{1,200}/edit")
_ALLOWED_HOSTS = {"note.com", "editor.note.com"}
_HISTORY_WINDOW_BEFORE = timedelta(seconds=90)
_HISTORY_WINDOW_AFTER = timedelta(minutes=4)
_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)

# Bounded, publicly reportable classification. Never include URLs/IDs.
_EMPTY = {
    "history_edit_candidate": "UNAVAILABLE",
    "history_edit_route": "NOT_CHECKED",
    "history_edit_title": "NOT_CHECKED",
    "history_edit_body": "NOT_CHECKED",
}


def _valid_edit_url(raw: str) -> str | None:
    try:
        p = urlsplit(str(raw or ""))
        if (p.scheme != "https" or p.hostname not in _ALLOWED_HOSTS
                or p.username or p.password or p.port not in (None, 443)
                or p.query or p.fragment or not _ROUTE_PATH.fullmatch(p.path)):
            return None
        return p.geturl()
    except (ValueError, TypeError):
        return None


def _history_candidates(started_at: str, *, profile_dir: Path | None = None) -> tuple[str, list[str]]:
    """Read a copied Chrome History DB and return at most 3 bounded edit routes."""
    try:
        began = datetime.fromisoformat(started_at)
        if began.tzinfo is None:
            return "UNAVAILABLE", []
        lo = int(((began.astimezone(timezone.utc) - _HISTORY_WINDOW_BEFORE) - _EPOCH).total_seconds() * 1e6)
        hi = int(((began.astimezone(timezone.utc) + _HISTORY_WINDOW_AFTER) - _EPOCH).total_seconds() * 1e6)
        if profile_dir is None:
            import run190_note_persistent_cloud as cloud
            profile_dir = cloud._profile_dir()
        paths = sorted(
            f for f in profile_dir.rglob("History")
            if f.is_file() and f.stat().st_size < 100_000_000
        )[:12]
        inspected = False
        candidates: dict[str, str] = {}
        with tempfile.TemporaryDirectory(prefix="v04-history-proof-") as tmp:
            for index, src in enumerate(paths):
                try:
                    dest = Path(tmp) / f"History-{index}.sqlite"
                    shutil.copy2(src, dest)
                    with sqlite3.connect(f"file:{dest}?mode=ro", uri=True) as db:
                        rows = db.execute(
                            "SELECT u.url FROM visits v JOIN urls u ON u.id=v.url "
                            "WHERE v.visit_time BETWEEN ? AND ? LIMIT 1024",
                            (lo, hi),
                        ).fetchall()
                    inspected = True
                except (OSError, sqlite3.Error, ValueError):
                    continue
                for (raw,) in rows:
                    url = _valid_edit_url(raw)
                    if url is None:
                        continue
                    parsed = urlsplit(url)
                    # Treat note.com and editor.note.com as aliases of one ID.
                    article_id = parsed.path.split("/")[2]
                    candidates.setdefault(article_id, url)
                    if len(candidates) > 3:
                        return "MULTIPLE", []
        if not inspected:
            return "UNAVAILABLE", []
        if not candidates:
            return "NONE", []
        if len(candidates) > 1:
            return "MULTIPLE", []
        return "ONE", list(candidates.values())
    except Exception:
        return "UNAVAILABLE", []


def _safe_title(field) -> str:
    tag = str(field.evaluate("el => el.tagName.toLowerCase()")).lower()
    if tag in {"input", "textarea"}:
        return str(field.input_value(timeout=2000) or "").strip()
    return str(field.inner_text(timeout=2000) or "").strip()


def _classify_body(expected: str, seen: str) -> str:
    normalize = lambda s: " ".join(str(s or "").split())
    expected = normalize(expected)
    seen = normalize(seen)
    if not seen:
        return "EMPTY"
    if not expected:
        return "UNINSPECTABLE"
    if seen == expected:
        return "EXACT"
    if len(seen) >= 32 and (
        expected.startswith(seen) or seen.startswith(expected[: min(len(expected), 120)])
    ):
        return "PREFIX_ONLY"
    return "OTHER"


def _only_get(route) -> None:
    """Block network mutation from the temporary inspection context."""
    if str(route.request.method).upper() in {"GET", "HEAD", "OPTIONS"}:
        route.continue_()
    else:
        route.abort()


def _read_only_editor_view(candidate_url: str, title: str, manuscript: str) -> dict:
    """Use an isolated no-service-worker Chrome context, no click/fill/save."""
    result = {"history_edit_route": "UNINSPECTABLE",
              "history_edit_title": "NOT_CHECKED",
              "history_edit_body": "NOT_CHECKED"}
    if not _valid_edit_url(candidate_url):
        return result
    try:
        import note_draft_automation as base
        import note_publication_reconcile as reconcile
        import run190_note_persistent_cloud as cloud
        import run187_note_editor_readiness as readiness
        import run_v04_note_body_locator as body_locator
        from playwright.sync_api import sync_playwright

        expected_id = reconcile.draft_identity_from_url(candidate_url)
        body_markdown = base._body_manuscript_for_note(title, manuscript)
        expected_body = base._plain_manuscript_text(body_markdown)
        with sync_playwright() as playwright:
            persistent = cloud._launch_persistent_context(playwright)
            try:
                browser = persistent.browser
                if browser is None:
                    return result
                # Copy authentication into a temporary isolated context. Never
                # navigate historical edits in the owner persistent tab.
                temporary = browser.new_context(
                    storage_state=persistent.storage_state(),
                    service_workers="block", locale="ja-JP",
                )
                try:
                    temporary.route("**/*", _only_get)
                    page = temporary.new_page()
                    page.set_default_timeout(10000)
                    try:
                        cloud._assert_expected_note_account(page)
                    except Exception:
                        result["history_edit_route"] = "ACCOUNT_UNVERIFIED"
                        return result
                    try:
                        page.goto(candidate_url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(1200)
                        actual_url = str(page.url or "")
                        if not _valid_edit_url(actual_url):
                            result["history_edit_route"] = "NO_VERIFIED_EDITOR"
                            return result
                        if reconcile.draft_identity_from_url(actual_url) != expected_id:
                            result["history_edit_route"] = "NO_VERIFIED_EDITOR"
                            return result
                        if not readiness._is_editor_url(actual_url):
                            result["history_edit_route"] = "NO_VERIFIED_EDITOR"
                            return result
                        result["history_edit_route"] = "EDITOR_ROUTE_OPENED"
                        field = base._find_title(page)
                        observed_title = _safe_title(field)
                        if not observed_title:
                            result["history_edit_title"] = "EMPTY"
                            return result
                        if " ".join(observed_title.split()) != " ".join(title.split()):
                            result["history_edit_title"] = "OTHER"
                            return result
                        result["history_edit_title"] = "MATCH"
                        try:
                            body = body_locator.find_body(page, field)
                            seen = str(body.inner_text(timeout=3000) or "")
                            result["history_edit_body"] = _classify_body(expected_body, seen)
                        except Exception:
                            result["history_edit_body"] = "UNINSPECTABLE"
                        return result
                    except Exception:
                        return result
                finally:
                    temporary.close()
            finally:
                persistent.close()
    except Exception:
        return result


def investigate(started_at: str, title: str, manuscript: str,
                *, history_reader=_history_candidates,
                editor_reader=_read_only_editor_view) -> dict:
    """Fixed enums only; this is NOT permission to clear the delivery ledger."""
    candidate_status, candidates = history_reader(started_at)
    if candidate_status not in {"UNAVAILABLE", "NONE", "ONE", "MULTIPLE"}:
        raise ValueError("V04_HISTORY_PROBE_INVALID")
    report = {**_EMPTY, "history_edit_candidate": candidate_status}
    if candidate_status != "ONE":
        return report
    if len(candidates) != 1 or not _valid_edit_url(candidates[0]):
        raise ValueError("V04_HISTORY_PROBE_INVALID")
    details = editor_reader(candidates[0], title, manuscript)
    if not isinstance(details, dict) or set(details) != {
        "history_edit_route", "history_edit_title", "history_edit_body"
    }:
        raise ValueError("V04_HISTORY_PROBE_INVALID")
    enums = {
        "history_edit_route": {"UNINSPECTABLE", "ACCOUNT_UNVERIFIED", "NO_VERIFIED_EDITOR", "EDITOR_ROUTE_OPENED"},
        "history_edit_title": {"NOT_CHECKED", "EMPTY", "OTHER", "MATCH"},
        "history_edit_body": {"NOT_CHECKED", "EMPTY", "OTHER", "EXACT", "PREFIX_ONLY", "UNINSPECTABLE"},
    }
    if any(details[key] not in allowed for key, allowed in enums.items()):
        raise ValueError("V04_HISTORY_PROBE_INVALID")
    if details["history_edit_route"] != "EDITOR_ROUTE_OPENED" and (
        details["history_edit_title"] != "NOT_CHECKED" or details["history_edit_body"] != "NOT_CHECKED"
    ):
        raise ValueError("V04_HISTORY_PROBE_INVALID")
    if details["history_edit_title"] != "MATCH" and details["history_edit_body"] != "NOT_CHECKED":
        raise ValueError("V04_HISTORY_PROBE_INVALID")
    return {**report, **details}
