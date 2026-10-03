#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
from urllib.parse import urlparse

import note_document_dom as note_dom
import note_draft_automation as note_base
import note_publication_reconcile as lifecycle
import note_ready_sync as ready_sync
import run190_note_persistent_cloud as cloud
import run222_note_presentation_integrity as run222
import run291_note_private_draft_audit as audit291
import run292_note_rendered_body_audit as audit292
import run295_note_private_draft_audit as audit295

TARGET = re.sub(r"[^0-9a-fA-F]", "", os.environ.get("TARGET_SYNC_ID", "")).lower()


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def load_target() -> tuple[dict, str, str]:
    if len(TARGET) != 32:
        raise RuntimeError("target_sync_id_invalid")
    pages = ready_sync._query_db(
        ready_sync.DEST_DATA_SOURCE_ID,
        ready_sync.DEST_DATABASE_ID,
        payload={"filter": {"property": "同期ID", "rich_text": {"equals": TARGET}}},
    )
    exact = [p for p in pages if ready_sync._normalize_page_id(ready_sync._text((p.get("properties") or {}).get("同期ID"))) == TARGET]
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

    response = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{TARGET}")
    if response.status_code != 200:
        raise RuntimeError("source_page_read_failed")
    state = ready_sync._source_state(response.json())
    if state is None or state.get("sync_id") != TARGET:
        raise RuntimeError("source_not_active_ready")
    if str(state.get("title") or "").strip() != title:
        raise RuntimeError("source_destination_title_mismatch")
    manuscript = ready_sync._source_current_ready_manuscript(TARGET)
    if not manuscript:
        raise RuntimeError("current_contract_manuscript_missing")
    presented = run222.prepare_note_editor_manuscript(manuscript, title)
    if len(presented) < 200:
        raise RuntimeError("prepared_presentation_too_short")
    return destination, title, presented


def route_identity(url: str) -> str:
    try:
        return lifecycle.draft_identity_from_url(url)
    except Exception:
        return ""


def collect_edit_routes(page) -> list[str]:
    values = page.evaluate("""() => Array.from(document.querySelectorAll('a[href]')).map(a => a.href || '')""")
    out: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        value = str(raw or "").strip()
        parsed = urlparse(value)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in {"note.com", "editor.note.com"}:
            continue
        if not re.fullmatch(r"/notes/[^/?#]+/edit/?", parsed.path or "", flags=re.I):
            continue
        identity = route_identity(value)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        out.append(value)
    return out


def list_structure(page, target_title: str) -> dict[str, int]:
    data = page.evaluate(
        """(expected) => {
          const txt = String(document.body?.innerText || '').replace(/\u3000/g, ' ').replace(/\s+/g, ' ').trim();
          const anchors = Array.from(document.querySelectorAll('a[href]'));
          const buttons = Array.from(document.querySelectorAll('button'));
          const hrefs = anchors.map(a => String(a.href || ''));
          const count = re => hrefs.filter(h => re.test(h)).length;
          return {
            anchor_count: anchors.length,
            button_count: buttons.length,
            body_chars: txt.length,
            target_visible: txt.includes(expected) ? 1 : 0,
            edit_href_count: count(/^https:\/\/(?:editor\.)?note\.com\/notes\/[^/?#]+\/edit\/?(?:[?#].*)?$/i),
            notes_href_count: count(/^https:\/\/(?:editor\.)?note\.com\/notes(?:\/|\?|$)/i),
            article_href_count: count(/^https:\/\/note\.com\/[^/]+\/n\/[^/?#]+/i),
          };
        }""",
        norm(target_title),
    )
    return {str(k): int(v or 0) for k, v in (data or {}).items()}


def candidate_metrics(page, expected_title: str, manuscript: str) -> dict:
    if note_base._looks_logged_out(page) or not audit291.run187._is_editor_url(str(page.url or "")):
        return {"editor": False}
    try:
        title_field = note_base._find_title(page)
        persisted_title = audit291._title_value(page)
        body = note_base._find_body(page, title_field)
        actual = audit291._normalized_visible(str(body.inner_text(timeout=5000) or ""))
    except Exception:
        return {"editor": True, "readable": False}
    expected = audit292._rendered_visible_text(manuscript)
    diag = audit292._safe_diagnostics(actual, expected, audit291._normalized_visible(note_base._plain_manuscript_text(manuscript)), expected_title)
    canonical_match = False
    canonical_code = ""
    try:
        snap = note_dom.snapshot_note_body(body)
        canon = audit292._canonical_snapshot_metrics(snap, manuscript)
        canonical_match = bool(canon.get("canonical_match"))
        canonical_code = str(canon.get("mismatch_category") or "")
    except audit292.Run292AuditDiagnosticError as exc:
        canonical_code = exc.code
    return {
        "editor": True,
        "readable": True,
        "title_match": persisted_title == expected_title,
        "canonical_match": canonical_match,
        "canonical_code": canonical_code,
        "exact_visible_match": bool(diag.get("exact_visible_match")),
        "prefix_match": bool(diag.get("prefix_match")),
        "suffix_match": bool(diag.get("suffix_match")),
        "visible_length_ratio": float(diag.get("visible_length_ratio") or 0.0),
    }


