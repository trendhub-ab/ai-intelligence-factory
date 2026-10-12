#!/usr/bin/env python3
"""Read-only discriminator for known ambiguous manuscript pages.

Only GETs page/block data from Notion. Never persists manuscript bodies; output is
limited to hashes, captions parsed into contract metadata, timestamps, and H1s.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = os.environ.get("NOTION_API_VERSION", "2026-03-11")
REVIEW_CAPTION = "AIIF_MANUSCRIPT:NEEDS_EDITORIAL_REVIEW"
READY_RE = re.compile(r"^AIIF_MANUSCRIPT:READY(?:\|policy=([0-9a-f]{64})\|body=([0-9a-f]{64}))?$")


def _headers() -> dict[str, str]:
    token = os.environ.get("NOTION_API_KEY", "").strip()
    if not token:
        raise RuntimeError("NOTION_API_KEY is required")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Notion-Version": NOTION_VERSION}


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers=_headers(), method="GET")
    last = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code == 429 or 500 <= exc.code < 600:
                time.sleep(min(2 ** attempt, 8)); continue
            raise
        except urllib.error.URLError as exc:
            last = exc; time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"GET failed after retries: {last}")


def _plain(values) -> str:
    return "".join(str(x.get("plain_text") or ((x.get("text") or {}).get("content")) or "") for x in (values or []))


def _prop_text(prop: dict | None) -> str:
    prop = prop or {}
    return _plain(prop.get("title") if prop.get("title") is not None else prop.get("rich_text"))


def _prop_select(prop: dict | None) -> str:
    return str(((prop or {}).get("select") or {}).get("name") or "")


def _children(page_id: str) -> list[dict]:
    rows, cursor = [], ""
    while True:
        query = {"page_size": "100"}
        if cursor: query["start_cursor"] = cursor
        time.sleep(0.38)
        data = _get(f"{API_BASE}/blocks/{page_id}/children?{urllib.parse.urlencode(query)}")
        rows.extend(data.get("results") or [])
        if not data.get("has_more"): return rows
        cursor = str(data.get("next_cursor") or "")
        if not cursor: raise RuntimeError(f"missing cursor for {page_id}")


def _body(block: dict) -> str:
    if block.get("type") != "code": return ""
    code = block.get("code") or {}
    if str(code.get("language") or "").lower() != "markdown": return ""
    return _plain(code.get("rich_text"))


def _caption(block: dict) -> str:
    return _plain(((block.get("code") or {}).get("caption"))) if block.get("type") == "code" else ""


def _h1(body: str) -> str:
    m = re.search(r"(?m)^#\s+(.+?)\s*$", body or "")
    return m.group(1).strip() if m else ""


def _contract(caption: str, body: str, main_policy_sha: str) -> dict:
    body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if caption == REVIEW_CAPTION:
        return {"kind": "review", "body_hash_valid": False, "main_policy_match": False}
    if not caption:
        return {"kind": "captionless", "body_hash_valid": False, "main_policy_match": False}
    m = READY_RE.match(caption)
    if not m:
        return {"kind": "other", "body_hash_valid": False, "main_policy_match": False}
    policy_sha, caption_body_sha = m.groups()
    if not policy_sha:
        return {"kind": "legacy_ready", "body_hash_valid": False, "main_policy_match": False}
    return {
        "kind": "addressed_ready",
        "policy_sha16": policy_sha[:16],
        "caption_body_sha16": caption_body_sha[:16],
        "body_hash_valid": caption_body_sha == body_sha,
        "main_policy_match": policy_sha == main_policy_sha,
    }


def main() -> int:
    target_ids = [x.strip().replace("-", "") for x in os.environ.get("AIIF_TARGET_PAGE_IDS", "").split(",") if x.strip()]
    main_policy_sha = os.environ.get("AIIF_MAIN_POLICY_SHA", "").strip()
    if not target_ids or not re.fullmatch(r"[0-9a-f]{64}", main_policy_sha):
        raise RuntimeError("AIIF_TARGET_PAGE_IDS and 64-char AIIF_MAIN_POLICY_SHA are required")
    pages = []
    for compact in target_ids:
        page = _get(f"{API_BASE}/pages/{compact}")
        props = page.get("properties") or {}
        expected_title = _prop_text(props.get("note記事タイトル"))
        blocks = []
        for block in _children(str(page.get("id") or compact)):
            body = _body(block)
            if not body: continue
            c = _contract(_caption(block), body, main_policy_sha)
            blocks.append({
                "block_id": str(block.get("id") or ""),
                "created_time": str(block.get("created_time") or ""),
                "last_edited_time": str(block.get("last_edited_time") or ""),
                "h1": _h1(body),
                "title_match": bool(expected_title and _h1(body) == expected_title),
                "body_sha16": hashlib.sha256(body.encode("utf-8")).hexdigest()[:16],
                **c,
            })
        exact_main = [b for b in blocks if b.get("kind") == "addressed_ready" and b.get("body_hash_valid") and b.get("main_policy_match")]
        exact_main_title = [b for b in exact_main if b.get("title_match")]
        unique_bodies = sorted({b["body_sha16"] for b in exact_main_title})
        if len(exact_main_title) == 1:
            classification = "unique_main_contract"
            canonical_block_id = exact_main_title[0]["block_id"]
        elif len(exact_main_title) > 1 and len(unique_bodies) == 1:
            classification = "duplicate_same_main_contract_body"
            canonical_block_id = sorted(exact_main_title, key=lambda b: (b["created_time"], b["block_id"]))[0]["block_id"]
        else:
            classification = "unresolved"
            canonical_block_id = ""
        pages.append({
            "page_id": compact,
            "article_status": _prop_select(props.get("記事状態")),
            "expected_title": expected_title,
            "classification": classification,
            "canonical_block_id": canonical_block_id,
            "main_contract_title_candidate_count": len(exact_main_title),
            "main_contract_title_unique_body_count": len(unique_bodies),
            "blocks": blocks,
        })
    report = {
        "read_only": True,
        "main_policy_sha16": main_policy_sha[:16],
        "target_count": len(target_ids),
        "resolved_count": sum(p["classification"] != "unresolved" for p in pages),
        "unresolved_count": sum(p["classification"] == "unresolved" for p in pages),
        "pages": pages,
    }
    out = Path("artifacts/notion_contract_targets.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("target_count", "resolved_count", "unresolved_count", "main_policy_sha16")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
