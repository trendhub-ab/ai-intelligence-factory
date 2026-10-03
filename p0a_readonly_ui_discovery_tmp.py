#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
from urllib.parse import urljoin, urlparse

import note_draft_automation as note_base
import note_publication_reconcile as lifecycle
import note_ready_sync as ready_sync
import run190_note_persistent_cloud as cloud
import run291_note_private_draft_audit as audit291
import run292_note_rendered_body_audit as audit292
import run295_note_private_draft_audit as audit295

TARGET = re.sub(r"[^0-9a-fA-F]", "", os.environ.get("TARGET_SYNC_ID", "")).lower()


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def safe_note_href(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    value = urljoin("https://note.com/", value)
    parsed = urlparse(value)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in {"note.com", "editor.note.com"}:
        return ""
    path = parsed.path or "/"
    if "/publish" in path or path.endswith("/delete") or "/new" in path:
        return ""
    return value


def title_anchor_hrefs(page, title: str) -> list[str]:
    values = page.evaluate(
        """() => Array.from(document.querySelectorAll('a[href]')).map(a => [String(a.innerText || a.textContent || ''), a.href || ''])"""
    )
    expected = norm(title)
    out: list[str] = []
    for item in values or []:
        if not isinstance(item, list) or len(item) != 2:
            continue
        raw, href = item
        lines = [norm(line) for line in str(raw or "").splitlines() if norm(line)]
        if norm(raw) == expected or expected in lines:
            safe = safe_note_href(str(href or ""))
            if safe:
                out.append(safe)
    return out


def edit_hrefs(page) -> list[str]:
    values = page.evaluate("""() => Array.from(document.querySelectorAll('a[href]')).map(a => a.href || '')""")
    out: list[str] = []
    for raw in values or []:
        href = safe_note_href(str(raw or ""))
        if not href:
            continue
        parsed = urlparse(href)
        if re.fullmatch(r"/notes/[^/?#]+/edit/?", parsed.path or "", flags=re.I):
            out.append(href)
    return out


def destination_contract() -> tuple[dict, str]:
    if len(TARGET) != 32:
        raise RuntimeError("target_sync_id_invalid")
    pages = ready_sync._query_db(
        ready_sync.DEST_DATA_SOURCE_ID,
        ready_sync.DEST_DATABASE_ID,
        payload={"filter": {"property": "同期ID", "rich_text": {"equals": TARGET}}},
    )
    exact = [
        page
        for page in pages
        if ready_sync._normalize_page_id(ready_sync._text((page.get("properties") or {}).get("同期ID"))) == TARGET
    ]
    if len(exact) != 1:
        raise RuntimeError("destination_row_not_unique")
    destination = exact[0]
    props = destination.get("properties") or {}
    title = ready_sync._text(props.get("記事タイトル")).strip()
    if not title:
        raise RuntimeError("destination_title_missing")
    if ready_sync._select(props.get("品質状態")) != "Ready" or ready_sync._select(props.get("投稿状態")) != "投稿準備中":
        raise RuntimeError("destination_state_invalid")
    public_url = ready_sync._url(props.get("note公開URL"))
    posted_date = str((((props.get("投稿日") or {}).get("date") or {}).get("start")) or "").strip()
    if public_url or posted_date:
        raise RuntimeError("public_evidence_present")
    if ready_sync._text(props.get(lifecycle.DRAFT_ID_PROPERTY)).strip():
        raise RuntimeError("stable_identity_already_present")
    return destination, title


def discover_identity(title: str) -> tuple[str, dict[str, int]]:
    from playwright.sync_api import sync_playwright

    discovered_ids: set[str] = set()
    pages_checked = 0
    title_matches = 0
    candidate_routes_checked = 0
    seeded = False

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            list_urls = [f"https://note.com/notes?page={n}&status=draft" for n in range(1, 11)]
            list_urls += [f"https://note.com/notes?page={n}&kind=draft" for n in range(1, 11)]
            seen_routes: set[str] = set()
            for list_url in list_urls:
                page.goto(list_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1000)
                if note_base._looks_logged_out(page) and not seeded:
                    seeded = bool(cloud._seed_note_state(context, page))
                    if seeded:
                        page.goto(list_url, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(1000)
                if note_base._looks_logged_out(page):
                    raise RuntimeError("note_auth_inactive")
                current = urlparse(str(page.url or ""))
                if (current.hostname or "").lower() not in {"note.com", "editor.note.com"}:
                    raise RuntimeError("draft_list_left_note_domain")
                route_key = f"{current.path}?{current.query}"
                if route_key in seen_routes:
                    continue
                seen_routes.add(route_key)
                pages_checked += 1

                hrefs = title_anchor_hrefs(page, title)
                title_matches += len(hrefs)
                for href in hrefs:
                    candidate_routes_checked += 1
                    parsed = urlparse(href)
                    if re.fullmatch(r"/notes/[^/?#]+/edit/?", parsed.path or "", flags=re.I):
                        discovered_ids.add(lifecycle.draft_identity_from_url(href))
                        continue
                    page.goto(href, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(1000)
                    if note_base._looks_logged_out(page):
                        continue
                    body_text = str(page.locator("body").inner_text(timeout=5000) or "")
                    normalized_body = norm(body_text)
                    if norm(title) not in normalized_body:
                        continue
                    for edit_url in edit_hrefs(page):
                        discovered_ids.add(lifecycle.draft_identity_from_url(edit_url))

                if len(discovered_ids) == 1:
                    break
                if len(discovered_ids) > 1:
                    raise RuntimeError("stable_identity_not_unique")
        finally:
            context.close()

    metrics = {
        "list_pages_checked": pages_checked,
        "title_link_match_count": title_matches,
        "candidate_routes_checked": candidate_routes_checked,
        "stable_identity_match_count": len(discovered_ids),
    }
    if len(discovered_ids) != 1:
        raise RuntimeError("identity_not_found:" + json.dumps(metrics, sort_keys=True))
    return next(iter(discovered_ids)), metrics


def audit_with_identity(destination: dict, title: str, draft_id: str) -> dict:
    original_destination = audit291._destination_row

    def bound_destination(sync_id: str):
        sid = audit291._normalize_sync_id(sync_id)
        if sid != TARGET:
            raise audit291.PrivateDraftAuditError("Run291 expected exactly one destination row for the requested sync_id")
        return {
            "destination_page_id": str(destination.get("id") or ""),
            "sync_id": TARGET,
            "title": title,
            "draft_id": draft_id,
        }

    audit291._destination_row = bound_destination
    try:
        try:
            return audit295.run(confirm=audit291.CONFIRM_TOKEN, sync_id=TARGET, prepare_only=False)
        except audit295.Run295EyecatchProofError as exc:
            return audit295._safe_failure_result(TARGET, exc.code, exc.safe_metrics)
        except audit292.Run292AuditDiagnosticError as exc:
            return audit295._safe_failure_result(TARGET, exc.code, exc.safe_metrics)
        except audit291.PrivateDraftAuditError as exc:
            return audit295._safe_failure_result(
                TARGET,
                audit292._safe_non_body_guard_code(exc),
                getattr(exc, "safe_metrics", None),
            )
    finally:
        audit291._destination_row = original_destination


def safe_result(result: dict, discovery: dict[str, int], draft_id: str) -> dict:
    keys = {
        "success", "status", "diagnostic_code", "zero_gemini_calls", "read_only", "public_release", "draft_mutation",
        "expectation_mode", "title_match", "eyecatch_present", "eyecatch_proof_mode", "body_h1_count", "heading_count",
        "paragraph_count", "list_item_count", "link_count", "blockquote_count", "body_visible_chars", "expected_visible_chars",
        "legacy_expected_visible_chars", "renderer_delta_chars", "renderer_delta_ratio", "visible_length_ratio", "prefix_match",
        "suffix_match", "exact_visible_match", "expected_contained_in_actual", "actual_contained_in_expected",
        "common_prefix_ratio", "common_suffix_ratio", "sources_present", "cta_present", "sources_before_cta",
        "duplicate_title_prefix", "code_fence_marker_count", "canonical_match", "mismatch_category", "mismatch_path",
        "dom_diagnostic_category", "unknown_dom_tags", "unknown_dom_tag_counts", "dom_tag_counts", "snapshot_element_node_count",
        "snapshot_text_node_count", "snapshot_total_node_count", "expected_canonical_node_count", "actual_canonical_node_count",
        "unsupported_expected_node_count", "unsupported_actual_node_count", "contract_version", "normalization_policy_version",
        "expected_node_counts", "actual_node_counts", "title_box", "body_box", "eyecatch_exact_control_count",
        "eyecatch_exact_control_visible_count", "image_labeled_control_count", "image_labeled_control_visible_count",
        "image_add_control_count", "image_add_control_visible_count", "file_input_count", "title_geometry_available",
        "visible_img_count", "large_top_img_count", "large_top_background_count", "visible_picture_count", "max_top_media_width",
        "max_top_media_height", "viewport_width", "viewport_height",
    }
    out = {k: v for k, v in result.items() if k in keys}
    out.update(discovery)
    out["identity_discovery"] = "exact_title_ui_match"
    out["stable_identity_hash"] = hashlib.sha256(draft_id.encode("utf-8")).hexdigest()[:12]
    return out


def main() -> int:
    try:
        destination, title = destination_contract()
        draft_id, discovery = discover_identity(title)
        result = audit_with_identity(destination, title, draft_id)
        print(json.dumps(safe_result(result, discovery, draft_id), ensure_ascii=False, sort_keys=True))
        return 0 if result.get("status") == "audit_passed" else 2
    except Exception as exc:
        message = str(exc)
        metrics = {}
        code = message
        if message.startswith("identity_not_found:"):
            code = "identity_not_found"
            try:
                metrics = json.loads(message.split(":", 1)[1])
            except Exception:
                metrics = {}
        safe = {
            "status": "discovery_failed_safe",
            "diagnostic_code": code,
            "read_only": True,
            "zero_gemini_calls": True,
            "draft_mutation": False,
            "public_release": False,
        }
        safe.update(metrics)
        print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
