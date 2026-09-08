#!/usr/bin/env python3
"""Run289: repair the single GenRec Note Ready queue row auto-revoked by Run287.

Root cause:
`note_ready_sync` correctly invalidated stale publication-contract material, but its
revocation path also wrote the human workflow field 投稿状態=取下げ. Run288 later
restored the exact GenRec manuscript to current-policy Ready and `note_ready_sync`
restored 品質状態=Ready, while deliberately preserving human workflow fields. The
system-induced 取下げ therefore survived and made the zero-VM draft preflight see no
投稿待ち candidate.

This migration is deliberately one-shot and specimen-bound. It restores only the exact
GenRec row whose automated revocation is independently established by the Run287/288
GitHub audit trail. It is not a generic rule for changing human queue state. The broader
revocation-state design is intentionally left outside this migration so the immediate
repair cannot silently change unrelated rows.

No Gemini/provider, browser, VM, note mutation, or public release exists here.
"""
from __future__ import annotations

from typing import Any

import note_ready_sync as sync
import publication_contract as contract

TARGET_SYNC_ID = "3bd479ffdca9817f926aeaffbb779c4b"
TARGET_URL_SLUG = "netflixtechblog.com/genrec-towards-llm-native-recommendation-at-netflix-f20be6f643e3"
TARGET_SOURCE = "HackerNews"
TARGET_POLICY_SHA256 = "b1b4d1e9d5e52788dc16396480ca0b7097701dc9354d91fd299394296fd1cd45"
EXPECTED_OLD_POSTING_STATUS = "取下げ"
EXPECTED_QUALITY_STATUS = "Ready"
RESTORED_POSTING_STATUS = "投稿待ち"
EXPECTED_PROVENANCE_LINE = "- **Hacker News投稿日**: 2026-08-15"
FORBIDDEN_OLD_PROVENANCE_LINE = "- **公開・更新**: 2026-08-15"


def _date_value(prop: dict[str, Any] | None) -> str:
    return str((((prop or {}).get("date") or {}).get("start")) or "").strip()


def _exact_destination_page() -> dict[str, Any]:
    rows = sync._query_db(
        sync.DEST_DATA_SOURCE_ID,
        sync.DEST_DATABASE_ID,
        payload={
            "filter": {
                "property": "同期ID",
                "rich_text": {"equals": TARGET_SYNC_ID},
            }
        },
    )
    exact = [
        row for row in rows
        if sync._normalize_page_id(sync._text((row.get("properties") or {}).get("同期ID"))) == TARGET_SYNC_ID
    ]
    if len(exact) != 1:
        raise RuntimeError(f"Run289 expected exactly one GenRec destination row; found {len(exact)}")
    return exact[0]


def _source_page() -> tuple[dict[str, Any], dict[str, Any], str]:
    response = sync._request("GET", f"https://api.notion.com/v1/pages/{TARGET_SYNC_ID}")
    if response.status_code != 200:
        raise RuntimeError(f"Run289 source page read failed: HTTP {response.status_code}")
    page = response.json()
    if not isinstance(page, dict):
        raise RuntimeError("Run289 source page response is invalid")
    state = sync._source_state(page)
    if not state:
        raise RuntimeError("Run289 source is no longer a live Ready row")
    if state.get("sync_id") != TARGET_SYNC_ID:
        raise RuntimeError("Run289 source sync_id mismatch")
    if state.get("source") != TARGET_SOURCE:
        raise RuntimeError("Run289 source family mismatch")
    if TARGET_URL_SLUG not in str(state.get("primary_url") or "").lower():
        raise RuntimeError("Run289 primary URL mismatch")
    if not state.get("eyecatch_url"):
        raise RuntimeError("Run289 source eyecatch is missing")
    manuscript = sync._source_current_ready_manuscript(TARGET_SYNC_ID)
    if not manuscript:
        raise RuntimeError("Run289 current-policy Ready manuscript is missing")
    if EXPECTED_PROVENANCE_LINE not in manuscript or FORBIDDEN_OLD_PROVENANCE_LINE in manuscript:
        raise RuntimeError("Run289 manuscript does not contain the exact Run287 provenance correction")
    return page, state, manuscript


