#!/usr/bin/env python3
"""Run418: replace the one broken RubyGems eyecatch with the canonical Production design.

Run416 incorrectly called the raw editorial_eyecatch renderer and therefore bypassed the
Production eyecatch stack (Run179/180/181/182/183/296). This one-off repair:
- is pinned to the exact RubyGems Content Intelligence page and existing private draft;
- requires the known Run416 eyecatch before replacing it;
- installs the canonical Production runtime and requires the official Run179 font asset;
- spends exactly one Gemini 3.5 call for the existing Run180 semantic layout plan;
- refuses the raw/base renderer fallback when that plan is invalid;
- renders through the current balanced/emphasis/editorial-v2 stack;
- replaces only the eyecatch in Notion and in the same existing note draft;
- proves title/body/route identity are unchanged and contains no public-release action.

Gemini 3.8 is never selected by this module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import requests

PAGE_ID = "3d9479ff-dca9-819a-814c-e4a0aeb3263f"
SYNC_ID = "3d9479ffdca9819a814ce4a0aeb3263f"
EXPECTED_SOURCE_TITLE = "OpenAI agents carried out an undisclosed attack on RubyGems"
EXPECTED_NOTE_TITLE = "AIが勝手に他社サーバーを突破した？OpenAIエージェントが起こしたRubyGems騒動から考える権限管理の境界線"
BROKEN_FILENAME = "run414-rubygems.png"
FIXED_FILENAME = "run418-rubygems-canonical.png"
SUMMARY = "OpenAIのAIエージェントとRubyGemsを巡るセキュリティ事例"
CATEGORY = "SECURITY"
NOTION_VERSION = "2026-03-11"
OUTPUT = Path("note_eyecatch_images") / FIXED_FILENAME
CONFIRM = "RUN418_EXACT_RUBYGEMS_CANONICAL_EYECATCH"


class Run418Error(RuntimeError):
    pass


def _notion_headers(json_content: bool = True) -> dict[str, str]:
    token = (os.getenv("NOTION_API_KEY") or os.getenv("NOTION_DECISION_INTELLIGENCE_API_KEY") or "").strip()
    if not token:
        raise Run418Error("Notion token required")
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION}
    if json_content:
        headers["Content-Type"] = "application/json"
    return headers


def _plain(values: list[dict] | None) -> str:
    return "".join(
        str(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
        for item in (values or [])
    )


def _fetch_exact_target(*, require_broken: bool = False, require_fixed: bool = False) -> dict[str, Any]:
    response = requests.get(
        f"https://api.notion.com/v1/pages/{PAGE_ID}", headers=_notion_headers(), timeout=30
    )
    if response.status_code != 200:
        raise Run418Error(f"Content Intelligence page read failed HTTP {response.status_code}")
    page = response.json()
    if str(page.get("id") or "").replace("-", "").lower() != SYNC_ID:
        raise Run418Error("Run418 page id drift")
    props = page.get("properties") or {}
    title = _plain((props.get("記事名") or {}).get("title"))
    note_title = _plain((props.get("note記事タイトル") or {}).get("rich_text"))
    state = str((((props.get("記事状態") or {}).get("select") or {}).get("name")) or "")
    files = (props.get("アイキャッチ") or {}).get("files") or []
    names = [str(item.get("name") or "") for item in files if isinstance(item, dict)]
    if title != EXPECTED_SOURCE_TITLE or note_title != EXPECTED_NOTE_TITLE or state != "Ready":
        raise Run418Error(
            f"Run418 exact target mismatch source={title!r} note={note_title!r} state={state!r}"
        )
    if len(files) != 1:
        raise Run418Error(f"Run418 requires exactly one current eyecatch, found={len(files)}")
    if require_broken and names != [BROKEN_FILENAME]:
        raise Run418Error(f"Run418 refuses to replace an unknown eyecatch: {names!r}")
    if require_fixed and names != [FIXED_FILENAME]:
        raise Run418Error(f"Run418 canonical eyecatch postcondition failed: {names!r}")
    return page


def _install_canonical_eyecatch_runtime():
    import pipeline
    import production_pipeline
    import run179_eyecatch_font_refinement as r179

    production_pipeline.install_runtime_layers(pipeline)
    status = r179.ensure_google_font_assets(enabled=True, logger=getattr(pipeline, "logger", None))
    noto_ready = bool(status.get(str(r179.NOTO_SANS_JP_PATH)))
    if not noto_ready or not r179._valid_font_file(r179.NOTO_SANS_JP_PATH, 5_000_000):
        raise Run418Error("Run418 refuses Japanese rendering without the canonical Noto Sans JP asset")

    required_markers = (
        "_RUN179_EYECATCH_FONT_REFINEMENT_INSTALLED",
        "_RUN180_EYECATCH_SEMANTIC_LAYOUT_INSTALLED",
        "_RUN181_EYECATCH_VISUAL_BALANCE_INSTALLED",
        "_RUN182_EYECATCH_CONCLUSION_EMPHASIS_INSTALLED",
        "_RUN183_EYECATCH_EMPHASIS_SCALE_INSTALLED",
        "_RUN296_EDITORIAL_FORMAT_V2_INSTALLED",
    )
    missing = [name for name in required_markers if not bool(getattr(pipeline, name, False))]
    if missing:
        raise Run418Error(f"Run418 canonical Production eyecatch stack incomplete: {missing}")
    return pipeline


def _render_canonical() -> tuple[Path, dict[str, Any]]:
    # Import after Production install so these modules carry the live current overlays.
    pipeline = _install_canonical_eyecatch_runtime()
    import editorial_eyecatch as ee
    import run178_eyecatch_editorial_layout_optimizer as r178
    import run180_eyecatch_semantic_layout as r180

    source_title = r180._source_title_for_direction(EXPECTED_NOTE_TITLE)
    existing_headline = ee.editorial_hook_from_title(EXPECTED_NOTE_TITLE, max_chars=48)
    subheadline = ee.editorial_subheadline(SUMMARY, existing_headline)

    original_generate = pipeline._generate_via_chat
    calls: list[str] = []

    def one_layout_call(model: str, *args: Any, **kwargs: Any):
        if calls:
            raise Run418Error("Run418 refuses a second model request")
        if str(model) != r180.EYECATCH_LAYOUT_MODEL or str(model) != "gemini-3.5-flash":
            raise Run418Error(f"Run418 refuses non-3.5 eyecatch model: {model}")
        if str(kwargs.get("request_kind") or "") != "eyecatch_layout":
            raise Run418Error("Run418 model call is not the canonical eyecatch_layout request")
        calls.append(str(model))
        return original_generate(model, *args, **kwargs)

    pipeline._generate_via_chat = one_layout_call
    try:
        raw_plan = r180._request_layout_plan(pipeline, source_title, subheadline)
    finally:
        pipeline._generate_via_chat = original_generate
    if calls != ["gemini-3.5-flash"]:
        raise Run418Error(f"Run418 expected exactly one Gemini 3.5 call, got {calls!r}")
    validated = r180._validate_layout_plan(source_title, subheadline, raw_plan)
    if validated is None:
        raise Run418Error("Run418 refuses raw/base eyecatch fallback because semantic layout plan was invalid")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # Runtime layers 181/182/183/296 have already patched this validated-plan renderer and
    # its typography helpers. This is the successful canonical Run180 Production path.
    result = r178._render_with_validated_plan(
        EXPECTED_NOTE_TITLE,
        SUMMARY,
        str(OUTPUT),
        validated,
        category=CATEGORY,
        date_label=None,
    )
    if str(result) != str(OUTPUT) or not OUTPUT.exists() or OUTPUT.stat().st_size < 10_000:
        raise Run418Error("Run418 canonical eyecatch render missing or unexpectedly small")

    from PIL import Image
    with Image.open(OUTPUT) as image:
        if image.size != (1280, 670) or image.format != "PNG":
            raise Run418Error(f"Run418 canonical eyecatch geometry invalid: {image.size} {image.format}")

    return OUTPUT, {
        "layout_title": str(validated.get("eyecatch_title") or ""),
        "title_lines": list(validated.get("title_lines") or []),
        "highlight_text": str(validated.get("highlight_text") or ""),
        "gemini_3_5_calls": 1,
        "gemini_3_8_calls": 0,
    }


def _upload_replace(path: Path) -> str:
    create = requests.post(
        "https://api.notion.com/v1/file_uploads",
        headers=_notion_headers(),
        json={"mode": "single_part", "filename": FIXED_FILENAME, "content_type": "image/png"},
        timeout=30,
    )
    if create.status_code not in (200, 201):
        raise Run418Error(f"Notion upload create failed HTTP {create.status_code}: {create.text[:300]}")
    upload_id = str((create.json() or {}).get("id") or "").strip()
    if not upload_id:
        raise Run418Error("Notion file upload id missing")
    with path.open("rb") as handle:
        send = requests.post(
            f"https://api.notion.com/v1/file_uploads/{upload_id}/send",
            headers=_notion_headers(json_content=False),
            files={"file": (FIXED_FILENAME, handle, "image/png")},
            timeout=60,
        )
    if send.status_code not in (200, 201):
        raise Run418Error(f"Notion upload send failed HTTP {send.status_code}: {send.text[:300]}")
    patch = requests.patch(
        f"https://api.notion.com/v1/pages/{PAGE_ID}",
        headers=_notion_headers(),
        json={
            "properties": {
                "アイキャッチ": {
                    "files": [
                        {
                            "name": FIXED_FILENAME,
                            "type": "file_upload",
                            "file_upload": {"id": upload_id},
                        }
                    ]
                }
            }
        },
        timeout=30,
    )
    if patch.status_code != 200:
        raise Run418Error(f"Notion eyecatch replacement failed HTTP {patch.status_code}: {patch.text[:300]}")
    _fetch_exact_target(require_fixed=True)
    return upload_id


def render_and_attach() -> dict[str, Any]:
    _fetch_exact_target(require_broken=True)
    path, plan = _render_canonical()
    upload_id = _upload_replace(path)
    return {
        "status": "canonical_eyecatch_attached",
        "page_id": PAGE_ID,
        "file": FIXED_FILENAME,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "upload_id": upload_id,
        "body_changed": False,
        "public_release": False,
        **plan,
    }


def refresh_existing_private_draft() -> dict[str, Any]:
    _fetch_exact_target(require_fixed=True)
    import note_draft_automation as note_base
    import note_eyecatch_persistence as persistence
    import note_ready_sync as ready_sync
    import run190_note_persistent_cloud as cloud
    import run193_note_official_header_upload as official_header
    import run291_note_private_draft_audit as audit291
    import run298_genrec_inplace_refresh as route_helpers
    import run298_hover_header_final as header_helpers
    import run417_note_body_verification as run417

    article = audit291._expected_article(SYNC_ID)
    if article.get("sync_id") != SYNC_ID or str(article.get("title") or "") != EXPECTED_NOTE_TITLE:
        raise Run418Error("Run418 private draft source/destination identity drift")
    manuscript = str(article.get("manuscript") or "")
    if len(manuscript) < 200:
        raise Run418Error("Run418 prepared manuscript unexpectedly short")

    source_response = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{SYNC_ID}")
    if source_response.status_code != 200:
        raise Run418Error("Run418 could not re-read source eyecatch")
    source_state = ready_sync._source_state(source_response.json())
    eyecatch_url = str((source_state or {}).get("eyecatch_url") or "")
    if not eyecatch_url:
        raise Run418Error("Run418 canonical source eyecatch URL missing")

    official_header.install()
    persistence.install_creation_persistence_guard(note_base)
    run417.install(note_base)
    image_path = note_base._download_eyecatch(eyecatch_url, SYNC_ID)
    if image_path.stat().st_size < 10_000:
        raise Run418Error("Run418 downloaded canonical eyecatch unexpectedly small")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise Run418Error("Playwright required for exact existing-draft repair") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            route, matched_rank, candidate_count = route_helpers._find_one_existing_route(
                context, page, EXPECTED_NOTE_TITLE
            )
            route_key = route_helpers._route_key(route)
            page.goto(route, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1000)
            if note_base._looks_logged_out(page):
                if not cloud._seed_note_state(context, page):
                    raise Run418Error("note authentication inactive")
                page.goto(route, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1000)
            if route_helpers._route_key(str(page.url or "")) != route_key:
                raise Run418Error("Run418 existing private draft route changed")
            if route_helpers._safe_title(page) != EXPECTED_NOTE_TITLE:
                raise Run418Error("Run418 existing private draft title mismatch")

            title_field = note_base._find_title(page)
            body, before_body = route_helpers._visible_body(page, title_field)
            # Prove the existing body is already the approved manuscript before touching the header.
            run417.verify_body_content(body, manuscript)
            before_hash, before_count = route_helpers._header_media_fingerprint(page, title_field)
            if not before_hash or before_count < 1:
                raise Run418Error("Run418 existing broken header not proven")

            header_result = header_helpers._replace_existing_header(page, image_path, title_field)
            saved_url = note_base._save_draft_and_verify(
                page, EXPECTED_NOTE_TITLE, manuscript, image_required=True
            )
            if route_helpers._route_key(saved_url) != route_key:
                raise Run418Error("Run418 accidentally changed private draft identity")

            title_field = note_base._find_title(page)
            body, after_body = route_helpers._visible_body(page, title_field)
            run417.verify_body_content(body, manuscript)
            if after_body != before_body:
                raise Run418Error("Run418 body changed during header-only repair")
            if route_helpers._safe_title(page) != EXPECTED_NOTE_TITLE:
                raise Run418Error("Run418 title changed during header-only repair")
            final_hash, final_count = route_helpers._header_media_fingerprint(page, title_field)
            if not final_hash or final_count < 1 or final_hash == before_hash:
                raise Run418Error("Run418 canonical private-draft header did not persist")
            audit291._destination_row(SYNC_ID)  # Ready / 投稿準備中 and no public evidence.

            return {
                "status": "existing_private_draft_header_replaced",
                "sync_id": SYNC_ID,
                "same_private_draft_route": True,
                "history_candidate_count": candidate_count,
                "matched_history_rank": matched_rank,
                "header_media_changed": bool(header_result.get("header_media_changed")),
                "body_unchanged": True,
                "title_unchanged": True,
                "duplicate_draft_created": False,
                "gemini_calls": 0,
                "public_release": False,
            }
        finally:
            context.close()


def main() -> int:
    if os.getenv("RUN418_CONFIRM", "").strip() != CONFIRM:
        raise Run418Error("Run418 explicit confirmation missing")
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("render-attach", "refresh-draft"))
    args = parser.parse_args()
    result = render_and_attach() if args.mode == "render-attach" else refresh_existing_private_draft()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
