#!/usr/bin/env python3
"""Run288: zero-model rebase for the single GenRec Ready manuscript affected by Run287.

Run287 changed only one public metadata label for Hacker News sourced articles:
`公開・更新` -> `Hacker News投稿日`.  GenRec had already passed the full Production gate stack
under the immediately preceding policy, so regenerating the article would spend model quota
without adding information and would risk changing already-approved prose.

This migration is intentionally specimen-bound and fail-closed.  It will append a new
current-policy Ready code block only when all of the following are true:
- the source page is still Article Status=Ready;
- it is the exact Netflix GenRec Hacker News candidate;
- the old Ready block is from the exact pre-Run287 policy SHA;
- the old caption's manuscript SHA matches the old body bytes;
- there is no conflicting current-policy Ready block;
- exactly one expected metadata line changes and every other byte is preserved.

No Gemini/provider call, fresh acquisition, screening, eyecatch generation, VM, browser,
or public note publication exists in this module.
"""
from __future__ import annotations

import re
from typing import Any

import note_ready_sync as sync
import publication_contract as contract

TARGET_URL_SLUG = "netflixtechblog.com/genrec-towards-llm-native-recommendation-at-netflix-f20be6f643e3"
TARGET_SOURCE = "HackerNews"
TARGET_DISCOVERY_LABEL = "Hacker News"
PRE_RUN287_POLICY_SHA256 = "7417b204254b07547d319b145e3b6e9b2d0d5023f6e1b1d2fa7219b81b372e9d"
OLD_LINE = "- **公開・更新**: 2026-08-15"
NEW_LINE = "- **Hacker News投稿日**: 2026-08-15"
RICH_TEXT_LIMIT = 1900
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def _caption_fields(value: str) -> dict[str, str]:
    text = str(value or "").strip()
    if not text.startswith(contract.READY_CAPTION_PREFIX):
        return {}
    fields: dict[str, str] = {}
    for token in text[len(contract.READY_CAPTION_PREFIX):].split("|"):
        if "=" not in token:
            return {}
        key, val = token.split("=", 1)
        key, val = key.strip(), val.strip()
        if not key or key in fields:
            return {}
        fields[key] = val
    return fields


def _is_exact_pre_run287_block(body: str, caption: str) -> bool:
    fields = _caption_fields(caption)
    manuscript_sha = fields.get("manuscript_sha256", "")
    return bool(
        fields.get("contract") == contract.CONTRACT_ID
        and fields.get("policy_sha256") == PRE_RUN287_POLICY_SHA256
        and _SHA_RE.fullmatch(manuscript_sha)
        and manuscript_sha == contract.manuscript_sha256(body)
    )


def transform_genrec_manuscript(old_body: str) -> str:
    """Apply the one Run287 metadata correction, preserving every other byte."""
    body = str(old_body or "")
    if TARGET_URL_SLUG not in body:
        raise ValueError("Run288 target primary URL is absent from old manuscript")
    if "- **発見経路**: Hacker News" not in body:
        raise ValueError("Run288 target is not visibly attributed to Hacker News")
    if body.count(OLD_LINE) != 1:
        raise ValueError("Run288 requires exactly one legacy publication-date line")
    if NEW_LINE in body:
        raise ValueError("Run288 target already contains the new provenance label")

    new_body = body.replace(OLD_LINE, NEW_LINE, 1)
    if new_body.replace(NEW_LINE, OLD_LINE, 1) != body:
        raise RuntimeError("Run288 transform changed bytes outside the approved metadata line")

    old_lines = body.splitlines(keepends=True)
    new_lines = new_body.splitlines(keepends=True)
    if len(old_lines) != len(new_lines):
        raise RuntimeError("Run288 transform changed manuscript line count")
    changed = [(before, after) for before, after in zip(old_lines, new_lines) if before != after]
    if len(changed) != 1:
        raise RuntimeError("Run288 transform must change exactly one line")
    before, after = changed[0]
    if before.rstrip("\r\n") != OLD_LINE or after.rstrip("\r\n") != NEW_LINE:
        raise RuntimeError("Run288 changed an unexpected line")
    return new_body


def _current_code_block(body: str) -> dict[str, Any]:
    caption = contract.current_ready_caption(body)
    segments = [body[i:i + RICH_TEXT_LIMIT] for i in range(0, len(body), RICH_TEXT_LIMIT)]
    roundtrip = "".join(segments)
    if roundtrip != body:
        raise RuntimeError("Run288 Notion transport segmentation changed manuscript bytes")
    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": [
                {"type": "text", "text": {"content": segment}}
                for segment in segments
            ],
            "language": "markdown",
            "caption": [{"type": "text", "text": {"content": caption}}],
        },
    }