def reactivate_genrec_queue() -> dict[str, Any]:
    if not sync.NOTION_API_KEY:
        raise ValueError("NOTION_API_KEY is required")
    if not (sync.SOURCE_DATA_SOURCE_ID or sync.SOURCE_DATABASE_ID):
        raise ValueError("Content Intelligence source DB is not configured")
    if not (sync.DEST_DATA_SOURCE_ID or sync.DEST_DATABASE_ID):
        raise ValueError("note Ready destination DB is not configured")

    policy = contract.policy_sha256()
    if policy != TARGET_POLICY_SHA256:
        raise RuntimeError(
            f"Run289 is bound to Run287 policy {TARGET_POLICY_SHA256}; current policy is {policy}"
        )

    _, source_state, manuscript = _source_page()
    destination = _exact_destination_page()
    props = destination.get("properties") or {}
    current = sync._destination_state(destination)
    page_id = str(destination.get("id") or "").strip()
    if not page_id:
        raise RuntimeError("Run289 destination page id is missing")
    if current.get("sync_id") != TARGET_SYNC_ID:
        raise RuntimeError("Run289 destination sync_id mismatch")
    if current.get("quality_status") != EXPECTED_QUALITY_STATUS:
        raise RuntimeError(
            f"Run289 requires quality={EXPECTED_QUALITY_STATUS}; found {current.get('quality_status')!r}"
        )
    if current.get("posting_status") == RESTORED_POSTING_STATUS:
        return {
            "status": "already_reactivated",
            "sync_id": TARGET_SYNC_ID,
            "destination_page_id": page_id,
            "publication_policy_sha256": policy,
            "manuscript_sha256": contract.manuscript_sha256(manuscript),
            "gemini_calls": 0,
            "browser_calls": 0,
            "public_release": False,
        }
    if current.get("posting_status") != EXPECTED_OLD_POSTING_STATUS:
        raise RuntimeError(
            f"Run289 refuses unexpected posting status {current.get('posting_status')!r}"
        )
    if sync._url(props.get("note公開URL")):
        raise RuntimeError("Run289 refuses a row that already has a public note URL")
    if _date_value(props.get("投稿日")):
        raise RuntimeError("Run289 refuses a row that already has a posted date")
    if sync._text(props.get("記事タイトル")) != str(source_state.get("title") or ""):
        raise RuntimeError("Run289 destination/source title mismatch")

    response = sync._request(
        "PATCH",
        f"https://api.notion.com/v1/pages/{page_id}",
        json={"properties": {"投稿状態": sync._sel(RESTORED_POSTING_STATUS)}},
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Run289 destination reactivation failed: HTTP {response.status_code} {response.text[:400]}"
        )

    verify = sync._request("GET", f"https://api.notion.com/v1/pages/{page_id}")
    if verify.status_code != 200:
        raise RuntimeError(f"Run289 destination readback failed: HTTP {verify.status_code}")
    verified_page = verify.json()
    if not isinstance(verified_page, dict):
        raise RuntimeError("Run289 destination readback is invalid")
    verified = sync._destination_state(verified_page)
    verified_props = verified_page.get("properties") or {}
    if verified.get("sync_id") != TARGET_SYNC_ID:
        raise RuntimeError("Run289 readback sync_id mismatch")
    if verified.get("quality_status") != EXPECTED_QUALITY_STATUS:
        raise RuntimeError("Run289 readback quality changed unexpectedly")
    if verified.get("posting_status") != RESTORED_POSTING_STATUS:
        raise RuntimeError("Run289 readback posting status was not restored")
    if sync._url(verified_props.get("note公開URL")) or _date_value(verified_props.get("投稿日")):
        raise RuntimeError("Run289 readback unexpectedly contains publication state")

    return {
        "status": "reactivated",
        "sync_id": TARGET_SYNC_ID,
        "destination_page_id": page_id,
        "title": source_state.get("title") or "",
        "publication_policy_sha256": policy,
        "manuscript_sha256": contract.manuscript_sha256(manuscript),
        "posting_status_before": EXPECTED_OLD_POSTING_STATUS,
        "posting_status_after": RESTORED_POSTING_STATUS,
        "gemini_calls": 0,
        "browser_calls": 0,
        "private_draft": False,
        "public_release": False,
    }


def main() -> int:
    print(reactivate_genrec_queue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
