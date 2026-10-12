#!/usr/bin/env python3
"""Regenerate one explicitly selected Ready article and overwrite its existing private note draft.

This lane is deliberately manual and exact-target only. It does not weaken or reuse the
normal automatic existing-article recovery authority: automatic Production must continue
to refuse write-enabled recovery after note delivery has started.

Safety contract:
- exact 32-hex Content Intelligence page/sync id;
- exactly one existing note queue row, quality=Ready, posting=投稿準備中;
- an existing stored note下書きID is mandatory and is the draft identity authority;
- any note public URL/date evidence blocks the operation;
- current Production regeneration must return accepted before note mutation;
- persistence targets the same Content Intelligence page with persist_results=True;
- note Ready reconciliation may update automated article fields but cannot replace the
  human delivery state or the stored draft identity;
- the browser opens only /notes/<stored-id>/edit, then updates title, body, and current
  eyecatch on that same edit identity;
- no /new navigation and no public-release control exists in this module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import article_revalidation
import eyecatch_publication_contract as eyecatch_contract
import note_draft_automation as note_base
import note_eyecatch_persistence as eyecatch
import note_ready_sync as ready_sync
import run190_note_persistent_cloud as run190
import run193_note_official_header_upload as official_image
import run222_note_presentation_integrity as run222
import run291_note_private_draft_audit as audit_base
import run417_note_body_verification as run417

CONFIRM_TOKEN = "REGENERATE_EXISTING_READY_DRAFT"
TARGET_ENV = "READY_DRAFT_REGENERATION_SYNC_ID"
CONFIRM_ENV = "READY_DRAFT_REGENERATION_CONFIRM"
DEFAULT_SCAN_LIMIT = 100


class ReadyDraftRegenerationError(RuntimeError):
    pass


def _normalize_sync_id(value: str) -> str:
    raw = str(value or "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{32}", raw) is None:
        raise ReadyDraftRegenerationError("sync_id must be exactly 32 hex characters")
    return raw.lower()


def _published_date(prop: dict | None) -> str:
    return str((((prop or {}).get("date") or {}).get("start")) or "").strip()


def _valid_note_draft_id(value: str) -> bool:
    return bool(re.fullmatch(r"n[0-9A-Za-z_-]{5,80}", str(value or "").strip()))


def destination_preflight(sync_id: str) -> dict[str, str]:
    """Prove one exact existing unpublished private-draft queue row."""
    sync_id = _normalize_sync_id(sync_id)
    pages = ready_sync._query_db(
        ready_sync.DEST_DATA_SOURCE_ID,
        ready_sync.DEST_DATABASE_ID,
        payload={"filter": {"property": "同期ID", "rich_text": {"equals": sync_id}}},
    )
    exact = [
        page
        for page in pages
        if ready_sync._normalize_page_id(
            ready_sync._text((page.get("properties") or {}).get("同期ID"))
        )
        == sync_id
    ]
    if len(exact) != 1:
        raise ReadyDraftRegenerationError(
            "expected exactly one existing note Ready destination row"
        )

    page = exact[0]
    props = page.get("properties") or {}
    quality = ready_sync._select(props.get("品質状態"))
    posting = ready_sync._select(props.get("投稿状態"))
    title = ready_sync._text(props.get("記事タイトル"))
    note_draft_id = ready_sync._text(props.get("note下書きID"))
    if quality != "Ready":
        raise ReadyDraftRegenerationError(f"destination is not Ready: {quality!r}")
    if posting != "投稿準備中":
        raise ReadyDraftRegenerationError(
            f"destination is not 投稿準備中: {posting!r}"
        )
    if not title:
        raise ReadyDraftRegenerationError("destination title is missing")
    if not _valid_note_draft_id(note_draft_id):
        raise ReadyDraftRegenerationError("destination has no valid existing note下書きID")
    if ready_sync._url(props.get("note公開URL")) or _published_date(props.get("投稿日")):
        raise ReadyDraftRegenerationError(
            "destination has public-post evidence; refusing existing-draft regeneration"
        )
    return {
        "sync_id": sync_id,
        "destination_page_id": str(page.get("id") or ""),
        "note_draft_id": note_draft_id,
        "title": title,
        "quality_state": quality,
        "posting_state": posting,
    }


def _draft_id_from_edit_url(url: str) -> str:
    try:
        parsed = urlparse(str(url or ""))
    except Exception:
        return ""
    if (parsed.hostname or "").lower() not in {"note.com", "editor.note.com"}:
        return ""
    match = re.fullmatch(r"/notes/([^/?#]+)/edit/?", parsed.path.rstrip("/") + "/")
    if not match:
        return ""
    value = str(match.group(1) or "").strip()
    return value if _valid_note_draft_id(value) else ""


def _same_exact_draft_route(left: str, right: str, note_draft_id: str) -> bool:
    target = str(note_draft_id or "").strip()
    return bool(
        _valid_note_draft_id(target)
        and _draft_id_from_edit_url(left) == target
        and _draft_id_from_edit_url(right) == target
    )


def _approval_is_valid(sync_id: str) -> bool:
    if os.environ.get(CONFIRM_ENV, "").strip() != CONFIRM_TOKEN:
        return False
    requested = os.environ.get(TARGET_ENV, "").strip()
    if not requested:
        return False
    try:
        return _normalize_sync_id(requested) == _normalize_sync_id(sync_id)
    except ReadyDraftRegenerationError:
        return False


def _select_exact_source_item(pipeline: Any, sync_id: str) -> dict[str, Any]:
    rows = pipeline.get_regen_test_items(DEFAULT_SCAN_LIMIT, "")
    if rows is None:
        raise ReadyDraftRegenerationError("existing article candidate read failed")
    matches = [
        dict(row or {})
        for row in rows
        if ready_sync._normalize_page_id((row or {}).get("notion_page_id") or "")
        == sync_id
    ]
    if len(matches) != 1:
        raise ReadyDraftRegenerationError(
            f"exact Content Intelligence target count mismatch: {len(matches)}"
        )
    return matches[0]


def _reconcile_failed_ready_target(sync_id: str, pipeline: Any) -> None:
    """Reconcile queue quality after a persisted regeneration failure, never mutate note."""
    try:
        ready_sync.sync_note_ready_db(target_sync_id=sync_id)
    except Exception as exc:
        pipeline.logger.warning(
            "[READY DRAFT REGENERATION RECONCILE FAILED] page=%s error=%s",
            sync_id,
            exc,
        )


def _persistent_generation_status(pipeline: Any, sync_id: str, generated: Any) -> str:
    """Classify persist_results=True without borrowing the non-persistent tuple contract."""
    if not generated:
        return "rejected"
    if isinstance(generated, tuple):
        if len(generated) < 2:
            return "unverified"
        explicit = str(generated[1] or "").strip().lower()
        return explicit if explicit in {"accepted", "rejected"} else "unverified"
    current = article_revalidation._read_current_statuses(pipeline, sync_id)
    if current == (
        pipeline.ARTICLE_STATUS_READY,
        pipeline.CONTENT_STATUS_DEEP_DIVE,
    ):
        return "accepted"
    return "rejected"


def run_ready_regeneration(pipeline: Any, sync_id: str) -> dict[str, Any]:
    """Run current Production generation against one already-delivered Ready source row."""
    sync_id = _normalize_sync_id(sync_id)
    if not _approval_is_valid(sync_id):
        raise ReadyDraftRegenerationError("explicit exact regeneration approval is missing")

    destination_before = destination_preflight(sync_id)
    item = _select_exact_source_item(pipeline, sync_id)
    page_id = ready_sync._normalize_page_id(item.get("notion_page_id") or "")
    if page_id != sync_id:
        raise ReadyDraftRegenerationError("selected source page identity changed")

    current = article_revalidation._read_current_statuses(pipeline, sync_id)
    if current is None:
        raise ReadyDraftRegenerationError("could not re-read current source lifecycle")
    article_status, content_status = current
    if article_status != pipeline.ARTICLE_STATUS_READY:
        raise ReadyDraftRegenerationError(
            f"source is not Ready: {article_status!r}"
        )

    # Treat this as an explicitly selected stale/current Ready recovery for source hydration
    # only. This does not call or change automatic delivery authority.
    hydrated_item = dict(item)
    hydrated_item["revalidation_stale_ready"] = True
    repo = article_revalidation.rehydrate_recovery_repo(pipeline, hydrated_item)
    if repo is None:
        raise ReadyDraftRegenerationError("exact source could not be safely rehydrated")
    safe, license_status = pipeline.legal_safety_gate(repo)
    if not safe:
        raise ReadyDraftRegenerationError(
            f"legal safety gate failed: {license_status}"
        )

    request_budget = article_revalidation._cap_validation_budget(pipeline)
    pipeline.logger.warning(
        "[READY DRAFT REGENERATION] exact page=%s request_budget=%s prior_content=%s persist=true",
        sync_id,
        request_budget,
        content_status,
    )
    generated = pipeline.generate_intelligence_report(
        repo,
        notion_page_id=sync_id,
        screening_score=item.get("screening_score"),
        screening_reason=item.get("screening_reason", ""),
        candidate_rank=1,
        candidate_origin="manual_ready_draft_regeneration",
        attribution_context=item,
        persist_results=True,
    )
    if not generated:
        _reconcile_failed_ready_target(sync_id, pipeline)
        raise ReadyDraftRegenerationError("exact target produced no manuscript")
    status = _persistent_generation_status(pipeline, sync_id, generated)
    manuscript = generated[0] if isinstance(generated, tuple) and generated else generated
    if status != "accepted":
        _reconcile_failed_ready_target(sync_id, pipeline)
        raise ReadyDraftRegenerationError(
            f"regenerated target did not pass current Production gates: status={status}"
        )

    sync_result = ready_sync.sync_note_ready_db(target_sync_id=sync_id)
    if int(sync_result.get("source_ready") or 0) != 1:
        raise ReadyDraftRegenerationError(
            "exact note Ready reconciliation did not preserve one current source"
        )
    destination_after = destination_preflight(sync_id)
    for key in ("destination_page_id", "note_draft_id", "posting_state"):
        if destination_after.get(key) != destination_before.get(key):
            raise ReadyDraftRegenerationError(
                f"existing draft binding changed during regeneration: {key}"
            )

    return {
        "selected": 1,
        "generated": 1,
        "accepted": 1,
        "sync_id": sync_id,
        "note_draft_id": destination_after["note_draft_id"],
        "destination_page_id": destination_after["destination_page_id"],
        "prior_title": destination_before["title"],
        "current_title": destination_after["title"],
        "chars": len(str(manuscript or "")),
        "new_draft_created": False,
        "public_release": False,
    }


def resume_persisted_ready_draft(pipeline: Any, sync_id: str) -> dict[str, Any]:
    """Resume delivery from an already-persisted Ready row without provider generation."""
    sync_id = _normalize_sync_id(sync_id)
    destination_before = destination_preflight(sync_id)
    current = article_revalidation._read_current_statuses(pipeline, sync_id)
    if current != (
        pipeline.ARTICLE_STATUS_READY,
        pipeline.CONTENT_STATUS_DEEP_DIVE,
    ):
        raise ReadyDraftRegenerationError(
            "persisted resume source is not current Ready / Deep Dive"
        )
    sync_result = ready_sync.sync_note_ready_db(target_sync_id=sync_id)
    if int(sync_result.get("source_ready") or 0) != 1:
        raise ReadyDraftRegenerationError(
            "persisted resume did not reconcile exactly one current Ready source"
        )
    destination_after = destination_preflight(sync_id)
    for key in ("destination_page_id", "note_draft_id", "posting_state"):
        if destination_after.get(key) != destination_before.get(key):
            raise ReadyDraftRegenerationError(
                f"existing draft binding changed during persisted resume: {key}"
            )
    return {
        "selected": 1,
        "generated": 0,
        "accepted": 1,
        "sync_id": sync_id,
        "note_draft_id": destination_after["note_draft_id"],
        "destination_page_id": destination_after["destination_page_id"],
        "prior_title": destination_before["title"],
        "current_title": destination_after["title"],
        "new_draft_created": False,
        "public_release": False,
    }


def _current_note_article(sync_id: str) -> dict[str, Any]:
    destination = destination_preflight(sync_id)
    response = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{sync_id}")
    if response.status_code != 200:
        raise ReadyDraftRegenerationError(
            f"Content Intelligence source fetch failed: HTTP {response.status_code}"
        )
    state = ready_sync._source_state(response.json())
    if state is None or state.get("sync_id") != sync_id:
        raise ReadyDraftRegenerationError("regenerated source is not an exact active Ready row")
    title = str(state.get("title") or "").strip()
    if title != destination["title"]:
        raise ReadyDraftRegenerationError(
            "regenerated source and destination titles do not match"
        )
    manuscript = ready_sync._source_current_ready_manuscript(sync_id)
    if not manuscript:
        raise ReadyDraftRegenerationError(
            "regenerated manuscript is not current under the Publication Contract"
        )
    image_url = str(state.get("eyecatch_url") or "").strip()
    try:
        eyecatch_contract.require_current_asset_url(image_url, title)
    except eyecatch_contract.EyecatchContractError as exc:
        raise ReadyDraftRegenerationError(
            "regenerated eyecatch is not current under the Eyecatch Contract"
        ) from exc
    presented = run222.prepare_note_editor_manuscript(manuscript, title)
    if len(presented) < 200:
        raise ReadyDraftRegenerationError(
            "regenerated note presentation is unexpectedly short"
        )
    try:
        image_path = note_base._download_eyecatch(image_url, sync_id, title)
    except note_base.NoteDraftError as exc:
        raise ReadyDraftRegenerationError(
            "regenerated eyecatch could not be downloaded and verified"
        ) from exc
    return {
        **destination,
        "manuscript": presented,
        "eyecatch_path": image_path,
    }


def _candidate_edit_urls(profile: Path, note_draft_id: str) -> list[str]:
    target = str(note_draft_id or "").strip()
    result: list[str] = []
    try:
        history = audit_base._recent_private_edit_urls(profile)
    except Exception:
        history = []
    for url in history:
        if _draft_id_from_edit_url(url) == target and url not in result:
            result.append(url)
    for url in (
        f"https://note.com/notes/{target}/edit",
        f"https://editor.note.com/notes/{target}/edit",
    ):
        if url not in result:
            result.append(url)
    return result


def _open_exact_existing_draft(page: Any, profile: Path, note_draft_id: str) -> str:
    target = str(note_draft_id or "").strip()
    if not _valid_note_draft_id(target):
        raise ReadyDraftRegenerationError("stored note draft identity is invalid")
    seeded = False
    for candidate in _candidate_edit_urls(profile, target):
        try:
            page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(900)
            if note_base._looks_logged_out(page) and not seeded:
                seeded = bool(run190._seed_note_state(page.context, page))
                if seeded:
                    page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(900)
            if note_base._looks_logged_out(page):
                continue
            actual = str(page.url or "")
            if _draft_id_from_edit_url(actual) != target:
                continue
            return actual
        except Exception:
            continue
    raise ReadyDraftRegenerationError(
        "stored note draft id did not resolve to one accessible existing edit route"
    )


def draft_route_preflight(destination: dict[str, str]) -> str:
    """Read-only browser proof before any provider or source write."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ReadyDraftRegenerationError(
            "Playwright is required for exact existing-draft preflight"
        ) from exc
    run190.install()
    profile = run190._profile_dir()
    with sync_playwright() as playwright:
        context = run190._launch_persistent_context(playwright)
        try:
            page = context.new_page()
            route = _open_exact_existing_draft(
                page, profile, destination["note_draft_id"]
            )
            if _draft_id_from_edit_url(route) != destination["note_draft_id"]:
                raise ReadyDraftRegenerationError("exact note draft route proof failed")
            return route
        finally:
            context.close()


