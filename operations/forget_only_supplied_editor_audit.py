"""Owner-supplied private note editor candidate: read-only authenticated identity proof.

The candidate URL is held ONLY in the private Notion revision stage.
Never print that URL, a draft ID, browser contents, cookies, or manuscript.
"""
from __future__ import annotations
import argparse
import json
import re
from urllib.parse import urlsplit

from operations import forget_only_draft_identity_diagnostic as audit
from operations import forget_only_private_swap_once as stage

STAGE_ID = "400479ffdca9817b9411e4289f77d810"
CANDIDATE_SHA256 = "c60844e9709b09fd9f139a42371576d37b9e8f5e7701496b55f51538b25e2332"
FIELD_PREFIX = "候補note編集URL:"

def candidate() -> str:
    blocks = stage.children(STAGE_ID)
    matches = []
    for block in blocks:
        data = block.get(block.get("type") or "", {})
        rich = data.get("rich_text") if isinstance(data, dict) else None
        text = stage.rich_text(rich)
        if text.strip().startswith(FIELD_PREFIX):
            matches.append(text.strip()[len(FIELD_PREFIX):].strip())
    audit.require(len(matches) == 1, "private_stage_candidate_not_unique")
    url = urlsplit(matches[0])
    audit.require(url.scheme == "https" and url.hostname == "editor.note.com"
                  and not url.username and not url.password and not url.port
                  and not url.query and not url.fragment, "candidate_url_not_canonical")
    match = re.fullmatch(r"/notes/(n[0-9A-Za-z_-]{5,80})/edit/?", url.path)
    audit.require(match is not None, "candidate_edit_path_invalid")
    draft_id = match.group(1)
    audit.require(audit.digest(draft_id) == CANDIDATE_SHA256,
                  "candidate_id_not_user_supplied")
    return draft_id

def check(*, browser: bool) -> dict:
    # The DB still holds the OLD draft identity, is unpublished and manually held.
    legacy = audit.exact_queue()
    new_id = candidate()
    audit.require(new_id != legacy["draft_id"], "candidate_equals_legacy")
    if not browser:
        return {"status": "candidate_preflight_pass", "source_ready": True,
                "queue_held": True, "candidate_sha_bound": True,
                "notion_mutation": False, "note_mutation": False, "model_calls": 0}
    audit.chrome.install()
    proof = audit.browser_probe(new_id)
    # Account + canonical existing editor + exact known article title.
    # Official list label count is supplemental because note may omit edit buttons.
    accepted = (proof["account_proven"] is True
                and proof["same_existing_edit_route"] is True
                and (proof["draft_editor_has_old_title"] is True
                     or proof["draft_editor_has_new_title"] is True))
    result = {"status": "supplied_draft_identity_verified" if accepted
              else "supplied_draft_identity_not_proven",
              "account_proven": bool(proof["account_proven"]),
              "same_existing_edit_route": bool(proof["same_existing_edit_route"]),
              "old_title_match": bool(proof["draft_editor_has_old_title"]),
              "new_title_match": bool(proof["draft_editor_has_new_title"]),
              "list_old_title_count": int(proof["official_list_old_title_matches"]),
              "list_new_title_count": int(proof["official_list_new_title_matches"]),
              "queue_held": True, "notion_mutation": False, "note_mutation": False,
              "model_calls": 0}
    print(json.dumps(result, sort_keys=True), flush=True)
    audit.require(accepted, "supplied_candidate_identity_unproven")
    return result

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    try:
        result = check(browser=not args.prepare_only)
        if args.prepare_only:
            print(json.dumps(result, sort_keys=True))
    except Exception:
        print(json.dumps({"status":"candidate_audit_refused",
                          "notion_mutation":False, "note_mutation":False,
                          "model_calls":0},sort_keys=True))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
