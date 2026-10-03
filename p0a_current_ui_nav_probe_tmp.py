#!/usr/bin/env python3
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from urllib.parse import urlparse

import note_draft_automation as note_base
import note_publication_reconcile as lifecycle
import note_ready_sync as ready_sync
import run190_note_persistent_cloud as cloud
import run222_note_presentation_integrity as run222
import run291_note_private_draft_audit as audit291
import run292_note_rendered_body_audit as audit292
import run295_note_private_draft_audit as audit295

TARGET = re.sub(r"[^0-9a-fA-F]", "", os.environ.get("TARGET_SYNC_ID", "")).lower()
DANGEROUS = ("公開", "投稿", "保存", "削除", "移動", "複製", "ログアウト")


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def note_domain(url: str) -> bool:
    try:
        p = urlparse(str(url or ""))
    except Exception:
        return False
    return p.scheme == "https" and (p.hostname or "").lower() in {"note.com", "www.note.com", "editor.note.com"}


def safe_nav_href(raw: str) -> str:
    value = str(raw or "").strip()
    if not value or not note_domain(value):
        return ""
    p = urlparse(value)
    path = p.path or "/"
    if "/publish" in path or "/delete" in path or path.rstrip("/").endswith("/new"):
        return ""
    return value


def load_target() -> tuple[dict, str, str, str]:
    if len(TARGET) != 32:
        raise RuntimeError("target_sync_id_invalid")
    rows = ready_sync._query_db(
        ready_sync.DEST_DATA_SOURCE_ID,
        ready_sync.DEST_DATABASE_ID,
        payload={"filter": {"property": "同期ID", "rich_text": {"equals": TARGET}}},
    )
    exact = [p for p in rows if ready_sync._normalize_page_id(ready_sync._text((p.get("properties") or {}).get("同期ID"))) == TARGET]
    if len(exact) != 1:
        raise RuntimeError("destination_row_not_unique")
    destination = exact[0]
    props = destination.get("properties") or {}
    title = ready_sync._text(props.get("記事タイトル")).strip()
    if not title:
        raise RuntimeError("destination_title_missing")
    if ready_sync._select(props.get("品質状態")) != "Ready" or ready_sync._select(props.get("投稿状態")) != "投稿準備中":
        raise RuntimeError("destination_state_invalid")
    if ready_sync._url(props.get("note公開URL")) or str((((props.get("投稿日") or {}).get("date") or {}).get("start")) or "").strip():
        raise RuntimeError("public_evidence_present")
    if ready_sync._text(props.get(lifecycle.DRAFT_ID_PROPERTY)).strip():
        raise RuntimeError("stable_identity_already_present")

    source = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{TARGET}")
    if source.status_code != 200:
        raise RuntimeError("source_page_read_failed")
    state = ready_sync._source_state(source.json())
    if not state or state.get("sync_id") != TARGET or str(state.get("title") or "").strip() != title:
        raise RuntimeError("source_contract_invalid")
    manuscript = ready_sync._source_current_ready_manuscript(TARGET)
    if not manuscript:
        raise RuntimeError("current_contract_manuscript_missing")
    presented = run222.prepare_note_editor_manuscript(manuscript, title)
    expected_visible = audit292._rendered_visible_text(presented)
    return destination, title, presented, expected_visible


def ensure_auth(context, page, url: str, seeded: bool) -> bool:
    if not note_base._looks_logged_out(page):
        return seeded
    if not seeded:
        seeded = bool(cloud._seed_note_state(context, page))
    if seeded:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1200)
    if note_base._looks_logged_out(page):
        raise RuntimeError("note_auth_inactive")
    return seeded


def exact_visible(page, label: str):
    locator = page.locator('a,button,[role="link"],[role="button"],[role="menuitem"]')
    matches = []
    try:
        count = min(locator.count(), 160)
    except Exception:
        count = 0
    expected = norm(label)
    for i in range(count):
        item = locator.nth(i)
        try:
            if not item.is_visible(timeout=100):
                continue
            text = norm(item.inner_text(timeout=300))
            if text == expected:
                matches.append(item)
        except Exception:
            continue
    return matches


