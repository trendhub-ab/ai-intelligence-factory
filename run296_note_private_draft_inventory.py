#!/usr/bin/env python3
"""Run296: read-only inventory of all remaining unpublished note drafts.

Safety contract:
- list drafts only through note's authenticated read-only GET endpoint;
- navigate only to existing private edit routes returned by that draft-only listing;
- never click, fill, type, upload, save, delete, publish, withdraw, or screenshot;
- never call Gemini/model providers;
- never emit unpublished title/body, draft URL, draft ID, or content fingerprint;
- classify only as KEEP / REPAIR / DISCARD_CANDIDATE;
- AI-style diagnostics alone can only produce REPAIR;
- any draft identity already tracked by AIIF/Notion is protected from DISCARD_CANDIDATE.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import editorial_naturalness
import note_draft_automation as note_base
import note_eyecatch_persistence as eyecatch
import note_publication_reconcile as note_lifecycle
import note_ready_sync as ready_sync
import run187_note_editor_readiness as run187
import run190_note_persistent_cloud as run190

CONFIRM_TOKEN = "AUDIT_ALL_NOTE_DRAFTS"
DRAFT_LIST_URL = "https://note.com/notes?page=1&status=draft"
DRAFT_LIST_API = "https://note.com/api/v2/note_list/contents"
MAX_LIST_PAGES = 50
LIST_LIMIT = 20
MIN_SUBSTANTIAL_BODY_CHARS = 200
_EDIT_PATH = re.compile(r"^/notes/([A-Za-z0-9_-]+)/edit/?$")
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_ALLOWED_SAFE_KEYS = {
    "position",
    "title_chars",
    "body_chars",
    "eyecatch_present",
    "eyecatch_state",
    "naturalness_high",
    "naturalness_score",
    "current_aiif_linked",
    "exact_duplicate_of",
    "classification",
    "reasons",
}


class InventoryError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = str(code)


def _normalized_visible(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def _visible_chars(value: str) -> int:
    return len(re.sub(r"\s+", "", str(value or "")))


def extract_edit_routes(hrefs: list[str]) -> list[str]:
    """Return canonical note edit routes only, preserving first-seen order."""
    result: list[str] = []
    seen: set[str] = set()
    for raw in hrefs:
        value = str(raw or "").strip()
        if not value or value.lower().startswith(("javascript:", "data:")):
            continue
        try:
            absolute = urljoin("https://note.com", value)
            parsed = urlparse(absolute)
        except Exception:
            continue
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in {"note.com", "editor.note.com"}:
            continue
        match = _EDIT_PATH.fullmatch(parsed.path or "")
        if not match or parsed.params or parsed.query or parsed.fragment:
            continue
        canonical = f"https://note.com/notes/{match.group(1)}/edit"
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


def draft_routes_from_api_payload(payload: dict[str, Any]) -> list[str]:
    """Convert only API-confirmed draft identities into private editor routes."""
    if not isinstance(payload, dict):
        raise InventoryError("draft_api_schema_invalid")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise InventoryError("draft_api_schema_invalid")
    notes = data.get("notes")
    if not isinstance(notes, list):
        raise InventoryError("draft_api_schema_invalid")

    routes: list[str] = []
    seen: set[str] = set()
    for item in notes:
        if not isinstance(item, dict):
            raise InventoryError("draft_api_schema_invalid")
        if str(item.get("status") or "").strip().lower() != "draft":
            raise InventoryError("draft_api_scope_violation")
        key = str(item.get("key") or "").strip()
        if not key or len(key) > 200 or not _OPAQUE_ID.fullmatch(key):
            raise InventoryError("draft_api_identity_missing")
        route = f"https://editor.note.com/notes/{key}/edit/"
        if route not in seen:
            seen.add(route)
            routes.append(route)
    return routes


def classify_draft(
    *,
    title_chars: int,
    body_chars: int,
    eyecatch_present: bool,
    naturalness_high: bool,
    current_aiif_linked: bool,
    exact_duplicate_of: int | None,
) -> dict[str, Any]:
    """Classify conservatively; only strong structural waste becomes discard candidate."""
    title_chars = max(0, int(title_chars or 0))
    body_chars = max(0, int(body_chars or 0))
    reasons: list[str] = []

    if current_aiif_linked:
        if body_chars == 0 or title_chars == 0:
            reasons.append("tracked_draft_incomplete")
        if not eyecatch_present:
            reasons.append("eyecatch_missing_or_unconfirmed")
        if naturalness_high:
            reasons.append("naturalness_high")
        if exact_duplicate_of is not None:
            reasons.append("tracked_exact_duplicate_review")
        if reasons:
            return {"classification": "REPAIR", "reasons": reasons}
        return {"classification": "KEEP", "reasons": []}

    if exact_duplicate_of is not None:
        return {"classification": "DISCARD_CANDIDATE", "reasons": ["exact_duplicate"]}

    if body_chars == 0:
        if eyecatch_present:
            reasons.append("eyecatch_only_empty_body")
        else:
            reasons.append("empty_draft")
        return {"classification": "DISCARD_CANDIDATE", "reasons": reasons}

    if title_chars == 0:
        reasons.append("title_missing")
    if body_chars < MIN_SUBSTANTIAL_BODY_CHARS:
        reasons.append("body_incomplete")
    if not eyecatch_present:
        reasons.append("eyecatch_missing_or_unconfirmed")
    if naturalness_high:
        # Editorial naturalness is intentionally a repair signal only.
        reasons.append("naturalness_high")

    if reasons:
        return {"classification": "REPAIR", "reasons": reasons}
    return {"classification": "KEEP", "reasons": []}


def safe_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Strip all private content/identity fields before persistence or logging."""
    safe = {key: raw.get(key) for key in _ALLOWED_SAFE_KEYS if key in raw}
    safe["position"] = int(safe.get("position") or 0)
    safe["title_chars"] = int(safe.get("title_chars") or 0)
    safe["body_chars"] = int(safe.get("body_chars") or 0)
    safe["eyecatch_present"] = bool(safe.get("eyecatch_present"))
    safe["naturalness_high"] = bool(safe.get("naturalness_high"))
    safe["naturalness_score"] = int(safe.get("naturalness_score") or 0)
    safe["current_aiif_linked"] = bool(safe.get("current_aiif_linked"))
    if safe.get("exact_duplicate_of") is not None:
        safe["exact_duplicate_of"] = int(safe["exact_duplicate_of"])
    safe["classification"] = str(safe.get("classification") or "REPAIR")
    safe["reasons"] = [str(x) for x in (safe.get("reasons") or [])]
    return safe