def _target_ready_page() -> tuple[dict[str, Any], dict[str, Any]]:
    pages = sync._query_db(
        sync.SOURCE_DATA_SOURCE_ID,
        sync.SOURCE_DATABASE_ID,
        payload={
            "filter": {
                "property": sync.SOURCE_ARTICLE_STATUS,
                "select": {"equals": sync.SOURCE_READY},
            }
        },
    )
    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for page in pages:
        state = sync._source_state(page)
        if not state:
            continue
        primary = str(state.get("primary_url") or "").lower()
        if state.get("source") == TARGET_SOURCE and TARGET_URL_SLUG in primary:
            matches.append((page, state))
    if len(matches) != 1:
        raise RuntimeError(f"Run288 expected exactly one live Ready GenRec page; found {len(matches)}")
    return matches[0]


def rebase_genrec_ready() -> dict[str, Any]:
    if not sync.NOTION_API_KEY:
        raise ValueError("NOTION_API_KEY is required")
    if not (sync.SOURCE_DATA_SOURCE_ID or sync.SOURCE_DATABASE_ID):
        raise ValueError("Content Intelligence source DB is not configured")

    page, state = _target_ready_page()
    page_id = str(page.get("id") or "").strip()
    if not page_id:
        raise RuntimeError("Run288 target page has no page id")
    if not state.get("eyecatch_url"):
        raise RuntimeError("Run288 refuses to rebase a Ready article without its eyecatch")

    blocks = sync._block_children(page_id)
    current: list[str] = []
    legacy_matches: list[str] = []
    for block in blocks:
        body = sync._code_body(block)
        caption = sync._code_caption(block)
        if not body or not caption:
            continue
        if contract.is_current_ready_block(body, caption):
            current.append(body)
        if _is_exact_pre_run287_block(body, caption):
            legacy_matches.append(body)

    if current:
        if len(current) != 1:
            raise RuntimeError("Run288 found multiple current-policy Ready blocks")
        expected = transform_genrec_manuscript(legacy_matches[-1]) if legacy_matches else ""
        if expected and current[-1] == expected:
            return {
                "status": "already_current",
                "page_id": page_id,
                "old_policy_sha256": PRE_RUN287_POLICY_SHA256,
                "new_policy_sha256": contract.policy_sha256(),
                "gemini_calls": 0,
            }
        raise RuntimeError("Run288 found a conflicting current-policy Ready block")

    if len(legacy_matches) != 1:
        raise RuntimeError(
            f"Run288 expected exactly one exact pre-Run287 Ready block; found {len(legacy_matches)}"
        )

    old_body = legacy_matches[0]
    new_body = transform_genrec_manuscript(old_body)
    if contract.manuscript_sha256(new_body) == contract.manuscript_sha256(old_body):
        raise RuntimeError("Run288 expected manuscript SHA to change after provenance correction")

    block = _current_code_block(new_body)
    new_caption = sync._code_caption(block)
    if not contract.is_current_ready_block(new_body, new_caption):
        raise RuntimeError("Run288 generated block does not satisfy current Publication Contract")

    response = sync._request(
        "PATCH",
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        json={"children": [block]},
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Run288 Notion append failed: HTTP {response.status_code} {response.text[:400]}"
        )

    verified = sync._source_current_ready_manuscript(page_id)
    if verified != new_body:
        raise RuntimeError("Run288 post-write verification did not read back the exact new manuscript")
    if OLD_LINE in verified or NEW_LINE not in verified:
        raise RuntimeError("Run288 post-write provenance verification failed")

    return {
        "status": "rebased",
        "page_id": page_id,
        "title": state.get("title") or "",
        "source": state.get("source") or "",
        "primary_url": state.get("primary_url") or "",
        "old_policy_sha256": PRE_RUN287_POLICY_SHA256,
        "new_policy_sha256": contract.policy_sha256(),
        "old_manuscript_sha256": contract.manuscript_sha256(old_body),
        "new_manuscript_sha256": contract.manuscript_sha256(new_body),
        "changed_lines": 1,
        "gemini_calls": 0,
        "private_draft": False,
        "public_release": False,
    }


def main() -> int:
    result = rebase_genrec_ready()
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