def open_profile_menu_until_my_articles(page) -> tuple[int, int]:
    direct = exact_visible(page, "自分の記事")
    if direct:
        return 0, len(direct)
    viewport = page.viewport_size or {"width": 1440, "height": 1100}
    controls = page.locator('header button,header [role="button"],nav button,nav [role="button"]')
    ranked = []
    try:
        count = min(controls.count(), 60)
    except Exception:
        count = 0
    for i in range(count):
        item = controls.nth(i)
        try:
            if not item.is_visible(timeout=100):
                continue
            box = item.bounding_box() or {}
            x, y = float(box.get("x", -1)), float(box.get("y", -1))
            if y < 0 or y > 190 or x < float(viewport["width"]) * 0.50:
                continue
            text = norm(item.inner_text(timeout=250))
            if any(word in text for word in DANGEROUS):
                continue
            has_img = item.locator("img").count() > 0
            aria_popup = str(item.get_attribute("aria-haspopup") or "")
            ranked.append((0 if aria_popup else 1, 0 if has_img else 1, -x, i, item))
        except Exception:
            continue
    ranked.sort(key=lambda row: row[:4])
    tried = 0
    for *_meta, item in ranked[:8]:
        try:
            item.click(timeout=1500)
            tried += 1
            page.wait_for_timeout(350)
            found = exact_visible(page, "自分の記事")
            if found:
                return tried, len(found)
        except Exception:
            continue
    return tried, 0


def navigate_control(page, item) -> None:
    try:
        href = safe_nav_href(str(item.get_attribute("href") or ""))
    except Exception:
        href = ""
    if href:
        page.goto(href, wait_until="domcontentloaded", timeout=60000)
    else:
        item.click(timeout=2500)
    page.wait_for_timeout(1600)


def draft_card_hrefs(page) -> tuple[int, list[str]]:
    data = page.evaluate(
        """() => {
          const n = s => String(s || '').replace(/\u3000/g, ' ').replace(/\s+/g, ' ').trim();
          const cards = Array.from(document.querySelectorAll('article,li,[role="listitem"]'))
            .filter(el => n(el.innerText || '').includes('下書き'));
          const hrefs = [];
          for (const card of cards) {
            for (const a of Array.from(card.querySelectorAll('a[href]'))) hrefs.push(a.href || '');
          }
          return {cardCount: cards.length, hrefs};
        }"""
    ) or {}
    hrefs = []
    seen = set()
    for raw in data.get("hrefs") or []:
        value = safe_nav_href(str(raw or ""))
        if value and value not in seen:
            seen.add(value)
            hrefs.append(value)
    return int(data.get("cardCount") or 0), hrefs


def body_signature(page, title: str, expected_visible: str) -> dict | None:
    if not audit291._is_note_edit_url(str(page.url or "")):
        return None
    try:
        persisted_title = audit291._title_value(page)
        title_field = note_base._find_title(page)
        body = note_base._find_body(page, title_field)
        actual = audit291._normalized_visible(str(body.inner_text(timeout=5000) or ""))
    except Exception:
        return None
    if not actual:
        return None
    similarity = difflib.SequenceMatcher(None, expected_visible, actual, autojunk=False).ratio()
    length_ratio = len(actual) / max(1, len(expected_visible))
    boundary = min(64, len(expected_visible))
    prefix = bool(boundary and expected_visible[:boundary] in actual)
    suffix = bool(boundary and expected_visible[-boundary:] in actual)
    title_match = persisted_title.strip() == title.strip()
    strong = 0.68 <= length_ratio <= 1.40 and similarity >= 0.70 and (title_match or prefix or suffix)
    return {
        "draft_id": lifecycle.draft_identity_from_url(str(page.url or "")),
        "title_match": title_match,
        "similarity": round(similarity, 4),
        "length_ratio": round(length_ratio, 4),
        "prefix": prefix,
        "suffix": suffix,
        "strong": strong,
    }


def audit_identity(destination: dict, title: str, draft_id: str) -> dict:
    original = audit291._destination_row
    def bound(sync_id: str):
        if audit291._normalize_sync_id(sync_id) != TARGET:
            raise audit291.PrivateDraftAuditError("target_sync_id_drift")
        return {"destination_page_id": str(destination.get("id") or ""), "sync_id": TARGET, "title": title, "draft_id": draft_id}
    audit291._destination_row = bound
    try:
        try:
            return audit295.run(confirm=audit291.CONFIRM_TOKEN, sync_id=TARGET, prepare_only=False)
        except audit295.Run295EyecatchProofError as exc:
            return audit295._safe_failure_result(TARGET, exc.code, exc.safe_metrics)
        except audit292.Run292AuditDiagnosticError as exc:
            return audit295._safe_failure_result(TARGET, exc.code, exc.safe_metrics)
        except audit291.PrivateDraftAuditError as exc:
            return audit295._safe_failure_result(TARGET, audit292._safe_non_body_guard_code(exc), getattr(exc, "safe_metrics", None))
    finally:
        audit291._destination_row = original


