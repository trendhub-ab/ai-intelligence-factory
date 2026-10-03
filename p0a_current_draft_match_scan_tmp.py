#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlparse, urlunparse

import note_document_contract as contract
import note_document_dom as dom
import note_draft_automation as note_base
import note_ready_sync as ready_sync
import run190_note_persistent_cloud as cloud
import run222_note_presentation_integrity as run222
import run291_note_private_draft_audit as audit291

MAX_ELIGIBLE_ROWS = 50
_URL_RE = re.compile(r"https?://[^\s\]\)\}\>\"']+")


def normalize_external_url(raw: str) -> str:
    try:
        parsed = urlparse(str(raw or "").strip().rstrip(".,;:!?"))
    except Exception:
        return ""
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        return ""
    if host in {"note.com", "www.note.com", "editor.note.com"}:
        return ""
    return urlunparse((parsed.scheme.lower(), host, parsed.path or "/", "", parsed.query, ""))


def expected_external_urls(markdown_text: str) -> frozenset[str]:
    return frozenset(
        value
        for value in (normalize_external_url(raw) for raw in _URL_RE.findall(str(markdown_text or "")))
        if value
    )


def destination_candidates() -> list[dict]:
    pages = ready_sync._query_db(ready_sync.DEST_DATA_SOURCE_ID, ready_sync.DEST_DATABASE_ID)
    result: list[dict] = []
    for page in pages:
        props = page.get("properties") or {}
        if ready_sync._select(props.get("品質状態")) != "Ready":
            continue
        if ready_sync._select(props.get("投稿状態")) != "投稿準備中":
            continue
        if ready_sync._url(props.get("note公開URL")):
            continue
        if str((((props.get("投稿日") or {}).get("date") or {}).get("start")) or "").strip():
            continue
        sync_id = ready_sync._normalize_page_id(ready_sync._text(props.get("同期ID")))
        title = ready_sync._text(props.get("記事タイトル")).strip()
        if len(sync_id) != 32 or not title:
            continue
        result.append({"sync_id": sync_id, "title": title})
    if len(result) > MAX_ELIGIBLE_ROWS:
        raise RuntimeError("eligible_row_safety_limit_exceeded")
    return result


def current_contracts(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        sync_id = row["sync_id"]
        try:
            response = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{sync_id}")
            if response.status_code != 200:
                continue
            state = ready_sync._source_state(response.json())
            if not state or state.get("sync_id") != sync_id:
                continue
            if str(state.get("title") or "").strip() != row["title"]:
                continue
            manuscript = ready_sync._source_current_ready_manuscript(sync_id)
            if not manuscript:
                continue
            presented = run222.prepare_note_editor_manuscript(manuscript, row["title"])
            expected_doc = contract.normalize_document(contract.parse_presentation_markdown(presented))
            out.append({
                "sync_id": sync_id,
                "title": row["title"],
                "document": expected_doc,
                "evidence": expected_external_urls(presented),
            })
        except Exception:
            continue
    return out


def body_external_urls(body) -> frozenset[str]:
    try:
        hrefs = body.locator("a[href]").evaluate_all("els => els.map(a => a.href || '')")
    except Exception:
        hrefs = []
    return frozenset(value for value in (normalize_external_url(raw) for raw in (hrefs or [])) if value)


def main() -> int:
    rows = destination_candidates()
    contracts = current_contracts(rows)
    history = cloud._recent_private_edit_urls(cloud._profile_dir())
    readable_editors = 0
    convertible_editors = 0
    canonical_match_pairs: list[tuple[str, str]] = []
    title_canonical_match_pairs: list[tuple[str, str]] = []
    exact_evidence_pairs = 0
    seeded = False

    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            for candidate in history:
                try:
                    page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(700)
                    if note_base._looks_logged_out(page) and not seeded:
                        seeded = bool(cloud._seed_note_state(context, page))
                        if seeded:
                            page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
                            page.wait_for_timeout(700)
                    if note_base._looks_logged_out(page) or not audit291._is_note_edit_url(str(page.url or "")):
                        continue
                    title_field = note_base._find_title(page)
                    actual_title = audit291._title_value(page)
                    body = note_base._find_body(page, title_field)
                    snapshot = dom.snapshot_note_body(body)
                    readable_editors += 1
                    actual_doc = dom.document_from_note_snapshot(
                        snapshot,
                        allowed_normalizations=(contract.NOTE_LIST_ITEM_PARAGRAPH_WRAPPER,),
                    )
                    convertible_editors += 1
                    actual_evidence = body_external_urls(body)
                    route_id = hashlib.sha256(
                        str(page.url or "").split("?", 1)[0].encode("utf-8")
                    ).hexdigest()[:12]
                    for expected in contracts:
                        evidence = expected["evidence"]
                        if evidence and evidence == actual_evidence:
                            exact_evidence_pairs += 1
                        receipt = contract.compare_documents(expected["document"], actual_doc)
                        if not receipt["canonical_match"]:
                            continue
                        sync_hash = hashlib.sha256(expected["sync_id"].encode("utf-8")).hexdigest()[:12]
                        canonical_match_pairs.append((sync_hash, route_id))
                        if actual_title.strip() == expected["title"].strip():
                            title_canonical_match_pairs.append((sync_hash, route_id))
                except Exception:
                    continue
        finally:
            context.close()

    canonical_unique = sorted(set(canonical_match_pairs))
    title_canonical_unique = sorted(set(title_canonical_match_pairs))
    result = {
        "status": "current_draft_scan_complete",
        "read_only": True,
        "zero_gemini_calls": True,
        "draft_mutation": False,
        "public_release": False,
        "eligible_preparing_unpublished_rows": len(rows),
        "rows_with_current_contract": len(contracts),
        "history_candidate_count": len(history),
        "readable_editor_count": readable_editors,
        "convertible_editor_count": convertible_editors,
        "exact_evidence_pair_count": exact_evidence_pairs,
        "canonical_current_match_count": len(canonical_unique),
        "title_and_canonical_current_match_count": len(title_canonical_unique),
        "normalization_policy_version": contract.NORMALIZATION_POLICY_VERSION,
    }
    if len(title_canonical_unique) == 1:
        result["current_match_sync_hash"] = title_canonical_unique[0][0]
        result["current_match_route_hash"] = title_canonical_unique[0][1]
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