def _cover_identity(page: Any) -> str:
    existing = official_image._find_existing_cover(page)
    if existing is None:
        return ""
    cover, _ = existing
    try:
        src = str(cover.evaluate("el => el.currentSrc || el.src || ''") or "")
    except Exception as exc:
        raise ReadyDraftRegenerationError(
            "existing cover media identity could not be read"
        ) from exc
    return hashlib.sha256(src.encode("utf-8")).hexdigest() if src else ""


def _cover_changed(page: Any, old_identity: str) -> bool:
    try:
        current = _cover_identity(page)
    except ReadyDraftRegenerationError:
        return False
    return bool(current and current != str(old_identity or ""))


def apply_current_article_to_existing_draft(
    sync_id: str, *, expected_route: str
) -> dict[str, Any]:
    """Replace title/body/eyecatch on the stored private draft identity only."""
    article = _current_note_article(_normalize_sync_id(sync_id))
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ReadyDraftRegenerationError(
            "Playwright is required for existing-draft replacement"
        ) from exc

    run190.install()
    run417.install(note_base)
    official_image.install()
    profile = run190._profile_dir()
    note_draft_id = str(article["note_draft_id"])

    with sync_playwright() as playwright:
        context = run190._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            route = _open_exact_existing_draft(page, profile, note_draft_id)
            if not _same_exact_draft_route(expected_route, route, note_draft_id):
                raise ReadyDraftRegenerationError(
                    "existing draft identity changed after regeneration"
                )
            page.goto(route, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(900)
            if not _same_exact_draft_route(route, str(page.url or ""), note_draft_id):
                raise ReadyDraftRegenerationError(
                    "existing draft route changed before mutation"
                )

            title = str(article["title"])
            manuscript = str(article["manuscript"])
            old_cover_identity = _cover_identity(page)

            title_field = note_base._set_title(page, title)
            body = note_base._find_body(page, title_field)
            note_base._paste_manuscript(page, body, manuscript)
            body = note_base._find_body(page, title_field)
            note_base._verify_body_content(body, manuscript)
            saved = note_base._save_draft_and_verify(
                page, title, manuscript, image_required=bool(old_cover_identity)
            )
            if not _same_exact_draft_route(route, saved, note_draft_id):
                raise ReadyDraftRegenerationError(
                    "title/body save escaped the existing draft identity"
                )

            official_image._upload_header_image(
                page,
                Path(article["eyecatch_path"]),
                media_changed=lambda: _cover_changed(page, old_cover_identity),
            )
            if not _cover_changed(page, old_cover_identity):
                raise ReadyDraftRegenerationError(
                    "regenerated eyecatch did not replace the previous cover media"
                )
            saved = note_base._save_draft_and_verify(
                page, title, manuscript, image_required=True
            )
            if not _same_exact_draft_route(route, saved, note_draft_id):
                raise ReadyDraftRegenerationError(
                    "eyecatch save escaped the existing draft identity"
                )
            metrics = eyecatch.collect_eyecatch_metrics(
                page, title_locator=note_base._find_title(page)
            )
            if not eyecatch.eyecatch_persistence_confirmed(metrics):
                raise ReadyDraftRegenerationError(
                    "regenerated eyecatch persistence proof failed"
                )

            return {
                "success": True,
                "status": "existing_ready_draft_regenerated",
                "sync_id": sync_id,
                "same_edit_route": True,
                "title_verified": True,
                "body_verified": True,
                "eyecatch_verified": True,
                "persisted_after_reload": True,
                "new_draft_created": False,
                "public_release": False,
                "editor_route_hash": hashlib.sha256(
                    note_draft_id.encode("utf-8")
                ).hexdigest()[:12],
            }
        finally:
            context.close()


def run_full(sync_id: str, *, resume_persisted: bool = False) -> dict[str, Any]:
    """Regenerate or resume persisted Ready, then overwrite the same private draft."""
    sync_id = _normalize_sync_id(sync_id)
    if not _approval_is_valid(sync_id):
        raise ReadyDraftRegenerationError("explicit exact regeneration approval is missing")

    destination = destination_preflight(sync_id)
    expected_route = draft_route_preflight(destination)

    if resume_persisted:
        import pipeline

        resume_persisted_ready_draft(pipeline, sync_id)
    else:
        article_revalidation.run_article_revalidation = (
            lambda pipeline, limit=None: run_ready_regeneration(pipeline, sync_id)
        )
        os.environ["AIIF_ONE_SHOT_MODE"] = "article_validation"
        import production_pipeline

        production_pipeline.main()

    result = apply_current_article_to_existing_draft(
        sync_id, expected_route=expected_route
    )
    if result.get("status") != "existing_ready_draft_regenerated":
        raise ReadyDraftRegenerationError("existing private draft replacement did not complete")
    return result


def _safe_stdout(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": bool(result.get("success", True)),
        "status": result.get("status", "ready"),
        "same_edit_route": result.get("same_edit_route"),
        "title_verified": result.get("title_verified"),
        "body_verified": result.get("body_verified"),
        "eyecatch_verified": result.get("eyecatch_verified"),
        "new_draft_created": result.get("new_draft_created", False),
        "public_release": result.get("public_release", False),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-id", required=True)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--resume-persisted", action="store_true")
    args = parser.parse_args()
    sync_id = _normalize_sync_id(args.sync_id)
    if args.confirm != CONFIRM_TOKEN:
        raise SystemExit("ready draft regeneration refused: invalid confirmation")
    os.environ[CONFIRM_ENV] = args.confirm
    os.environ[TARGET_ENV] = sync_id

    if args.prepare_only:
        destination_preflight(sync_id)
        print(json.dumps({
            "success": True,
            "status": "exact_existing_draft_ready",
            "draft_bound": True,
            "new_draft_created": False,
            "public_release": False,
        }, ensure_ascii=False))
        return

    result = run_full(sync_id, resume_persisted=args.resume_persisted)
    print(json.dumps(_safe_stdout(result), ensure_ascii=False))


if __name__ == "__main__":
    main()