def main() -> int:
    destination, title, manuscript, expected_visible = load_target()
    metrics = {
        "read_only": True, "zero_gemini_calls": True, "draft_mutation": False, "public_release": False,
        "profile_controls_tried": 0, "my_articles_entry_count": 0, "draft_filter_count": 0,
        "target_exact_count": 0, "draft_card_count": 0, "draft_card_href_count": 0,
        "editor_candidates_checked": 0, "strong_signature_match_count": 0, "max_similarity_ratio": 0.0,
    }
    selected = ""
    proof_mode = ""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        seeded = False
        try:
            home = "https://note.com/"
            page.goto(home, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1200)
            seeded = ensure_auth(context, page, home, seeded)

            tried, found_count = open_profile_menu_until_my_articles(page)
            metrics["profile_controls_tried"] = tried
            metrics["my_articles_entry_count"] = found_count
            entries = exact_visible(page, "自分の記事")
            if not entries:
                metrics["status"] = "my_articles_entry_not_found"
                print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))
                return 2
            navigate_control(page, entries[0])
            if not note_domain(str(page.url or "")):
                raise RuntimeError("my_articles_left_note_domain")

            target_controls = exact_visible(page, title)
            draft_filters = exact_visible(page, "下書き")
            metrics["draft_filter_count"] = len(draft_filters)
            if not target_controls and draft_filters:
                navigate_control(page, draft_filters[0])
                target_controls = exact_visible(page, title)

            metrics["target_exact_count"] = len(target_controls)
            if target_controls:
                navigate_control(page, target_controls[0])
                if not audit291._is_note_edit_url(str(page.url or "")):
                    edit_controls = exact_visible(page, "編集")
                    if edit_controls:
                        navigate_control(page, edit_controls[0])
                if audit291._is_note_edit_url(str(page.url or "")):
                    selected = lifecycle.draft_identity_from_url(str(page.url or ""))
                    proof_mode = "official_ui_exact_title"

            if not selected:
                card_count, card_hrefs = draft_card_hrefs(page)
                metrics["draft_card_count"] = card_count
                metrics["draft_card_href_count"] = len(card_hrefs)
                strong = {}
                for href in card_hrefs[:120]:
                    try:
                        page.goto(href, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(800)
                        seeded = ensure_auth(context, page, href, seeded)
                        if not audit291._is_note_edit_url(str(page.url or "")):
                            edits = exact_visible(page, "編集")
                            if edits:
                                navigate_control(page, edits[0])
                        sig = body_signature(page, title, expected_visible)
                        if not sig:
                            continue
                        metrics["editor_candidates_checked"] += 1
                        metrics["max_similarity_ratio"] = max(metrics["max_similarity_ratio"], float(sig["similarity"]))
                        if sig["strong"]:
                            strong[sig["draft_id"]] = sig
                    except Exception:
                        continue
                metrics["strong_signature_match_count"] = len(strong)
                if len(strong) == 1:
                    selected = next(iter(strong))
                    proof_mode = "official_ui_unique_body_signature"
        finally:
            context.close()

    if not selected:
        metrics["status"] = "identity_not_found_via_current_ui"
        print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))
        return 2

    metrics["identity_proof_mode"] = proof_mode
    metrics["stable_identity_hash"] = hashlib.sha256(selected.encode("utf-8")).hexdigest()[:12]
    result = audit_identity(destination, title, selected)
    metrics["audit_status"] = result.get("status")
    metrics["audit_diagnostic_code"] = result.get("diagnostic_code", "")
    for key in (
        "canonical_match", "mismatch_category", "mismatch_path", "dom_diagnostic_category",
        "unknown_dom_tags", "unknown_dom_tag_counts", "dom_tag_counts", "expected_canonical_node_count",
        "actual_canonical_node_count", "title_match", "eyecatch_present", "eyecatch_proof_mode",
        "visible_length_ratio", "prefix_match", "suffix_match", "exact_visible_match",
    ):
        if key in result:
            metrics[f"audit_{key}"] = result[key]
    print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") == "audit_passed" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "status": "current_ui_probe_failed_safe",
            "diagnostic_code": type(exc).__name__,
            "read_only": True,
            "zero_gemini_calls": True,
            "draft_mutation": False,
            "public_release": False,
        }, ensure_ascii=False, sort_keys=True))
        raise SystemExit(2)
