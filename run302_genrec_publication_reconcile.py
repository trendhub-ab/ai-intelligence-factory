#!/usr/bin/env python3
"""Run302: reconcile the manually published Netflix GenRec note back into Note Ready.

Safety boundary:
- exact fixed GenRec sync_id and exact Ready / 投稿準備中 Note Ready row;
- never creates, edits, saves, publishes, republishes, or withdraws a note;
- discovers the one existing editor route read-only and derives the public note ID from it;
- audits the live public note page before any Notion posting-state mutation;
- updates only 投稿状態, note公開URL, 投稿日, 最終同期日 after the live audit passes;
- rejects duplicate use of the same public URL by another Note Ready row;
- zero Gemini/model calls and Daily remains paused.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import note_draft_automation as note_base
import note_ready_sync as ready_sync
import run190_note_persistent_cloud as cloud
import run291_note_private_draft_audit as audit_base
import run296_editorial_format_v2 as r296
import run298_genrec_inplace_refresh as r298
import run301_genrec_summary_restore as r301

TARGET_SYNC_ID = r298.TARGET_SYNC_ID
AUTHOR_SLUG = "trendhub_biz"
TOKYO = ZoneInfo("Asia/Tokyo")
PUBLISHED_STATUS = "投稿済み"
PREPARING_STATUS = "投稿準備中"
READY_STATUS = "Ready"


class Run302Error(RuntimeError):
    pass


def _prop_date(prop: dict | None) -> str:
    return str((((prop or {}).get("date") or {}).get("start")) or "").strip()


def _destination_snapshot() -> dict[str, Any]:
    pages = ready_sync._query_db(
        ready_sync.DEST_DATA_SOURCE_ID,
        ready_sync.DEST_DATABASE_ID,
        payload={"filter": {"property": "同期ID", "rich_text": {"equals": TARGET_SYNC_ID}}},
    )
    exact = []
    for page in pages:
        props = page.get("properties") or {}
        sid = audit_base._normalize_sync_id(ready_sync._text(props.get("同期ID")))
        if sid == TARGET_SYNC_ID:
            exact.append(page)
    if len(exact) != 1:
        raise Run302Error(f"destination_row_not_unique:{len(exact)}")
    page = exact[0]
    props = page.get("properties") or {}
    title = ready_sync._text(props.get("記事タイトル"))
    quality = ready_sync._select(props.get("品質状態"))
    posting = ready_sync._select(props.get("投稿状態"))
    public_url = ready_sync._url(props.get("note公開URL"))
    posted_date = _prop_date(props.get("投稿日"))
    if title.strip() != r296.GENREC_SOURCE_TITLE:
        raise Run302Error("destination_title_drift")
    if quality != READY_STATUS:
        raise Run302Error("destination_not_ready")
    if posting not in {PREPARING_STATUS, PUBLISHED_STATUS}:
        raise Run302Error(f"destination_posting_state_invalid:{posting}")
    if posting == PREPARING_STATUS and (public_url or posted_date):
        raise Run302Error("preparing_row_has_partial_public_evidence")
    if posting == PUBLISHED_STATUS and (not public_url or not posted_date):
        raise Run302Error("published_row_missing_public_evidence")
    return {
        "page_id": str(page.get("id") or ""),
        "title": title.strip(),
        "quality": quality,
        "posting": posting,
        "public_url": public_url,
        "posted_date": posted_date,
    }


def _note_id_from_edit_route(route: str) -> str:
    parsed = urlparse(str(route or ""))
    match = re.fullmatch(r"/notes/([^/?#]+)/edit/?", parsed.path or "", flags=re.I)
    if not match:
        raise Run302Error("invalid_editor_route")
    note_id = match.group(1).strip()
    if not re.fullmatch(r"n[0-9A-Za-z]+", note_id):
        raise Run302Error("invalid_note_id")
    return note_id


def _candidate_public_urls(page: Any, note_id: str) -> list[str]:
    raw: list[str] = []
    try:
        raw.extend(
            str(value or "")
            for value in page.locator("a[href]").evaluate_all(
                "els => els.map(el => el.href || el.getAttribute('href') || '')"
            )
        )
    except Exception:
        pass
    for selector in ('link[rel="canonical"]', 'meta[property="og:url"]'):
        try:
            loc = page.locator(selector).first
            if loc.count():
                attr = "href" if selector.startswith("link") else "content"
                raw.append(str(loc.get_attribute(attr) or ""))
        except Exception:
            pass

    # Account slug is fixed for this publication surface, but the constructed URL is only a
    # candidate: the live page must pass exact note-id/title/body auditing before it is accepted.
    raw.append(f"https://note.com/{AUTHOR_SLUG}/n/{note_id}")

    result: list[str] = []
    seen: set[str] = set()
    for value in raw:
        absolute = urljoin("https://note.com/", value.strip())
        try:
            parsed = urlparse(absolute)
        except Exception:
            continue
        if parsed.scheme != "https" or (parsed.hostname or "").lower() != "note.com":
            continue
        path = (parsed.path or "").rstrip("/")
        if not re.fullmatch(rf"/[^/?#]+/n/{re.escape(note_id)}", path, flags=re.I):
            continue
        clean = f"https://note.com{path}"
        if clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _normalized(value: str) -> str:
    return audit_base._normalized_visible(str(value or ""))


def _public_body_metrics(text: str, title: str) -> dict[str, Any]:
    actual = _normalized(text)
    summary = _normalized(r301.EXPECTED_SUMMARY)
    if not actual:
        raise Run302Error("public_page_body_empty")
    summary_count = actual.count(summary)
    intro_index = actual.find(_normalized(r296.INTRO_HEADING_NEW))
    summary_index = actual.find(summary)
    why_index = actual.find(_normalized("なぜ重要？"))
    conclusion_index = actual.find(_normalized("結論は？"))
    source_index = actual.find(_normalized("Sources / Evidence"))
    cta_index = actual.find(_normalized(r296.CTA_HEADING))
    if summary_count != 1:
        raise Run302Error(f"public_summary_count_invalid:{summary_count}")
    if not (0 <= intro_index < summary_index < why_index < conclusion_index):
        raise Run302Error("public_intro_summary_order_invalid")
    if _normalized(r296.REMOVE_SUMMARY_LABEL) in actual:
        raise Run302Error("public_removed_label_reappeared")
    if source_index < 0 or cta_index < 0 or source_index >= cta_index:
        raise Run302Error("public_sources_cta_order_invalid")
    if _normalized(r296.CTA_BODY) not in actual or _normalized(r296.CTA_LINK_LABEL) not in actual:
        raise Run302Error("public_cta_surface_invalid")
    title_count = actual.count(_normalized(title))
    return {
        "summary_count": summary_count,
        "summary_order_valid": True,
        "what_label_absent": True,
        "sources_before_cta": True,
        "cta_present": True,
        "public_visible_chars": len(actual),
        "public_title_visible_count": title_count,
    }


def _live_page_title_ok(page: Any, expected_title: str) -> bool:
    expected = _normalized(expected_title)
    values: list[str] = []
    for selector, attr in (
        ('meta[property="og:title"]', "content"),
        ('meta[name="twitter:title"]', "content"),
    ):
        try:
            loc = page.locator(selector).first
            if loc.count():
                values.append(str(loc.get_attribute(attr) or ""))
        except Exception:
            pass
    try:
        values.extend(str(x or "") for x in page.locator("h1").all_inner_texts())
    except Exception:
        pass
    return any(expected and expected in _normalized(value) for value in values)


def _public_eyecatch_metrics(page: Any) -> dict[str, Any]:
    try:
        large = page.evaluate(
            """() => Array.from(document.querySelectorAll('img')).filter(img => {
                const r = img.getBoundingClientRect();
                const s = getComputedStyle(img);
                const nw = Number(img.naturalWidth || 0), nh = Number(img.naturalHeight || 0);
                const ratio = nh > 0 ? nw / nh : 0;
                return s.display !== 'none' && s.visibility !== 'hidden' && r.width >= 420 && r.height >= 180 &&
                       nw >= 600 && nh >= 250 && ratio >= 1.6 && ratio <= 2.2;
            }).length"""
        )
    except Exception:
        large = 0
    try:
        og_image = str(page.locator('meta[property="og:image"]').first.get_attribute("content") or "")
    except Exception:
        og_image = ""
    if int(large or 0) < 1 or not og_image.startswith("https://"):
        raise Run302Error("public_eyecatch_not_confirmed")
    return {"public_large_eyecatch_count": int(large), "public_og_image_present": True}


def _audit_public_candidate(page: Any, url: str, note_id: str, title: str) -> dict[str, Any]:
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1800)
    final = str(page.url or "")
    parsed = urlparse(final)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != "note.com":
        raise Run302Error("public_candidate_redirected_off_note")
    if not re.fullmatch(rf"/[^/?#]+/n/{re.escape(note_id)}/?", parsed.path or "", flags=re.I):
        raise Run302Error("public_candidate_note_id_mismatch")
    if not _live_page_title_ok(page, title):
        raise Run302Error("public_title_mismatch")
    try:
        visible = str(page.locator("body").inner_text(timeout=10000) or "")
    except Exception as exc:
        raise Run302Error("public_body_read_failed") from exc
    metrics = _public_body_metrics(visible, title)
    metrics.update(_public_eyecatch_metrics(page))
    metrics["public_url"] = f"https://note.com{(parsed.path or '').rstrip('/')}"
    metrics["public_note_id_match"] = True
    metrics["public_title_match"] = True
    return metrics


def _discover_and_audit_live_publication(title: str) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise Run302Error("playwright_missing") from exc
    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            route, matched_rank, candidate_count = r298._find_one_existing_route(context, page, title)
            note_id = _note_id_from_edit_route(route)
            page.goto(route, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1000)
            if note_base._looks_logged_out(page):
                if not cloud._seed_note_state(context, page):
                    raise Run302Error("note_auth_inactive")
                page.goto(route, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1000)
            if r298._safe_title(page) != title:
                raise Run302Error("editor_title_mismatch")
            candidates = _candidate_public_urls(page, note_id)
            if not candidates:
                raise Run302Error("no_public_url_candidates")
            passed: list[dict[str, Any]] = []
            for candidate in candidates:
                try:
                    passed.append(_audit_public_candidate(page, candidate, note_id, title))
                except Run302Error:
                    continue
            unique = {item["public_url"]: item for item in passed}
            if len(unique) != 1:
                raise Run302Error(f"public_url_not_unique:{len(unique)}")
            result = next(iter(unique.values()))
            result["history_candidate_count"] = candidate_count
            result["matched_history_rank"] = matched_rank
            result["public_candidate_count"] = len(candidates)
            return result
        finally:
            context.close()


def _require_no_duplicate_public_url(public_url: str, target_page_id: str) -> None:
    pages = ready_sync._query_db(
        ready_sync.DEST_DATA_SOURCE_ID,
        ready_sync.DEST_DATABASE_ID,
        payload={"filter": {"property": "note公開URL", "url": {"equals": public_url}}},
    )
    other = [page for page in pages if str(page.get("id") or "") != target_page_id]
    if other:
        raise Run302Error(f"public_url_already_bound_elsewhere:{len(other)}")


def _patch_published(snapshot: dict[str, Any], public_url: str, posted_date: str) -> None:
    props = {
        "投稿状態": ready_sync._sel(PUBLISHED_STATUS),
        "note公開URL": {"url": public_url},
        "投稿日": {"date": {"start": posted_date}},
        "最終同期日": {"date": {"start": posted_date}},
    }
    res = ready_sync._request(
        "PATCH",
        f"https://api.notion.com/v1/pages/{snapshot['page_id']}",
        json={"properties": props},
    )
    if res.status_code != 200:
        raise Run302Error(f"notion_publish_reconcile_http_{res.status_code}")


def _verify_published(public_url: str, posted_date: str) -> dict[str, Any]:
    snap = _destination_snapshot()
    if snap["posting"] != PUBLISHED_STATUS:
        raise Run302Error("posting_status_not_published_after_patch")
    if snap["public_url"] != public_url:
        raise Run302Error("public_url_readback_mismatch")
    if snap["posted_date"] != posted_date:
        raise Run302Error("posted_date_readback_mismatch")
    return snap


def reconcile_publication(*, prepare_only: bool = False) -> dict[str, Any]:
    snapshot = _destination_snapshot()
    if snapshot["posting"] == PUBLISHED_STATUS:
        return {
            "status": "already_reconciled",
            "should_start_vm": False,
            "sync_id": TARGET_SYNC_ID,
            "posting_state_published": True,
            "public_url_present": True,
            "posted_date_present": True,
            "duplicate_draft_created": False,
            "public_release_performed": False,
            "daily_restarted": False,
            "zero_gemini_calls": True,
        }
    if prepare_only:
        return {
            "status": "ready_for_public_audit",
            "should_start_vm": True,
            "sync_id": TARGET_SYNC_ID,
            "posting_state_preparing": True,
            "public_evidence_blank_before_reconcile": True,
            "zero_gemini_calls": True,
        }

    live = _discover_and_audit_live_publication(snapshot["title"])
    public_url = str(live["public_url"])
    _require_no_duplicate_public_url(public_url, snapshot["page_id"])
    posted_date = datetime.now(TOKYO).date().isoformat()
    _patch_published(snapshot, public_url, posted_date)
    final = _verify_published(public_url, posted_date)
    result = {
        "status": "reconciled",
        "sync_id": TARGET_SYNC_ID,
        "posting_state_published": final["posting"] == PUBLISHED_STATUS,
        "public_url_present": bool(final["public_url"]),
        "posted_date": final["posted_date"],
        "quality_state_ready": final["quality"] == READY_STATUS,
        "duplicate_public_url": False,
        "duplicate_draft_created": False,
        "public_release_performed": False,
        "daily_restarted": False,
        "zero_gemini_calls": True,
    }
    result.update(live)
    return result


def _write_result(path_value: str, result: dict[str, Any]) -> None:
    if not path_value:
        return
    target = Path(path_value)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    prepare_only = os.environ.get("RUN302_PREPARE_ONLY", "false").lower() in {"1", "true", "yes", "on"}
    result = reconcile_publication(prepare_only=prepare_only)
    _write_result(os.environ.get("RUN302_RESULT_FILE", ""), result)
    print(json.dumps({
        "status": result["status"],
        "should_start_vm": result.get("should_start_vm"),
        "posting_state_published": result.get("posting_state_published"),
        "public_url_present": result.get("public_url_present"),
        "quality_state_ready": result.get("quality_state_ready"),
        "public_release_performed": result.get("public_release_performed", False),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
