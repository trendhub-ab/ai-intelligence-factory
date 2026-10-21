"""Read-only existing note draft identity diagnostics for one interrupted swap.

The source manuscript, unpublished queue, and saved draft ID are checked by
literal source ID and fixed SHA digests. Neither the old nor new private article
title nor the draft ID are committed as plaintext to the public repo.
This module NEVER clicks an edit/save/publish control.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re

import eyecatch_publication_contract as eyecatch
import note_ready_sync as sync
import run190_note_persistent_cloud as chrome
import ready_draft_regeneration as drafts

SOURCE_ID = "3f4479ffdca981ca9220cf15ac374db6"
DRAFT_ID_SHA256 = "26441aade090755c0c517cb80e16e33be30f32f99ef6cee398d2f17ee99975fb"
OLD_TITLE_SHA256 = "df24bc3d13cee8664191c0f1b71e573067fdbc95982f92315f19b3e2ca4e9b09"
NEW_TITLE_SHA256 = "09b3596e7da11afc7441c9aa6fb35a8dfcb20852cdb50f552da767bd167c109a"

class Refused(RuntimeError):
    pass

def require(ok: object, code: str) -> None:
    if not ok:
        raise Refused(code)

def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def exact_queue() -> dict:
    result = sync._query_db(sync.DEST_DATA_SOURCE_ID, sync.DEST_DATABASE_ID,
        payload={"filter":{"property":"同期ID","rich_text":{"equals":SOURCE_ID}}})
    rows = [p for p in result if sync._normalize_page_id(
        sync._text((p.get("properties") or {}).get("同期ID"))) == SOURCE_ID]
    require(len(rows) == 1, "queue_identity_ambiguous")
    props = rows[0].get("properties") or {}
    draft_id = sync._text(props.get("note下書きID"))
    require(digest(draft_id) == DRAFT_ID_SHA256, "draft_identity_changed")
    require(sync._select(props.get("品質状態")) == "Ready", "queue_quality_not_ready")
    require(sync._select(props.get("投稿状態")) == "保留", "queue_not_manual_hold")
    require(digest(sync._text(props.get("記事タイトル"))) == NEW_TITLE_SHA256, "queue_title_changed")
    require(not sync._url(props.get("note公開URL"))
            and not ((props.get("投稿日") or {}).get("date")), "published_evidence")
    response = sync._request("GET", "https://api.notion.com/v1/pages/" + SOURCE_ID)
    require(response.status_code == 200, "source_unreadable")
    state = sync._source_state(response.json())
    require(state is not None and state.get("sync_id") == SOURCE_ID,
            "source_not_ready_or_invalid")
    require(sync._select((response.json().get("properties") or {}).get("記事状態")) == "Ready",
            "source_status_not_ready")
    require(digest(str(state.get("title") or "")) == NEW_TITLE_SHA256,
            "source_title_changed")
    require(bool(sync._source_current_ready_manuscript(SOURCE_ID)),
            "source_manuscript_contract_invalid")
    require(eyecatch.current_asset_url(str(state.get("eyecatch_url") or ""), str(state["title"])),
            "source_cover_contract_invalid")
    return {"draft_id":draft_id, "source_id":SOURCE_ID}

def _list_labels(page) -> tuple[int, int]:
    page.goto("https://note.com/notes", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1500)
    require(page.url.split("?")[0].rstrip("/") == "https://note.com/notes",
            "official_article_list_not_open")
    require(not bool(page.locator("input[type=password]:visible").count()),
            "note_authentication_required")
    controls = page.get_by_role("button", name=re.compile(r"を編集$"))
    size = min(controls.count(), 250)
    old_count, new_count = 0, 0
    for i in range(size):
        button = controls.nth(i)
        try:
            label = str(button.evaluate(
                "(el) => (el.getAttribute('aria-label') || el.innerText || '').trim()"))
        except Exception:
            continue
        if not label.endswith("を編集"):
            continue
        h = digest(label[:-len("を編集")])
        old_count += int(h == OLD_TITLE_SHA256)
        new_count += int(h == NEW_TITLE_SHA256)
    return old_count, new_count

def browser_probe(draft_id: str) -> dict:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        context = chrome._launch_persistent_context(p)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            try:
                chrome._assert_expected_note_account(page)
            except Exception as exc:
                raise Refused("expected_note_account_not_proven") from exc
            try:
                old_count, new_count = _list_labels(page)
            except Exception as exc:
                raise Refused("official_list_unreadable") from exc
            # Reading the old title/list never clicks a button and never writes.
            from run291_note_private_draft_audit import _title_value
            route = "https://note.com/notes/" + draft_id + "/edit"
            try:
                page.goto(route, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1250)
                actual = str(page.url or "")
                resolved = drafts._draft_id_from_edit_url(actual)
                route_exact = resolved == draft_id
                title_hash = digest(_title_value(page)) if route_exact else ""
            except Exception:
                route_exact, title_hash = False, ""
            return {
                "status": "read_only_draft_identity_probe",
                "account_proven": True,
                "official_list_old_title_matches": old_count,
                "official_list_new_title_matches": new_count,
                "same_existing_edit_route": route_exact,
                "draft_editor_has_old_title": title_hash == OLD_TITLE_SHA256,
                "draft_editor_has_new_title": title_hash == NEW_TITLE_SHA256,
                "hold_preserved": True,
                "note_mutation": False,
                "notion_mutation": False,
                "new_draft_created": False,
                "public_release": False,
                "model_calls": 0,
            }
        finally:
            context.close()


def _held_destination(sync_id: str) -> dict:
    """In-memory adapter for a *manually held* row; never release the hold."""
    require(sync_id == SOURCE_ID, "wrong_target")
    q = exact_queue()
    resp = sync._request("GET", "https://api.notion.com/v1/pages/" + SOURCE_ID)
    require(resp.status_code == 200, "source_unreadable")
    state = sync._source_state(resp.json())
    require(state is not None and digest(str(state.get("title") or "")) == NEW_TITLE_SHA256,
            "source_title_changed")
    return {
        "sync_id": SOURCE_ID, "note_draft_id": q["draft_id"],
        "title": str(state["title"]), "posting_state": "保留",
        "quality_state": "Ready",
    }


def replace_held_draft_once() -> dict:
    """Guarded same-ID note-only replacement. Notion's manual hold never changes."""
    from unittest.mock import patch
    import run222_note_presentation_integrity as presentation
    import run291_note_private_draft_audit as private_audit
    import run295_note_private_draft_audit as modern_audit
    from operations import forget_only_private_swap_once as swap

    chrome.install()
    q = exact_queue()
    proof = browser_probe(q["draft_id"])
    require(proof["account_proven"], "note_account_not_proven")
    require(proof["same_existing_edit_route"], "same_draft_route_not_proven")
    require(proof["draft_editor_has_old_title"] or proof["draft_editor_has_new_title"],
            "draft_title_unrecognized")
    require(proof["official_list_old_title_matches"] + proof["official_list_new_title_matches"] >= 1,
            "official_list_has_no_matching_draft_title")

    # Source is already updated. Never regenerate or change the approved material.
    manuscript = sync._source_current_ready_manuscript(SOURCE_ID)
    require(bool(manuscript), "source_manuscript_not_current")
    approved = swap._verified_stage_manuscript(manuscript)
    destination = _held_destination(SOURCE_ID)
    title = destination["title"]
    presented = presentation.prepare_note_editor_manuscript(approved, title)
    require(len(presented) >= 200, "prepared_manuscript_too_short")

    route = "https://note.com/notes/" + q["draft_id"] + "/edit"
    # The production writer expects 投稿準備中. Supply the *verified held*
    # destination in process memory only; never write to or unhold Notion.
    with patch.object(drafts, "destination_preflight", side_effect=_held_destination):
        result = drafts.apply_current_article_to_existing_draft(SOURCE_ID, expected_route=route)
    require(result.get("status") == "existing_ready_draft_regenerated"
            and result.get("same_edit_route") is True
            and result.get("title_verified") is True
            and result.get("body_verified") is True
            and result.get("eyecatch_verified") is True
            and result.get("new_draft_created") is False
            and result.get("public_release") is False, "private_write_proof_failed")
    require(exact_queue()["draft_id"] == q["draft_id"], "post_save_draft_binding_changed")

    # Independent authenticated *reload* proof on exactly the same editor ID.
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        context = chrome._launch_persistent_context(p)
        try:
            page = context.new_page()
            chrome._assert_expected_note_account(page)
            page.goto(route, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1200)
            require(drafts._draft_id_from_edit_url(str(page.url or "")) == q["draft_id"],
                    "reload_draft_id_changed")
            metrics = modern_audit._audit_wrapper(private_audit._audit_current_page)(
                page, title, presented)
            require(metrics.get("title_match") is True
                    and metrics.get("eyecatch_present") is True
                    and metrics.get("prefix_match") is True
                    and metrics.get("suffix_match") is True, "independent_reload_failed")
        finally:
            context.close()
    require(exact_queue()["draft_id"] == q["draft_id"], "final_draft_binding_changed")
    return {"status": "EXACT_HELD_DRAFT_REPLACED", "existing_draft_preserved": True,
            "title_body_cover_verified": True, "independent_reload_passed": True,
            "hold_preserved": True, "notion_mutation": False, "new_draft_created": False,
            "public_release": False, "model_calls": 0}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--apply-held", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    try:
        q = exact_queue()
        if args.apply_held:
            require(args.confirm == "REPLACE_EXACT_HELD_DRAFT_ONCE", "approval_missing")
            result = replace_held_draft_once()
        elif args.prepare_only:
            result = {"status":"read_only_preflight_pass", "hold_preserved":True,
                      "note_mutation":False, "notion_mutation":False, "model_calls":0}
        else:
            result = browser_probe(q["draft_id"])
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except Refused as exc:
        print(json.dumps({"status":"blocked_read_only", "diagnostic_code":str(exc),
                          "hold_preserved":True, "note_mutation":False,
                          "notion_mutation":False, "model_calls":0}))
        raise SystemExit(2)
    except Exception:
        # Suppress URL/title/manuscript disclosures in public Actions traces.
        print(json.dumps({"status":"blocked_or_failed", "diagnostic_code":"private_runtime_failure",
                          "hold_preserved":True, "notion_mutation":False,
                          "model_calls":0}))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