def _tracked_draft_ids() -> set[str]:
    """Read AIIF destination identities so tracked drafts can never be discard candidates."""
    try:
        pages = ready_sync._query_db(
            ready_sync.DEST_DATA_SOURCE_ID,
            ready_sync.DEST_DATABASE_ID,
            payload={},
        )
    except Exception as exc:
        raise InventoryError("aiif_draft_protection_lookup_failed") from exc

    tracked: set[str] = set()
    for page in pages:
        props = (page or {}).get("properties") or {}
        draft_id = ready_sync._text(props.get(note_lifecycle.DRAFT_ID_PROPERTY)).strip()
        if draft_id:
            tracked.add(draft_id)
    return tracked


def _seed_if_needed(context: Any, page: Any, target_url: str) -> None:
    if not note_base._looks_logged_out(page):
        return
    seeded = bool(run190._seed_note_state(context, page))
    if not seeded:
        raise InventoryError("note_auth_inactive")
    try:
        page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1000)
    except Exception as exc:
        raise InventoryError("note_route_reopen_failed") from exc
    if note_base._looks_logged_out(page):
        raise InventoryError("note_auth_inactive")


def _open_authenticated_draft_management(context: Any, page: Any) -> None:
    try:
        page.goto(DRAFT_LIST_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1000)
    except Exception as exc:
        raise InventoryError("draft_listing_open_failed") from exc
    _seed_if_needed(context, page, DRAFT_LIST_URL)
    parsed = urlparse(str(page.url or ""))
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != "note.com":
        raise InventoryError("draft_listing_scope_not_confirmed")


