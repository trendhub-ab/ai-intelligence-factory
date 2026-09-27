#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from typing import Any
from playwright.sync_api import sync_playwright

import note_draft_automation as note_base
import run190_note_existing_draft_repair as run190
import run417_note_draft_text_persistence as run417
import run103_note_ready_rescue as audit_base
import run_vtcode_existing_draft_repair as repair

def update_body_only() -> dict[str, Any]:
    manuscript = repair.load_manuscript()
    gates = repair.validate_repaired_manuscript(manuscript)
    if gates.get("publication_state") != "PASS" or not gates.get("fact_ok") or not gates.get("editorial_ok"):
        raise repair.VTCodeRepairError("VT Code manuscript no longer passes current gates")
    dest = repair.destination_preflight()
    expected_route = repair.draft_preflight()
    body_manuscript = note_base._body_manuscript_for_note(repair.NEW_TITLE, manuscript)

    run190.install()
    run417.install(note_base)
    profile = run190._profile_dir()
    with sync_playwright() as playwright:
        context = run190._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            url = repair._open_exact_draft(page, profile, expected_route=expected_route)
            title_field = note_base._set_title(page, repair.NEW_TITLE)
            body = note_base._find_body(page, title_field)
            note_base._paste_manuscript(page, body, body_manuscript)
            body = note_base._find_body(page, title_field)
            note_base._verify_body_content(body, body_manuscript)
            saved = note_base._save_draft_and_verify(
                page, repair.NEW_TITLE, body_manuscript, image_required=False
            )
            if not repair._same_edit_route(url, saved):
                raise repair.VTCodeRepairError("Body-only save escaped the existing VT Code draft")
            title_match = audit_base._title_value(page) == repair.NEW_TITLE
            if not title_match:
                raise repair.VTCodeRepairError("VT Code title did not persist")
            return {
                "status": "existing_draft_body_updated",
                "same_edit_route": True,
                "title_match": True,
                "body_verified": True,
                "eyecatch_skipped": True,
                "zero_gemini_calls": True,
                "new_draft_created": False,
                "public_release": False,
                "publication_gates_passed": True,
                "posting_state_preserved": dest.get("posting_state"),
                "editor_route_hash": hashlib.sha256(repair._route_key(url).encode()).hexdigest()[:12],
            }
        finally:
            context.close()

if __name__ == "__main__":
    print(json.dumps(update_body_only(), ensure_ascii=False, sort_keys=True))
