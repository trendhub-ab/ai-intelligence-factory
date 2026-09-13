#!/usr/bin/env python3
"""Run413 one-off operator-approved RubyGems Ready recaption.

No model calls. Reuses the exact persisted manuscript bytes already stored on the
single approved Content Intelligence page, appends a current-policy Ready code
block with a byte-matching caption, and refuses every other page/title/state.
"""
from __future__ import annotations

import os
import requests

import publication_contract

PAGE_ID = "3d9479ff-dca9-819a-814c-e4a0aeb3263f"
EXPECTED_TITLE = "OpenAI agents carried out an undisclosed attack on RubyGems"
CONFIRM = "RUN413_ONEOFF_RUBYGEMS_MANUAL_READY"
API_VERSION = "2026-03-11"


def headers():
    token = (os.getenv("NOTION_API_KEY") or os.getenv("NOTION_DECISION_INTELLIGENCE_API_KEY") or "").strip()
    if not token:
        raise RuntimeError("Notion token required")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Notion-Version": API_VERSION}


def plain(items):
    return "".join(str(x.get("plain_text") or ((x.get("text") or {}).get("content")) or "") for x in (items or []))


def get_children():
    out, cursor = [], ""
    while True:
        url = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        r = requests.get(url, headers=headers(), timeout=25)
        r.raise_for_status()
        data = r.json(); out.extend(data.get("results") or [])
        if not data.get("has_more"):
            return out
        cursor = str(data.get("next_cursor") or "")
        if not cursor:
            return out


def main():
    if os.getenv("RUN413_CONFIRM", "").strip() != CONFIRM:
        raise RuntimeError("Run413 explicit confirmation missing")
    page = requests.get(f"https://api.notion.com/v1/pages/{PAGE_ID}", headers=headers(), timeout=25)
    page.raise_for_status(); data = page.json(); props = data.get("properties") or {}
    title = plain((props.get("記事名") or {}).get("title"))
    status = str((((props.get("記事状態") or {}).get("select") or {}).get("name")) or "")
    if title != EXPECTED_TITLE or status != "Ready":
        raise RuntimeError(f"Run413 target mismatch title={title!r} status={status!r}")

    blocks = get_children()
    bodies = []
    for block in blocks:
        if block.get("type") != "code":
            continue
        code = block.get("code") or {}
        body = plain(code.get("rich_text"))
        if body and EXPECTED_TITLE in body:
            bodies.append(body)
    if not bodies:
        raise RuntimeError("Run413 exact persisted manuscript code block not found")
    manuscript = bodies[-1]
    caption = publication_contract.current_ready_caption(manuscript)
    if publication_contract.is_current_ready_block(manuscript, caption) is not True:
        raise RuntimeError("Run413 generated Ready caption did not self-verify")

    payload = {"children": [{"object": "block", "type": "code", "code": {"language": "markdown", "rich_text": [{"type": "text", "text": {"content": manuscript}}], "caption": [{"type": "text", "text": {"content": caption}}]}}]}
    r = requests.patch(f"https://api.notion.com/v1/blocks/{PAGE_ID}/children", headers=headers(), json=payload, timeout=25)
    r.raise_for_status()
    print({"run": 413, "page_id": PAGE_ID, "zero_model_calls": True, "manuscript_chars": len(manuscript), "policy_sha256": publication_contract.policy_sha256(), "ready_caption_verified": True})


if __name__ == "__main__":
    main()