def _fetch_draft_api_page(page: Any, page_number: int) -> tuple[list[str], bool | None]:
    endpoint = (
        f"{DRAFT_LIST_API}?limit={LIST_LIMIT}&page={int(page_number)}"
        "&status=draft&without_magazines=true"
    )
    try:
        response = page.evaluate(
            """async (url) => {
                const res = await fetch(url, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {'Accept': 'application/json'}
                });
                let body = null;
                try { body = await res.json(); } catch (_) { body = null; }
                return {ok: res.ok, status: res.status, body};
            }""",
            endpoint,
        )
    except Exception as exc:
        raise InventoryError("draft_api_request_failed") from exc
    if not isinstance(response, dict) or not response.get("ok"):
        raise InventoryError("draft_api_request_failed")
    payload = response.get("body")
    if not isinstance(payload, dict):
        raise InventoryError("draft_api_schema_invalid")
    routes = draft_routes_from_api_payload(payload)
    data = payload.get("data") or {}
    marker = data.get("isLastPage")
    is_last = marker if isinstance(marker, bool) else None
    return routes, is_last


def _discover_all_draft_routes(context: Any, page: Any) -> list[str]:
    """List all drafts from the authenticated draft-only GET endpoint; no DOM inference."""
    _open_authenticated_draft_management(context, page)
    routes: list[str] = []
    seen: set[str] = set()

    for page_number in range(1, MAX_LIST_PAGES + 1):
        page_routes, is_last = _fetch_draft_api_page(page, page_number)
        new_routes = [route for route in page_routes if route not in seen]
        for route in new_routes:
            seen.add(route)
            routes.append(route)

        if is_last is True:
            break
        if not page_routes or len(page_routes) < LIST_LIMIT:
            break
        if page_number > 1 and not new_routes:
            raise InventoryError("draft_api_pagination_stalled")
    else:
        raise InventoryError("draft_api_pagination_unbounded")

    return routes


def _read_title(title_field: Any) -> str:
    try:
        tag = str(title_field.evaluate("el => el.tagName.toLowerCase()"))
        if tag in {"input", "textarea"}:
            return str(title_field.input_value() or "")
        return str(title_field.inner_text() or "")
    except Exception as exc:
        raise InventoryError("draft_title_read_failed") from exc


