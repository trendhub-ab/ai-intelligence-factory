#!/usr/bin/env python3
"""Repair one existing VT Code private note draft; never create or publish an article."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import note_draft_automation as note_base
import note_ready_sync as ready_sync
import note_eyecatch_persistence as eyecatch
import publication_contract
import run190_note_persistent_cloud as run190
import run193_note_official_header_upload as official_image
import run291_note_private_draft_audit as audit_base
import run417_note_body_verification as run417
from notion_payloads import build_notion_manuscript_children, safe_chunk_text
from run_sgps_existing_draft_repair import _same_edit_route, _route_key

SYNC_ID = "3d4479ffdca981a2880bf46d5c02403d"
DESTINATION_PAGE_ID = "3e7479ff-dca9-819b-aeba-ce65d5fb919f"
CONFIRM_TOKEN = "REPAIR_VTCODE_EXISTING_DRAFT"
OLD_TITLE = "Show HN: VT Code – My attempt at building a coding-agent harness：いま何を判断材料にするべきか。"
NEW_TITLE = "VT Code：AIのコード変更をどう確認する？"
MANUSCRIPT_PATH = Path(__file__).resolve().parent / "repairs/vtcode_publishable_20260927.md"
IMAGE_PATH = Path(__file__).resolve().parent / "repairs/vtcode_eyecatch_20260927.png"
IMAGE_URL = "https://raw.githubusercontent.com/trendhub-ab/ai-intelligence-factory/main/repairs/vtcode_eyecatch_20260927.png"
PRIMARY_URL = "https://github.com/vinhnx/VTCode"
SOURCE_REVIEW_PATH = Path(__file__).resolve().parent / "repairs/vtcode_source_review_20260927.json"


class VTCodeRepairError(RuntimeError):
    pass


def load_manuscript() -> str:
    text = MANUSCRIPT_PATH.read_text(encoding="utf-8").strip()
    if len(text) < 1200 or not text.startswith(f"# {NEW_TITLE}\n"):
        raise VTCodeRepairError("Exact repaired manuscript is missing or malformed")
    if text.count("### Sources / Evidence") != 1 or "※本記事に含まれる見解・提案は" not in text:
        raise VTCodeRepairError("Repaired article lacks complete provenance")
    if not IMAGE_PATH.is_file() or IMAGE_PATH.stat().st_size < 10000:
        raise VTCodeRepairError("Repaired eyecatch is missing")
    return text


def _core(manuscript: str) -> str:
    core = manuscript.split("\n### Sources / Evidence", 1)[0].strip()
    if not core:
        raise VTCodeRepairError("Article core is empty")
    return core


def _reviewed_source() -> tuple[str, dict, dict]:
    """Use the recorded official README observations, including their explicit limits."""
    review = json.loads(SOURCE_REVIEW_PATH.read_text(encoding="utf-8"))
    if review.get("primary_url") != PRIMARY_URL or len(review.get("observations") or []) < 4 or not review.get("limits"):
        raise VTCodeRepairError("Official source review is incomplete")
    source_context = "\n".join([PRIMARY_URL, *review["observations"], *review["limits"]])
    source_info = {"sufficient": True, "deep_source_required": True,
                   "deep_source_scanned": bool(review.get("primary_sections")), "decision_scope_safe": True}
    evidence = {"evidence_strength": "PRIMARY_SOURCE", "coverage": {
        "code_availability": "FOUND", "runtime": "UNKNOWN", "benchmark": "UNKNOWN", "hardware": "UNKNOWN"}}
    return source_context, source_info, evidence


def validate_repaired_manuscript(manuscript: str | None = None) -> dict[str, Any]:
    """Apply the current deterministic Production gates before any Notion/note mutation."""
    import pipeline
    import production_pipeline
    import source_normalization
    import reader_quality_precision
    import run283_numeric_evidence_equivalence
    import run284_reader_recovery_precision
    import runtime_layers

    source_normalization.install(pipeline)
    production_pipeline.install_runtime_layers(pipeline)
    run283_numeric_evidence_equivalence.install(pipeline)
    reader_quality_precision.install(pipeline)
    run284_reader_recovery_precision.install(pipeline)
    body = manuscript if manuscript is not None else load_manuscript()
    source_context, source_info, evidence_metadata = _reviewed_source()
    parsed = {
        "note_draft": _core(body), "title_text": NEW_TITLE, "decision_text": "TRY", "score": 70,
        "decision_reason_text": "公式リポジトリにレビュー用コマンドとツール実行ポリシーが記されており、隔離環境での小規模な試用で条件を確認する価値がある。",
        "action_text": "使い捨ての作業ディレクトリで vtcode init が作る設定ファイルを確認し、vtcode review の操作を試す。",
        "source_summary_text": "VT CodeはRust製のコーディングエージェントで、レビュー用コマンドとツール実行ポリシーを備える。",
        "alternative_comparison_text": "",
    }
    fact_ok, fact_failures = pipeline.validate_fact_gate(
        parsed, "vtcode-existing-draft-repair", source_context=source_context,
        source="HackerNews", evidence_metadata=evidence_metadata, source_info=source_info,
        freshness={"status": "CURRENT"}, output_truncated=False,
    )
    editorial_ok, editorial_warnings = pipeline.validate_editorial_gate(parsed, "vtcode-existing-draft-repair")
    publication_state, publication_issues = pipeline.validate_publication_readiness_gate(parsed, source_context, source_info)
    human_state, human_issues = pipeline.validate_human_appeal_gate(parsed, [])
    result = {"fact_ok": bool(fact_ok), "editorial_ok": bool(editorial_ok),
              "publication_state": publication_state, "human_state": human_state,
              "issues": list(fact_failures or []) + list(editorial_warnings or []) + list(publication_issues or []) + list(human_issues or [])}
    if not fact_ok or not editorial_ok or publication_state != "PASS" or human_state != "ACCEPTABLE":
        raise VTCodeRepairError("Current publication gates reject the repair: " + "; ".join(result["issues"]))
    return result


def destination_preflight() -> dict[str, str]:
    pages = ready_sync._query_db(ready_sync.DEST_DATA_SOURCE_ID, ready_sync.DEST_DATABASE_ID,
        payload={"filter": {"property": "同期ID", "rich_text": {"equals": SYNC_ID}}})
    exact = [page for page in pages if str(page.get("id") or "").replace("-", "").lower() == DESTINATION_PAGE_ID.replace("-", "")
             and ready_sync._normalize_page_id(ready_sync._text((page.get("properties") or {}).get("同期ID"))) == SYNC_ID]
    if len(exact) != 1:
        raise VTCodeRepairError("Exact VT Code note queue row was not found")
    p = exact[0]["properties"]
    posting, quality = ready_sync._select(p.get("投稿状態")), ready_sync._select(p.get("品質状態"))
    if posting != "投稿準備中":
        raise VTCodeRepairError(f"VT Code queue row is not 投稿準備中: {posting!r}")
    if quality != "Ready":
        raise VTCodeRepairError(f"VT Code queue row is not Ready: {quality!r}")
    if ready_sync._url(p.get("note公開URL")) or audit_base._prop_date(p.get("投稿日")):
        raise VTCodeRepairError("VT Code destination has public-post evidence; refusing to edit")
    return {"posting_state": posting, "quality_state": quality}


def _source_preflight() -> dict:
    response = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{SYNC_ID}")
    if response.status_code != 200:
        raise VTCodeRepairError("VT Code Content Intelligence source could not be read")
    page = response.json()
    props = page.get("properties") or {}
    if ready_sync._select(props.get("記事状態")) != "Ready" or ready_sync._text(props.get("note記事タイトル")) not in {OLD_TITLE, NEW_TITLE}:
        raise VTCodeRepairError("Exact VT Code source title/status changed")
    if ready_sync._url(props.get("元情報URL")).casefold() != PRIMARY_URL.casefold():
        raise VTCodeRepairError("VT Code primary source changed")
    return page


def sync_corrected_source(manuscript: str) -> None:
    """Replace only exact article title/eyecatch and append a byte-valid Ready manuscript."""
    page = _source_preflight()
    current = ready_sync._source_current_ready_manuscript(SYNC_ID)
    props = page.get("properties") or {}
    desired = {"note記事タイトル": {"rich_text": [{"text": {"content": NEW_TITLE}}]},
               "アイキャッチ": {"files": [{"type": "external", "name": "VT Code corrected eyecatch", "external": {"url": IMAGE_URL}}]}}
    if ready_sync._text(props.get("note記事タイトル")) != NEW_TITLE or ready_sync._files_url(props.get("アイキャッチ")) != IMAGE_URL:
        response = ready_sync._request("PATCH", f"https://api.notion.com/v1/pages/{SYNC_ID}", json={"properties": desired})
        if response.status_code != 200:
            raise VTCodeRepairError("Exact source metadata update failed")
    if current != manuscript:
        caption = publication_contract.current_ready_caption(manuscript)
        children = build_notion_manuscript_children(manuscript, caption,
            chunker=lambda text: safe_chunk_text(text, 1800))
        response = ready_sync._request("PATCH", f"https://api.notion.com/v1/blocks/{SYNC_ID}/children", json={"children": children})
        if response.status_code != 200:
            raise VTCodeRepairError("Corrected manuscript append failed")
    # The destination row remains 投稿準備中 and no unrelated queue row is touched.
    ready_sync.sync_note_ready_db(target_sync_id=SYNC_ID)
    if ready_sync._source_current_ready_manuscript(SYNC_ID) != manuscript:
        raise VTCodeRepairError("Corrected manuscript did not survive current-policy verification")


def _find_exact_existing_draft(page: Any, profile: Path) -> str:
    matched: dict[str, str] = {}
    for candidate in audit_base._recent_private_edit_urls(profile):
        try:
            page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(900)
            if note_base._looks_logged_out(page):
                if not run190._seed_note_state(page.context, page):
                    continue
                page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
            if audit_base._is_note_edit_url(str(page.url or "")) and audit_base._title_value(page) in {OLD_TITLE, NEW_TITLE}:
                matched[_route_key(str(page.url))] = str(page.url)
        except Exception:
            continue
    if len(matched) != 1:
        raise VTCodeRepairError(f"Expected one existing VT Code private draft; found {len(matched)}")
    return next(iter(matched.values()))


def _header_media_identity(page: Any) -> str:
    """Fingerprint the unique visible cover media near the title, never expose its URL."""
    title_box = note_base._find_title(page).bounding_box()
    if not title_box:
        raise VTCodeRepairError("Draft title has no geometry for cover verification")
    media = page.evaluate("""(titleY) => {
        const result = [];
        for (const el of document.querySelectorAll('img, picture, figure, section, div')) {
            const r = el.getBoundingClientRect();
            if (r.width < 420 || r.height < 140 || r.top >= titleY || r.top < -500) continue;
            const style = getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden') continue;
            const value = el.tagName === 'IMG' ? (el.currentSrc || el.src) :
                (style.backgroundImage !== 'none' ? style.backgroundImage : '');
            if (value) result.push(value);
        }
        return [...new Set(result)];
    }""", float(title_box["y"]))
    if not isinstance(media, list) or len(media) != 1:
        raise VTCodeRepairError("Cover media cannot be identified uniquely")
    return hashlib.sha256(str(media[0]).encode()).hexdigest()


def _cover_changed(page: Any, old_identity: str) -> bool:
    try:
        return _header_media_identity(page) != old_identity
    except VTCodeRepairError:
        return False


def _open_exact_draft(page: Any, profile: Path, *, expected_route: str | None = None) -> str:
    url = _find_exact_existing_draft(page, profile)
    if expected_route is not None and not _same_edit_route(expected_route, url):
        raise VTCodeRepairError("Draft route changed after preflight")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1000)
    if not _same_edit_route(url, str(page.url)) or audit_base._title_value(page) not in {OLD_TITLE, NEW_TITLE}:
        raise VTCodeRepairError("Existing VT Code draft route/title changed")
    return url


def draft_preflight() -> str:
    """Read-only confirmation of exactly one existing edit route before Notion writes."""
    from playwright.sync_api import sync_playwright
    run190.install()
    profile = run190._profile_dir()
    with sync_playwright() as playwright:
        context = run190._launch_persistent_context(playwright)
        try:
            page = context.new_page()
            return _open_exact_draft(page, profile)
        finally:
            context.close()


def browser_repair(manuscript: str, *, expected_route: str) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright
    body_manuscript = note_base._body_manuscript_for_note(NEW_TITLE, manuscript)
    run190.install()
    run417.install(note_base)
    profile = run190._profile_dir()
    with sync_playwright() as playwright:
        context = run190._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            url = _open_exact_draft(page, profile, expected_route=expected_route)
            old_media = _header_media_identity(page)
            title_field = note_base._set_title(page, NEW_TITLE)
            body = note_base._find_body(page, title_field)
            note_base._paste_manuscript(page, body, body_manuscript)
            body = note_base._find_body(page, title_field)
            note_base._verify_body_content(body, body_manuscript)
            saved = note_base._save_draft_and_verify(page, NEW_TITLE, body_manuscript, image_required=True)
            if not _same_edit_route(url, saved):
                raise VTCodeRepairError("Save escaped the existing VT Code private draft")
            # The title/body are durable before a separate cover replacement. Never
            # use a hidden posting API or navigate to /new.
            official_image._upload_header_image(page, IMAGE_PATH,
                media_changed=lambda: _cover_changed(page, old_media))
            saved = note_base._save_draft_and_verify(page, NEW_TITLE, body_manuscript, image_required=True)
            if not _same_edit_route(url, saved):
                raise VTCodeRepairError("Cover save escaped the existing VT Code draft")
            metrics = eyecatch.collect_eyecatch_metrics(page, title_locator=note_base._find_title(page))
            if not eyecatch.eyecatch_persistence_confirmed(metrics):
                raise VTCodeRepairError("Repaired VT Code eyecatch did not persist")
            if _header_media_identity(page) == old_media:
                raise VTCodeRepairError("Repaired cover still uses the original image")
            return {"status": "existing_draft_repaired", "same_edit_route": True,
                    "title_match": audit_base._title_value(page) == NEW_TITLE,
                    "body_verified": True, "eyecatch_verified": True,
                    "editor_route_hash": hashlib.sha256(_route_key(url).encode()).hexdigest()[:12],
                    "zero_gemini_calls": True, "new_draft_created": False, "public_release": False}
        finally:
            context.close()


def run(*, confirm: str, prepare_only: bool = False) -> dict[str, Any]:
    if confirm != CONFIRM_TOKEN:
        raise VTCodeRepairError("Explicit exact-target repair token is required")
    manuscript = load_manuscript()
    gates = validate_repaired_manuscript(manuscript)
    state = destination_preflight()
    _source_preflight()
    result = {"status": "repair_ready" if prepare_only else "existing_draft_repaired",
              "sync_id": SYNC_ID, "zero_gemini_calls": True, "new_draft_created": False,
              "public_release": False, "publication_gates_passed": True,
              "quality_state_preserved": state["quality_state"],
              "posting_state_preserved": state["posting_state"],
              "gate_summary": {k: gates[k] for k in ("fact_ok", "editorial_ok", "publication_state", "human_state")}}
    if not prepare_only:
        route = draft_preflight()
        sync_corrected_source(manuscript)
        destination_preflight()
        result.update(browser_repair(manuscript, expected_route=route))
    return result


def main() -> None:
    result = run(confirm=os.environ.get("VTCODE_DRAFT_REPAIR_CONFIRM", ""),
                 prepare_only=os.environ.get("VTCODE_DRAFT_REPAIR_PREPARE_ONLY", "").lower() in {"1", "true", "yes"})
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
