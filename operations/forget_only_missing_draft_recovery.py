#!/usr/bin/env python3
"""One-time replacement of a *missing* Forget-Only private draft.

Never reuse or overwrite another note draft. The old binding stays manually 保留
until a NEW browser-saved private draft passes an independent post-save audit.
A local, exclusive durable receipt freezes retry authority at the first new ID,
so a failure after save cannot accidentally create duplicates.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from operations import forget_only_draft_identity_diagnostic as identity
from operations import forget_only_private_swap_once as approved
import eyecatch_publication_contract as eyecatch
import note_draft_automation as note
import note_ready_sync as sync
import ready_draft_regeneration as old
import run190_note_persistent_cloud as chrome
import run222_note_presentation_integrity as presentation

SOURCE_ID = identity.SOURCE_ID
QUEUE_ID = "3f4479ffdca9815489c0e6c977065699"
CONFIRM = "RECREATE_MISSING_FORGET_ONLY_PRIVATE_ONCE"
RECEIPT = Path.home() / ".aiif-note" / "forget-only-missing-draft-once.receipt.json"


def require(condition: object, code: str) -> None:
    identity.require(condition, code)


def prepared() -> dict:
    """Strict read-only source and old queue binding proof; never unhold first."""
    row = identity.exact_queue()
    article, title = approved.stage_article()
    require(identity.digest(title) == identity.NEW_TITLE_SHA256, "title_drift")
    saved_article = sync._source_current_ready_manuscript(SOURCE_ID)
    require(bool(saved_article), "source_not_current")
    require(approved._verified_stage_manuscript(saved_article) == article,
            "source_stage_manuscript_drift")
    src = approved.notion("GET", "pages/" + SOURCE_ID)
    state = sync._source_state(src)
    require(state is not None and state.get("sync_id") == SOURCE_ID,
            "source_identity_not_ready")
    require(state.get("title") == title, "source_title_drift")
    require(eyecatch.current_asset_url(str(state.get("eyecatch_url") or ""), title),
            "cover_manifest_not_current")
    rows = sync._query_db(sync.DEST_DATA_SOURCE_ID, sync.DEST_DATABASE_ID,
             payload={"filter":{"property":"同期ID","rich_text":{"equals":SOURCE_ID}}})
    require(len(rows) == 1 and rows[0].get("id") == QUEUE_ID, "queue_id_drift")
    props = rows[0].get("properties") or {}
    require(sync._select(props.get("投稿状態")) == "保留"
            and not sync._url(props.get("note公開URL"))
            and not ((props.get("投稿日") or {}).get("date")),
            "queue_no_longer_held")
    return {"title":title, "article":article, "old_draft_id":row["draft_id"],
            "cover":str(state["eyecatch_url"])}


def _require_no_existing_browser_draft(legacy: str) -> None:
    from playwright.sync_api import sync_playwright
    chrome.install()
    with sync_playwright() as p:
        context = chrome._launch_persistent_context(p)
        try:
            page = context.new_page()
            page.set_default_timeout(30000)
            chrome._assert_expected_note_account(page)
            old_count, new_count = identity._list_labels(page)
            require(old_count == 0 and new_count == 0,
                    "existing_matching_title_in_official_article_list")
            # Refuse if old ID still resolves to any authenticated editor.
            try:
                found = old._open_exact_existing_draft(page, chrome._profile_dir(), legacy)
            except old.ReadyDraftRegenerationError:
                found = ""
            require(not found, "old_id_still_has_editable_draft")
        finally:
            context.close()


def _queue_readback(expected_draft_id: str, *, old_id: str) -> None:
    rows = sync._query_db(sync.DEST_DATA_SOURCE_ID, sync.DEST_DATABASE_ID,
            payload={"filter":{"property":"同期ID","rich_text":{"equals":SOURCE_ID}}})
    require(len(rows) == 1 and rows[0].get("id") == QUEUE_ID, "queue_drift")
    props = rows[0].get("properties") or {}
    require(sync._text(props.get("note下書きID")) == expected_draft_id,
            "queue_draft_binding_incorrect")
    require(sync._select(props.get("投稿状態")) == "保留", "human_hold_was_lost")
    require(not sync._url(props.get("note公開URL"))
            and not ((props.get("投稿日") or {}).get("date")),
            "unexpected_publication_evidence")
    require(expected_draft_id != old_id, "old_id_reused")


def _post_save_browser_audit(new_id: str, title: str, manuscript: str) -> None:
    from playwright.sync_api import sync_playwright
    import run291_note_private_draft_audit as article_audit
    with sync_playwright() as p:
        context = chrome._launch_persistent_context(p)
        try:
            page = context.new_page()
            page.set_default_timeout(30000)
            chrome._assert_expected_note_account(page)
            url = old._open_exact_existing_draft(page, chrome._profile_dir(), new_id)
            require(old._draft_id_from_edit_url(url) == new_id,
                    "new_saved_route_not_exact")
            metrics = article_audit._audit_current_page(page, title, manuscript)
            require(metrics.get("title_match") is True
                    and metrics.get("eyecatch_present") is True
                    and metrics.get("prefix_match") is True
                    and metrics.get("suffix_match") is True,
                    "saved_private_article_readback_failed")
        finally:
            context.close()


def _commit_new_id(new_id: str, legacy: str) -> None:
    # Re-read before write. Hold remains and the stable old identity is pinned.
    still = prepared()
    require(still["old_draft_id"] == legacy, "queue_changed_before_commit")
    response = sync._request(
        "PATCH", "https://api.notion.com/v1/pages/" + QUEUE_ID,
        json={"properties":{
            "note下書きID":{"rich_text":[{"type":"text","text":{"content":new_id}}]}
        }},
    )
    require(response.status_code == 200, "note_queue_binding_write_refused")
    _queue_readback(new_id, old_id=legacy)


def _record_new_id_once(url: str, old_id: str) -> None:
    from urllib.parse import urlparse
    result = urlparse(url)
    require(result.scheme == "https"
            and result.hostname in {"note.com", "editor.note.com"}
            and not result.query and not result.fragment, "new_draft_url_invalid")
    new_id = old._draft_id_from_edit_url(url)
    require(bool(new_id) and new_id != old_id, "new_draft_id_invalid")
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation means an interrupted previous attempt cannot be retried
    # into a second new draft. Never delete/overwrite this receipt automatically.
    fd = os.open(str(RECEIPT), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"source_id":SOURCE_ID,"new_draft_id":new_id,
                   "state":"candidate_created_review_before_queue_update"},handle)


def apply() -> dict:
    require(os.environ.get("NOTE_STORAGE_STATE_B64"), "note_auth_state_missing")
    require(not RECEIPT.exists(), "prior_creation_receipt_exists_no_retry")
    target = prepared()
    legacy = target["old_draft_id"]
    _require_no_existing_browser_draft(legacy)
    require(not RECEIPT.exists(), "creation_already_recorded")
    public_title = target["title"]
    body = presentation.prepare_note_editor_manuscript(target["article"], public_title)
    require(len(body) >= 200, "approved_presentation_too_short")
    image_path = note._download_eyecatch(target["cover"], SOURCE_ID, public_title)
    chrome.install()
    # This is a new draft, NOT an attempt to edit a different note article.
    draft_url = chrome._create_browser_draft(
        public_title, body, image_path, Path("/dev/null"),
        on_stable_draft_url=lambda url: _record_new_id_once(url, legacy),
    )
    draft_id = old._draft_id_from_edit_url(draft_url)
    require(bool(draft_id) and RECEIPT.is_file(), "stable_draft_creation_unverified")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(receipt.get("new_draft_id") == draft_id, "receipt_draft_id_drift")
    _post_save_browser_audit(draft_id, public_title,
                             note._body_manuscript_for_note(public_title, body))
    _commit_new_id(draft_id, legacy)
    receipt["state"] = "verified_and_bound_hold_preserved"
    RECEIPT.write_text(json.dumps(receipt,ensure_ascii=False), encoding="utf-8")
    RECEIPT.chmod(0o600)
    return {"status":"NEW_PRIVATE_DRAFT_RECREATED_AND_VERIFIED",
            "same_queue_row":True,"replaced_missing_legacy_binding":True,
            "note_body_title_cover_verified":True,"posting_hold_preserved":True,
            "new_draft_created":True,"public_release":False,"gemini_calls":0}


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    p.add_argument("--confirm",default="")
    args=p.parse_args()
    require(not args.apply or args.confirm == CONFIRM, "one_shot_approval_missing")
    if not args.apply:
        prepared()
        output={"status":"READ_ONLY_RECOVERY_PREFLIGHT_PASSED",
                "queue_held":True,"note_write":False,"notion_write":False}
    else:
        output=apply()
    print(json.dumps(output,sort_keys=True,ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Intentionally no source titles, URLs, cookies, manuscript or new ID.
        kind = exc.args[0] if isinstance(exc, identity.Refused) else "private_runtime_error"
        print(json.dumps({"status":"RECOVERY_STOPPED_MANUAL_REVIEW",
                          "diagnostic_code":str(kind),
                          "auto_retry":False,"public_release":False}))
        raise SystemExit(2)