def _inspect_one(page: Any, route: str, *, position: int, tracked_ids: set[str]) -> dict[str, Any]:
    try:
        page.goto(route, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(900)
    except Exception as exc:
        raise InventoryError("draft_editor_open_failed") from exc
    if note_base._looks_logged_out(page):
        raise InventoryError("note_auth_inactive")
    if not run187._is_editor_url(str(page.url or "")):
        raise InventoryError("draft_editor_route_invalid")

    try:
        title_field = note_base._find_title(page)
        title = _read_title(title_field)
        body = note_base._find_body(page, title_field)
        body_text = str(body.inner_text(timeout=5000) or "")
    except InventoryError:
        raise
    except Exception as exc:
        raise InventoryError("draft_content_read_failed") from exc

    normalized_title = _normalized_visible(title)
    normalized_body = _normalized_visible(body_text)
    title_chars = _visible_chars(normalized_title)
    body_chars = _visible_chars(normalized_body)

    try:
        eye_metrics = eyecatch.collect_eyecatch_metrics(page, title_locator=title_field)
        eye_state = eyecatch.classify_eyecatch_persistence(eye_metrics)
        eye_present = eyecatch.eyecatch_persistence_confirmed(eye_metrics)
    except Exception as exc:
        raise InventoryError("eyecatch_read_failed") from exc

    naturalness = {"score": 0, "high": False}
    if body_chars >= MIN_SUBSTANTIAL_BODY_CHARS:
        try:
            naturalness = editorial_naturalness.ai_style_composite_signals(normalized_body, [])
        except Exception:
            # Diagnostic failure must never turn a draft into a discard candidate.
            naturalness = {"score": 0, "high": False}

    try:
        draft_id = note_lifecycle.draft_identity_from_url(route, error_type=InventoryError)
    except Exception as exc:
        if isinstance(exc, InventoryError):
            raise
        raise InventoryError("draft_identity_invalid") from exc

    fingerprint = hashlib.sha256(
        (normalized_title + "\0" + normalized_body).encode("utf-8")
    ).hexdigest()
    return {
        "position": position,
        "title": title,
        "body": body_text,
        "draft_url": route,
        "draft_id": draft_id,
        "body_fingerprint": fingerprint,
        "title_chars": title_chars,
        "body_chars": body_chars,
        "eyecatch_present": bool(eye_present),
        "eyecatch_state": str(eye_state),
        "naturalness_high": bool(naturalness.get("high")),
        "naturalness_score": int(naturalness.get("score") or 0),
        "current_aiif_linked": draft_id in tracked_ids,
        "exact_duplicate_of": None,
    }


def _mark_exact_duplicates(records: list[dict[str, Any]]) -> None:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        fingerprint = str(record.get("body_fingerprint") or "")
        if fingerprint:
            groups[fingerprint].append(record)
    for group in groups.values():
        if len(group) < 2:
            continue
        linked = [row for row in group if row.get("current_aiif_linked")]
        keeper = linked[0] if linked else group[0]
        keeper_position = int(keeper["position"])
        for row in group:
            if row is not keeper:
                row["exact_duplicate_of"] = keeper_position


def _classify_records(records: list[dict[str, Any]]) -> None:
    for row in records:
        decision = classify_draft(
            title_chars=int(row.get("title_chars") or 0),
            body_chars=int(row.get("body_chars") or 0),
            eyecatch_present=bool(row.get("eyecatch_present")),
            naturalness_high=bool(row.get("naturalness_high")),
            current_aiif_linked=bool(row.get("current_aiif_linked")),
            exact_duplicate_of=row.get("exact_duplicate_of"),
        )
        row.update(decision)


def run(*, confirm: str) -> dict[str, Any]:
    if confirm != CONFIRM_TOKEN:
        raise InventoryError("confirmation_invalid")

    tracked_ids = _tracked_draft_ids()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise InventoryError("playwright_missing") from exc

    raw_records: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        context = run190._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            routes = _discover_all_draft_routes(context, page)
            for position, route in enumerate(routes, start=1):
                try:
                    raw_records.append(
                        _inspect_one(page, route, position=position, tracked_ids=tracked_ids)
                    )
                except InventoryError as exc:
                    if exc.code == "note_auth_inactive":
                        raise
                    # Preserve uncertain items as repair work; never discard what could not be inspected.
                    try:
                        draft_id = note_lifecycle.draft_identity_from_url(route, error_type=InventoryError)
                    except Exception:
                        draft_id = ""
                    raw_records.append(
                        {
                            "position": position,
                            "title_chars": 0,
                            "body_chars": 0,
                            "eyecatch_present": False,
                            "eyecatch_state": "unconfirmed",
                            "naturalness_high": False,
                            "naturalness_score": 0,
                            "current_aiif_linked": bool(draft_id and draft_id in tracked_ids),
                            "exact_duplicate_of": None,
                            "classification": "REPAIR",
                            "reasons": [f"inspection_failed:{exc.code}"],
                        }
                    )
        finally:
            context.close()

    inspectable = [row for row in raw_records if "body_fingerprint" in row]
    _mark_exact_duplicates(inspectable)
    _classify_records(inspectable)

    safe_records = [safe_record(row) for row in raw_records]
    counts = Counter(str(row.get("classification") or "REPAIR") for row in safe_records)
    return {
        "success": True,
        "status": "inventory_complete",
        "read_only": True,
        "zero_gemini_calls": True,
        "draft_mutation": False,
        "public_release": False,
        "private_content_exposed": False,
        "total": len(safe_records),
        "counts": {
            "KEEP": counts.get("KEEP", 0),
            "REPAIR": counts.get("REPAIR", 0),
            "DISCARD_CANDIDATE": counts.get("DISCARD_CANDIDATE", 0),
        },
        "records": safe_records,
    }


def _safe_failure(code: str) -> dict[str, Any]:
    return {
        "success": False,
        "status": "fail_closed",
        "diagnostic_code": str(code),
        "read_only": True,
        "zero_gemini_calls": True,
        "draft_mutation": False,
        "public_release": False,
        "private_content_exposed": False,
        "total": None,
        "counts": {},
        "records": [],
    }


def _write_result(path_value: str, result: dict[str, Any]) -> None:
    if not path_value:
        return
    target = Path(path_value)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", default=os.environ.get("NOTE_INVENTORY_CONFIRM", ""))
    parser.add_argument("--result-file", default=os.environ.get("NOTE_INVENTORY_RESULT_FILE", ""))
    args = parser.parse_args()

    exit_code = 0
    try:
        result = run(confirm=args.confirm)
    except InventoryError as exc:
        result = _safe_failure(exc.code)
        exit_code = 2
    except Exception:
        result = _safe_failure("unexpected_inventory_failure")
        exit_code = 2

    _write_result(args.result_file, result)
    print(json.dumps(result, ensure_ascii=False))
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
