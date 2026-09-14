#!/usr/bin/env python3
"""Run425 one-off repair for the already-approved RubyGems private note draft.

This operational repair does not regenerate the article. It derives the missing reader intro from
existing authoritative Content Intelligence properties, appends a new current-policy Ready block,
then updates only the body of the same existing private note draft. Header/title/route are guarded
byte-for-byte/identity-wise. Zero model calls; no public release action exists here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import requests

import publication_contract
import run425_required_intro_summary as contract

PAGE_ID = "3d9479ff-dca9-819a-814c-e4a0aeb3263f"
SYNC_ID = "3d9479ffdca9819a814ce4a0aeb3263f"
EXPECTED_SOURCE_TITLE = "OpenAI agents carried out an undisclosed attack on RubyGems"
EXPECTED_NOTE_TITLE = "AIが勝手に他社サーバーを突破した？OpenAIエージェントが起こしたRubyGems騒動から考える権限管理の境界線"
EXPECTED_DECISION = "WATCH"
CONFIRM = "RUN425_EXACT_RUBYGEMS_INTRO_RESTORE"
NOTION_VERSION = "2026-03-11"


class Run425RestoreError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    token = (os.getenv("NOTION_API_KEY") or os.getenv("NOTION_DECISION_INTELLIGENCE_API_KEY") or "").strip()
    if not token:
        raise Run425RestoreError("Notion token required")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Notion-Version": NOTION_VERSION}


def _plain(values: list[dict] | None) -> str:
    return "".join(
        str(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
        for item in (values or [])
    ).strip()


def _prop_text(prop: dict | None) -> str:
    prop = prop or {}
    if prop.get("title") is not None:
        return _plain(prop.get("title"))
    if prop.get("rich_text") is not None:
        return _plain(prop.get("rich_text"))
    return ""


def _select(prop: dict | None) -> str:
    return str(((prop or {}).get("select") or {}).get("name") or "").strip()


def _rich(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text[i:i + 1900]}} for i in range(0, len(text), 1900)]


def _children() -> list[dict]:
    out: list[dict] = []
    cursor = ""
    for _ in range(30):
        suffix = f"&start_cursor={cursor}" if cursor else ""
        response = requests.get(
            f"https://api.notion.com/v1/blocks/{PAGE_ID}/children?page_size=100{suffix}",
            headers=_headers(), timeout=30,
        )
        if response.status_code != 200:
            raise Run425RestoreError(f"Notion children read failed HTTP {response.status_code}")
        data = response.json()
        out.extend(data.get("results") or [])
        if not data.get("has_more"):
            return out
        cursor = str(data.get("next_cursor") or "")
        if not cursor:
            return out
    raise Run425RestoreError("Notion children pagination safety limit exceeded")


def _page_state() -> tuple[dict[str, Any], dict[str, Any]]:
    response = requests.get(f"https://api.notion.com/v1/pages/{PAGE_ID}", headers=_headers(), timeout=30)
    if response.status_code != 200:
        raise Run425RestoreError(f"Notion page read failed HTTP {response.status_code}")
    page = response.json()
    if str(page.get("id") or "").replace("-", "").lower() != SYNC_ID:
        raise Run425RestoreError("RubyGems page id drift")
    props = page.get("properties") or {}
    source_title = _prop_text(props.get("記事名"))
    note_title = _prop_text(props.get("note記事タイトル"))
    state = _select(props.get("記事状態"))
    decision = _select(props.get("判断"))
    if (source_title, note_title, state, decision) != (
        EXPECTED_SOURCE_TITLE, EXPECTED_NOTE_TITLE, "Ready", EXPECTED_DECISION
    ):
        raise Run425RestoreError(
            f"exact target mismatch source={source_title!r} note={note_title!r} state={state!r} decision={decision!r}"
        )
    return page, props


def _latest_manuscript() -> str:
    bodies: list[str] = []
    for block in _children():
        if block.get("type") != "code":
            continue
        body = _plain((block.get("code") or {}).get("rich_text"))
        if body.startswith(f"# {EXPECTED_NOTE_TITLE}"):
            bodies.append(body)
    if not bodies:
        raise Run425RestoreError("exact RubyGems manuscript code block not found")
    return bodies[-1]


def _conclusion_from_action(action: str) -> str:
    action = str(action or "").strip()
    if len(action) < 8:
        raise Run425RestoreError("authoritative next action missing")
    return "今すぐ全面停止・全面刷新する段階ではありません。まずは、" + action


def _intro_block(what: str, why: str, conclusion: str) -> str:
    return (
        "## どんな内容？\n\n"
        f"{what.strip()}\n\n"
        "**なぜ重要？**\n"
        f"{why.strip()}\n\n"
        "**結論は？**\n"
        f"{conclusion.strip()}"
    )


def restore_intro(manuscript: str, what: str, why: str, conclusion: str) -> str:
    text = str(manuscript or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    expected_h1 = f"# {EXPECTED_NOTE_TITLE}"
    if not text.startswith(expected_h1):
        raise Run425RestoreError("manuscript H1/title drift")
    if "**何が出た？**" in text:
        raise Run425RestoreError("legacy what label unexpectedly present")
    block = _intro_block(what, why, conclusion)
    if "## どんな内容？" in text:
        # Idempotency is allowed only when the exact expected intro is already present once.
        if text.count(block) != 1:
            raise Run425RestoreError("existing intro differs from authoritative Run425 block")
        repaired = text
    else:
        rest = text[len(expected_h1):].lstrip("\n")
        repaired = expected_h1 + "\n\n" + block + "\n\n" + rest
    summary = {"what": what, "why": why, "decision": conclusion}
    issues = contract.summary_contract_issues(summary, repaired)
    if issues:
        raise Run425RestoreError(f"restored intro contract failed: {issues}")
    return repaired


def _authoritative_repair() -> tuple[str, dict[str, str]]:
    _page, props = _page_state()
    what = _prop_text(props.get("これは何？"))
    why = _prop_text(props.get("なぜ重要？"))
    action = _prop_text(props.get("次にやること"))
    conclusion = _conclusion_from_action(action)
    if not what or not why:
        raise Run425RestoreError("authoritative summary properties missing")
    current = _latest_manuscript()
    repaired = restore_intro(current, what, why, conclusion)
    return repaired, {"what": what, "why": why, "decision": conclusion}


def repair_notion() -> dict[str, Any]:
    repaired, summary = _authoritative_repair()
    caption = publication_contract.current_ready_caption(repaired)
    if not publication_contract.is_current_ready_block(repaired, caption):
        raise Run425RestoreError("current Ready caption self-check failed")
    payload = {"children": [{
        "object": "block", "type": "code",
        "code": {"language": "markdown", "rich_text": _rich(repaired), "caption": _rich(caption)},
    }]}
    response = requests.patch(
        f"https://api.notion.com/v1/blocks/{PAGE_ID}/children",
        headers=_headers(), json=payload, timeout=30,
    )
    if response.status_code not in {200, 201}:
        raise Run425RestoreError(f"Notion Ready append failed HTTP {response.status_code}: {response.text[:300]}")
    if _latest_manuscript() != repaired:
        raise Run425RestoreError("Notion repaired manuscript readback mismatch")
    return {
        "status": "rubygems_intro_restored_in_notion",
        "page_id": PAGE_ID,
        "manuscript_chars": len(repaired),
        "summary_lengths": {k: len(v) for k, v in summary.items()},
        "policy_sha256": publication_contract.policy_sha256(),
        "zero_model_calls": True,
        "public_release": False,
    }


def _normalized(value: str) -> str:
    import run291_note_private_draft_audit as audit_base
    return audit_base._normalized_visible(str(value or ""))


def _visible_intro_ok(text: str, summary: dict[str, str]) -> bool:
    value = _normalized(text)
    markers = [
        _normalized("どんな内容？"), _normalized(summary["what"]),
        _normalized("なぜ重要？"), _normalized(summary["why"]),
        _normalized("結論は？"), _normalized(summary["decision"]),
    ]
    positions = [value.find(marker) for marker in markers]
    return all(pos >= 0 for pos in positions) and positions == sorted(positions) and _normalized("何が出た？") not in value


def refresh_existing_private_draft() -> dict[str, Any]:
    import note_draft_automation as note_base
    import note_eyecatch_persistence as persistence
    import run190_note_persistent_cloud as cloud
    import run298_genrec_inplace_refresh as route_helpers
    import run300_genrec_final_body_repair as body_helpers

    manuscript, summary = _authoritative_repair()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise Run425RestoreError("playwright missing") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            route, matched_rank, candidate_count = route_helpers._find_one_existing_route(context, page, EXPECTED_NOTE_TITLE)
            route_key = route_helpers._route_key(route)
            route_hash = hashlib.sha256(route_key.encode("utf-8")).hexdigest()[:12]
            page.goto(route, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1200)
            if note_base._looks_logged_out(page):
                if not cloud._seed_note_state(context, page):
                    raise Run425RestoreError("note auth inactive")
                page.goto(route, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1200)
            if route_helpers._route_key(str(page.url or "")) != route_key:
                raise Run425RestoreError("existing private draft route changed")
            if route_helpers._safe_title(page) != EXPECTED_NOTE_TITLE:
                raise Run425RestoreError("existing draft title mismatch")

            title_field = note_base._find_title(page)
            body, before_text = route_helpers._visible_body(page, title_field)
            header_metrics_before = persistence.collect_eyecatch_metrics(page, title_locator=title_field)
            if not persistence.eyecatch_persistence_confirmed(header_metrics_before):
                raise Run425RestoreError("header not persistent before body repair")
            header_hash_before, header_count_before = route_helpers._header_media_fingerprint(page, title_field)
            if not header_hash_before or header_count_before < 1:
                raise Run425RestoreError("header fingerprint missing before body repair")

            mutation_performed = not _visible_intro_ok(before_text, summary)
            clear_metrics: dict[str, Any] = {}
            paste_metrics: dict[str, Any] = {}
            if mutation_performed:
                clear_metrics = body_helpers._strict_clear_body(page, body)
                paste_metrics = body_helpers._paste_canonical_once(page, manuscript, EXPECTED_NOTE_TITLE)
                saved_url = note_base._save_draft_and_verify(
                    page, EXPECTED_NOTE_TITLE, manuscript, image_required=True
                )
                if route_helpers._route_key(saved_url) != route_key:
                    raise Run425RestoreError("same private draft route lost after save")
                page.wait_for_timeout(1000)

            title_field = note_base._find_title(page)
            _, final_text = route_helpers._visible_body(page, title_field)
            if not _visible_intro_ok(final_text, summary):
                raise Run425RestoreError("final private draft intro contract missing")
            if route_helpers._safe_title(page) != EXPECTED_NOTE_TITLE:
                raise Run425RestoreError("title changed during body-only repair")
            header_hash_after, header_count_after = route_helpers._header_media_fingerprint(page, title_field)
            if header_hash_after != header_hash_before or header_count_after != header_count_before:
                raise Run425RestoreError("eyecatch/header changed during body-only repair")

            return {
                "status": "existing_private_draft_intro_restored" if mutation_performed else "existing_private_draft_intro_already_current",
                "same_private_draft_route": True,
                "editor_route_hash": route_hash,
                "history_candidate_count": candidate_count,
                "matched_history_rank": matched_rank,
                "title_unchanged": True,
                "header_unchanged": True,
                "intro_contract_present": True,
                "duplicate_draft_created": False,
                "gemini_calls": 0,
                "public_release": False,
                **clear_metrics,
                **paste_metrics,
            }
        finally:
            context.close()


def main() -> int:
    if os.getenv("RUN425_CONFIRM", "").strip() != CONFIRM:
        raise Run425RestoreError("Run425 explicit exact-target confirmation missing")
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("repair-notion", "refresh-draft"))
    args = parser.parse_args()
    result = repair_notion() if args.mode == "repair-notion" else refresh_existing_private_draft()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