def full_audit(destination: dict, title: str, draft_id: str) -> dict:
    original = audit291._destination_row
    def bound(sync_id: str):
        if audit291._normalize_sync_id(sync_id) != TARGET:
            raise audit291.PrivateDraftAuditError("Run291 expected exactly one destination row for the requested sync_id")
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
    try:
        destination, title, manuscript = load_target()
        from playwright.sync_api import sync_playwright
        list_pages_checked = 0
        target_visible_pages = 0
        anchor_total = 0
        button_total = 0
        edit_href_observations = 0
        notes_href_total = 0
        article_href_total = 0
        candidates: dict[str, str] = {}
        seeded = False

        with sync_playwright() as playwright:
            context = cloud._launch_persistent_context(playwright)
            page = context.new_page()
            page.set_default_timeout(30000)
            try:
                for mode in ("status", "kind"):
                    for n in range(1, 11):
                        url = f"https://note.com/notes?page={n}&{mode}=draft"
                        page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(900)
                        if note_base._looks_logged_out(page) and not seeded:
                            seeded = bool(cloud._seed_note_state(context, page))
                            if seeded:
                                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                                page.wait_for_timeout(900)
                        if note_base._looks_logged_out(page):
                            raise RuntimeError("note_auth_inactive")
                        stats = list_structure(page, title)
                        list_pages_checked += 1
                        target_visible_pages += stats.get("target_visible", 0)
                        anchor_total += stats.get("anchor_count", 0)
                        button_total += stats.get("button_count", 0)
                        edit_href_observations += stats.get("edit_href_count", 0)
                        notes_href_total += stats.get("notes_href_count", 0)
                        article_href_total += stats.get("article_href_count", 0)
                        for edit_url in collect_edit_routes(page):
                            identity = route_identity(edit_url)
                            if identity:
                                candidates.setdefault(identity, edit_url)

                exact_title_matches: list[str] = []
                canonical_matches: list[str] = []
                exact_visible_matches: list[str] = []
                readable_candidates = 0
                for identity, edit_url in list(candidates.items())[:120]:
                    page.goto(edit_url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(900)
                    metrics = candidate_metrics(page, title, manuscript)
                    if metrics.get("readable"):
                        readable_candidates += 1
                    if metrics.get("title_match"):
                        exact_title_matches.append(identity)
                    if metrics.get("canonical_match"):
                        canonical_matches.append(identity)
                    if metrics.get("exact_visible_match"):
                        exact_visible_matches.append(identity)
            finally:
                context.close()

        safe = {
            "status": "candidate_probe_complete",
            "read_only": True,
            "zero_gemini_calls": True,
            "draft_mutation": False,
            "public_release": False,
            "list_pages_checked": list_pages_checked,
            "target_visible_pages": target_visible_pages,
            "anchor_total": anchor_total,
            "button_total": button_total,
            "edit_href_observations": edit_href_observations,
            "unique_edit_candidates": len(candidates),
            "notes_href_total": notes_href_total,
            "article_href_total": article_href_total,
            "readable_edit_candidates": readable_candidates,
            "exact_title_match_count": len(exact_title_matches),
            "canonical_body_match_count": len(canonical_matches),
            "exact_visible_body_match_count": len(exact_visible_matches),
        }

        selected = ""
        selection_mode = ""
        if len(canonical_matches) == 1:
            selected = canonical_matches[0]
            selection_mode = "canonical_body_unique"
        elif len(exact_visible_matches) == 1:
            selected = exact_visible_matches[0]
            selection_mode = "exact_visible_body_unique"
        elif len(exact_title_matches) == 1:
            selected = exact_title_matches[0]
            selection_mode = "exact_title_unique"

        if selected:
            safe["selection_mode"] = selection_mode
            safe["stable_identity_hash"] = hashlib.sha256(selected.encode("utf-8")).hexdigest()[:12]
            safe["selected_title_match"] = selected in exact_title_matches
            result = full_audit(destination, title, selected)
            for key, value in result.items():
                if key not in {"title", "manuscript", "draft_url", "actual_text", "expected_text", "sync_id"}:
                    safe[f"audit_{key}"] = value
        else:
            safe["selection_mode"] = "none"

        print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
        return 0 if selected and safe.get("audit_status") == "audit_passed" else 2
    except Exception as exc:
        print(json.dumps({
            "status": "candidate_probe_failed_safe",
            "diagnostic_code": type(exc).__name__,
            "read_only": True,
            "zero_gemini_calls": True,
            "draft_mutation": False,
            "public_release": False,
        }, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
