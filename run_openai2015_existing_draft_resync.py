#!/usr/bin/env python3
"""One-off exact resync of the existing OpenAI (2015) private note draft.

Safety contract:
- exact Content Intelligence page and exact note queue row only;
- reuse the already operator-edited manuscript bytes; no semantic rewrite;
- zero Gemini/model calls;
- append a byte-valid current publication-contract Ready block;
- preserve the existing note edit route and existing eyecatch;
- never navigate to /new and never perform public release.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import note_draft_automation as note_base
import note_ready_sync as ready_sync
import publication_contract
import run190_note_persistent_cloud as run190
import run291_note_private_draft_audit as audit_base
import run417_note_body_verification as run417
from notion_payloads import build_notion_manuscript_children, safe_chunk_text
from run_sgps_existing_draft_repair import _route_key, _same_edit_route

SYNC_ID = "3e8479ffdca9812e9661f337a84b1df4"
DESTINATION_PAGE_ID = "3e8479ff-dca9-8175-9904-d7098f2682c5"
ARTICLE_NAME = "OpenAI (2015)"
TITLE = "AIの巨人はどこから生まれたのか。2015年、非営利スタートアップ「OpenAI」が掲げた理想と出発点。"
PRIMARY_URL = "https://openai.com/index/introducing-openai/"
CONFIRM_TOKEN = "RESYNC_OPENAI2015_EXISTING_DRAFT"

BAD_PHRASES = (
    "今は導入を急がず",
    "実務への直接的な導入を急ぐ段階ではありません",
    "AI導入の意思決定者",
)
REQUIRED_PHRASES = (
    "後年のOpenAI公式発表と比較するための「原点」",
    "2015年のOpenAIは、まず「非営利」から始まった",
    "「10億ドル」は、すぐ使う10億ドルではなかった",
)


class OpenAI2015ResyncError(RuntimeError):
    pass


def _source_page() -> dict:
    response = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{SYNC_ID}")
    if response.status_code != 200:
        raise OpenAI2015ResyncError(
            f"Content Intelligence source fetch failed: HTTP {response.status_code}"
        )
    page = response.json()
    props = page.get("properties") or {}
    if ready_sync._text(props.get("記事名")) != ARTICLE_NAME:
        raise OpenAI2015ResyncError("Exact article name changed")
    if ready_sync._select(props.get("記事状態")) != "Ready":
        raise OpenAI2015ResyncError("Exact source is no longer 記事状態=Ready")
    if ready_sync._text(props.get("note記事タイトル")) != TITLE:
        raise OpenAI2015ResyncError("Exact public title changed")
    if ready_sync._url(props.get("元情報URL")).casefold() != PRIMARY_URL.casefold():
        raise OpenAI2015ResyncError("Exact primary source changed")
    return page


def _operator_manuscript() -> str:
    bodies: list[str] = []
    for block in note_base._fetch_block_children(SYNC_ID):
        parsed = note_base._code_block_text(block)
        if parsed is None:
            continue
        body, _caption = parsed
        manuscript = str(body or "").strip()
        if manuscript.startswith(f"# {TITLE}\n"):
            bodies.append(manuscript)
    if not bodies:
        raise OpenAI2015ResyncError("Operator-edited OpenAI 2015 manuscript was not found")
    manuscript = bodies[-1]
    if len(manuscript) < 1800:
        raise OpenAI2015ResyncError("Operator-edited manuscript is unexpectedly short")
    for phrase in BAD_PHRASES:
        if phrase in manuscript:
            raise OpenAI2015ResyncError(f"Old adoption framing survived: {phrase}")
    for phrase in REQUIRED_PHRASES:
        if phrase not in manuscript:
            raise OpenAI2015ResyncError(f"Expected revised passage is missing: {phrase}")
    return manuscript


def _destination_page(*, require_ready: bool) -> dict[str, str]:
    pages = ready_sync._query_db(
        ready_sync.DEST_DATA_SOURCE_ID,
        ready_sync.DEST_DATABASE_ID,
        payload={"filter": {"property": "同期ID", "rich_text": {"equals": SYNC_ID}}},
    )
    exact = [
        page
        for page in pages
        if str(page.get("id") or "").replace("-", "").lower()
        == DESTINATION_PAGE_ID.replace("-", "")
        and ready_sync._normalize_page_id(
            ready_sync._text((page.get("properties") or {}).get("同期ID"))
        )
        == SYNC_ID
    ]
    if len(exact) != 1:
        raise OpenAI2015ResyncError("Exact OpenAI 2015 note queue row was not found")
    props = exact[0].get("properties") or {}
    posting = ready_sync._select(props.get("投稿状態"))
    quality = ready_sync._select(props.get("品質状態"))
    if posting != "投稿準備中":
        raise OpenAI2015ResyncError(
            f"Existing OpenAI 2015 draft is not 投稿準備中: {posting!r}"
        )
    if require_ready:
        if quality != "Ready":
            raise OpenAI2015ResyncError(
                f"Exact queue row did not return to Ready after recaption: {quality!r}"
            )
    elif quality not in {"Ready", "Ready取消"}:
        raise OpenAI2015ResyncError(f"Unexpected queue quality state: {quality!r}")
    if ready_sync._url(props.get("note公開URL")) or audit_base._prop_date(
        props.get("投稿日")
    ):
        raise OpenAI2015ResyncError(
            "Public-post evidence exists; refusing to mutate the private draft"
        )
    return {"posting_state": posting, "quality_state": quality}


def _recaption_and_exact_sync(manuscript: str) -> None:
    _source_page()
    current = ready_sync._source_current_ready_manuscript(SYNC_ID)
    if current != manuscript:
        caption = publication_contract.current_ready_caption(manuscript)
        if not publication_contract.is_current_ready_block(manuscript, caption):
            raise OpenAI2015ResyncError("Current publication caption self-check failed")
        children = build_notion_manuscript_children(
            manuscript,
            caption,
            chunker=lambda text: safe_chunk_text(text, 1800),
        )
        response = ready_sync._request(
            "PATCH",
            f"https://api.notion.com/v1/blocks/{SYNC_ID}/children",
            json={"children": children},
        )
        if response.status_code != 200:
            raise OpenAI2015ResyncError(
                f"Current-policy manuscript append failed: HTTP {response.status_code}"
            )
    ready_sync.sync_note_ready_db(target_sync_id=SYNC_ID)
    if ready_sync._source_current_ready_manuscript(SYNC_ID) != manuscript:
        raise OpenAI2015ResyncError(
            "Current-policy manuscript did not survive byte verification"
        )
    _destination_page(require_ready=True)


def _find_exact_existing_draft(page: Any, profile) -> str:
    matched: dict[str, str] = {}
    for candidate in audit_base._recent_private_edit_urls(profile):
        try:
            page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(900)
            if note_base._looks_logged_out(page):
                if not run190._seed_note_state(page.context, page):
                    continue
                page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(700)
            if (
                audit_base._is_note_edit_url(str(page.url or ""))
                and audit_base._title_value(page) == TITLE
            ):
                matched[_route_key(str(page.url))] = str(page.url)
        except Exception:
            continue
    if len(matched) != 1:
        raise OpenAI2015ResyncError(
            f"Expected exactly one existing OpenAI 2015 private draft; found {len(matched)}"
        )
    return next(iter(matched.values()))


def _draft_route_preflight() -> str:
    from playwright.sync_api import sync_playwright

    run190.install()
    profile = run190._profile_dir()
    with sync_playwright() as playwright:
        context = run190._launch_persistent_context(playwright)
        try:
            page = context.new_page()
            return _find_exact_existing_draft(page, profile)
        finally:
            context.close()


def _browser_resync(manuscript: str, *, expected_route: str) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    body_manuscript = note_base._body_manuscript_for_note(TITLE, manuscript)
    run190.install()
    run417.install(note_base)
    profile = run190._profile_dir()

    with sync_playwright() as playwright:
        context = run190._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            url = _find_exact_existing_draft(page, profile)
            if not _same_edit_route(expected_route, url):
                raise OpenAI2015ResyncError("Existing draft route changed after preflight")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1000)
            if (
                not _same_edit_route(url, str(page.url))
                or audit_base._title_value(page) != TITLE
            ):
                raise OpenAI2015ResyncError("Exact existing note draft identity changed")

            title_field = note_base._set_title(page, TITLE)
            body = note_base._find_body(page, title_field)
            note_base._paste_manuscript(page, body, body_manuscript)
            body = note_base._find_body(page, title_field)
            note_base._verify_body_content(body, body_manuscript)
            saved = note_base._save_draft_and_verify(
                page, TITLE, body_manuscript, image_required=True
            )
            if not _same_edit_route(url, saved):
                raise OpenAI2015ResyncError(
                    "Save escaped the existing OpenAI 2015 private draft"
                )
            return {
                "status": "existing_draft_resynced",
                "same_edit_route": True,
                "title_match": audit_base._title_value(page) == TITLE,
                "body_verified": True,
                "eyecatch_unchanged": True,
                "editor_route_hash": hashlib.sha256(
                    _route_key(url).encode("utf-8")
                ).hexdigest()[:12],
                "zero_gemini_calls": True,
                "new_draft_created": False,
                "public_release": False,
            }
        finally:
            context.close()


def run(*, confirm: str, prepare_only: bool = False) -> dict[str, Any]:
    if confirm != CONFIRM_TOKEN:
        raise OpenAI2015ResyncError("Exact resync confirmation token is required")
    _source_page()
    manuscript = _operator_manuscript()
    state = _destination_page(require_ready=False)
    result: dict[str, Any] = {
        "status": "resync_ready" if prepare_only else "existing_draft_resynced",
        "sync_id": SYNC_ID,
        "zero_gemini_calls": True,
        "new_draft_created": False,
        "public_release": False,
        "eyecatch_unchanged": True,
        "posting_state_preserved": state["posting_state"],
    }
    if prepare_only:
        return result

    # Prove the existing private edit route before any Notion mutation.
    route = _draft_route_preflight()
    _recaption_and_exact_sync(manuscript)
    result.update(_browser_resync(manuscript, expected_route=route))
    result["quality_state_after_sync"] = _destination_page(
        require_ready=True
    )["quality_state"]
    return result


def main() -> None:
    result = run(
        confirm=os.environ.get("OPENAI2015_RESYNC_CONFIRM", ""),
        prepare_only=os.environ.get(
            "OPENAI2015_RESYNC_PREPARE_ONLY", ""
        ).lower()
        in {"1", "true", "yes", "on"},
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
