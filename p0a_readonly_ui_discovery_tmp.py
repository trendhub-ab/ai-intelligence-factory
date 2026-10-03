#!/usr/bin/env python3
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from urllib.parse import urljoin, urlparse, urlunparse

import note_draft_automation as note_base
import note_publication_reconcile as lifecycle
import note_ready_sync as ready_sync
import run190_note_persistent_cloud as cloud
import run222_note_presentation_integrity as run222
import run291_note_private_draft_audit as audit291
import run292_note_rendered_body_audit as audit292
import run295_note_private_draft_audit as audit295

TARGET = re.sub(r"[^0-9a-fA-F]", "", os.environ.get("TARGET_SYNC_ID", "")).lower()
_URL_RE = re.compile(r"https?://[^\s\]\)\}\>\"']+")


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


def normalize_external_url(raw: str) -> str:
    try:
        parsed = urlparse(str(raw or "").strip().rstrip(".,;:!?"))
    except Exception:
        return ""
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        return ""
    if host in {"note.com", "www.note.com", "editor.note.com"}:
        return ""
    path = parsed.path or "/"
    return urlunparse((parsed.scheme.lower(), host, path, "", parsed.query, ""))


def expected_external_urls(markdown_text: str) -> set[str]:
    out: set[str] = set()
    for raw in _URL_RE.findall(str(markdown_text or "")):
        value = normalize_external_url(raw)
        if value:
            out.add(value)
    return out


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


def draft_card_hrefs(page) -> list[str]:
    values = page.evaluate(
        """() => {
          const n = s => String(s || '').replace(/\u3000/g, ' ').replace(/\s+/g, ' ').trim();
          const out = [];
          for (const a of Array.from(document.querySelectorAll('a[href]'))) {
            const card = a.closest('article,li,[role="listitem"]');
            const text = n((card || a.parentElement || a).innerText || '');
            if (text.includes('下書き')) out.push(a.href || '');
          }
          return out;
        }"""
    )
    return [safe_note_href(value) for value in (values or []) if safe_note_href(value)]


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


def expected_contract(title: str) -> tuple[str, str, set[str]]:
    response = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{TARGET}")
    if response.status_code != 200:
        raise RuntimeError("source_page_read_failed")
    state = ready_sync._source_state(response.json())
    if state is None or state.get("sync_id") != TARGET:
        raise RuntimeError("source_not_active_ready")
    if str(state.get("title") or "").strip() != title.strip():
        raise RuntimeError("source_destination_title_mismatch")
    manuscript = ready_sync._source_current_ready_manuscript(TARGET)
    if not manuscript:
        raise RuntimeError("current_contract_manuscript_missing")
    presented = run222.prepare_note_editor_manuscript(manuscript, title)
    expected_visible = audit292._rendered_visible_text(presented)
    if len(expected_visible) < 150:
        raise RuntimeError("prepared_presentation_too_short")
    return presented, expected_visible, expected_external_urls(presented)


def ensure_auth(context, page, url: str, seeded: bool) -> bool:
    if not note_base._looks_logged_out(page):
        return seeded
    if not seeded:
        seeded = bool(cloud._seed_note_state(context, page))
    if seeded:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(900)
    if note_base._looks_logged_out(page):
        raise RuntimeError("note_auth_inactive")
    return seeded


def candidate_signature(page, title: str, expected_visible: str, expected_urls: set[str]) -> tuple[str, dict] | None:
    if not audit291._is_note_edit_url(str(page.url or "")):
        return None
    try:
        persisted_title = audit291._title_value(page)
        title_field = note_base._find_title(page)
        body = note_base._find_body(page, title_field)
        actual_visible = norm(str(body.inner_text(timeout=5000) or ""))
        hrefs = body.locator("a[href]").evaluate_all("els => els.map(a => a.href || '')")
    except Exception:
        return None
    if not actual_visible:
        return None
    actual_urls = {value for value in (normalize_external_url(raw) for raw in (hrefs or [])) if value}
    matched_external = len(expected_urls & actual_urls)
    external_ratio = matched_external / max(1, len(expected_urls)) if expected_urls else 0.0
    similarity = difflib.SequenceMatcher(None, expected_visible, actual_visible, autojunk=False).ratio()
    length_ratio = len(actual_visible) / max(1, len(expected_visible))
    boundary = min(64, len(expected_visible))
    prefix_match = bool(boundary and expected_visible[:boundary] in actual_visible)
    suffix_match = bool(boundary and expected_visible[-boundary:] in actual_visible)
    title_match = persisted_title.strip() == title.strip()
    source_present = run222.SOURCE_HEADING in actual_visible
    strong = bool(
        0.68 <= length_ratio <= 1.40
        and source_present
        and (
            (title_match and similarity >= 0.72 and (prefix_match or suffix_match or external_ratio >= 0.5))
            or (
                len(expected_urls) >= 1
                and matched_external == len(expected_urls)
                and similarity >= 0.74
                and (prefix_match or suffix_match)
            )
        )
    )
    draft_id = lifecycle.draft_identity_from_url(str(page.url or ""))
    return draft_id, {
        "strong_match": strong,
        "title_match": title_match,
        "similarity_ratio": round(similarity, 4),
        "length_ratio": round(length_ratio, 4),
        "prefix_match": prefix_match,
        "suffix_match": suffix_match,
        "source_present": source_present,
        "expected_external_link_count": len(expected_urls),
        "matched_external_link_count": matched_external,
        "external_link_match_ratio": round(external_ratio, 4),
    }


def discover_identity(title: str, expected_visible: str, expected_urls: set[str]) -> tuple[str, dict[str, object]]:
    from playwright.sync_api import sync_playwright

    exact_ids: set[str] = set()
    candidate_urls: set[str] = set()
    pages_checked = 0
    title_matches = 0
    list_edit_href_count = 0
    draft_card_href_count = 0
    unique_list_fingerprints: set[str] = set()
    editor_candidates_checked = 0
    strong_matches: dict[str, dict] = {}
    max_similarity = 0.0
    max_external_ratio = 0.0
    seeded = False

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            list_urls = ["https://note.com/notes"]
            list_urls += [f"https://note.com/notes?page={n}&status=draft" for n in range(1, 11)]
            list_urls += [f"https://note.com/notes?page={n}&kind=draft" for n in range(1, 11)]
            seen_routes: set[str] = set()
            for list_url in list_urls:
                page.goto(list_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(900)
                seeded = ensure_auth(context, page, list_url, seeded)
                current = urlparse(str(page.url or ""))
                if (current.hostname or "").lower() not in {"note.com", "editor.note.com"}:
                    raise RuntimeError("draft_list_left_note_domain")
                route_key = f"{current.path}?{current.query}"
                if route_key in seen_routes:
                    continue
                seen_routes.add(route_key)
                pages_checked += 1
                try:
                    visible = norm(str(page.locator("body").inner_text(timeout=5000) or ""))
                except Exception:
                    visible = ""
                if visible:
                    unique_list_fingerprints.add(hashlib.sha256(visible.encode("utf-8")).hexdigest())

                hrefs = title_anchor_hrefs(page, title)
                title_matches += len(hrefs)
                for href in hrefs:
                    parsed = urlparse(href)
                    if re.fullmatch(r"/notes/[^/?#]+/edit/?", parsed.path or "", flags=re.I):
                        exact_ids.add(lifecycle.draft_identity_from_url(href))
                    else:
                        candidate_urls.add(href)

                edits = edit_hrefs(page)
                list_edit_href_count += len(edits)
                candidate_urls.update(edits)
                cards = draft_card_hrefs(page)
                draft_card_href_count += len(cards)
                candidate_urls.update(cards)

                if len(exact_ids) > 1:
                    raise RuntimeError("stable_identity_not_unique")
                if len(exact_ids) == 1:
                    draft_id = next(iter(exact_ids))
                    return draft_id, {
                        "identity_proof_mode": "exact_title_edit_link",
                        "list_pages_checked": pages_checked,
                        "title_link_match_count": title_matches,
                        "list_edit_href_count": list_edit_href_count,
                        "draft_card_href_count": draft_card_href_count,
                        "unique_list_fingerprint_count": len(unique_list_fingerprints),
                        "history_candidate_count": 0,
                        "editor_candidates_checked": 0,
                        "strong_signature_match_count": 1,
                    }

            history_candidates = cloud._recent_private_edit_urls(cloud._profile_dir())
            candidate_urls.update(history_candidates)
            for candidate in list(candidate_urls):
                try:
                    page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(800)
                    seeded = ensure_auth(context, page, candidate, seeded)
                    if not audit291._is_note_edit_url(str(page.url or "")):
                        continue
                    editor_candidates_checked += 1
                    measured = candidate_signature(page, title, expected_visible, expected_urls)
                    if not measured:
                        continue
                    draft_id, metrics = measured
                    max_similarity = max(max_similarity, float(metrics["similarity_ratio"]))
                    max_external_ratio = max(max_external_ratio, float(metrics["external_link_match_ratio"]))
                    if metrics["strong_match"]:
                        strong_matches[draft_id] = metrics
                except Exception:
                    continue
        finally:
            context.close()

    metrics: dict[str, object] = {
        "identity_proof_mode": "content_signature",
        "list_pages_checked": pages_checked,
        "title_link_match_count": title_matches,
        "list_edit_href_count": list_edit_href_count,
        "draft_card_href_count": draft_card_href_count,
        "unique_list_fingerprint_count": len(unique_list_fingerprints),
        "history_candidate_count": len(history_candidates),
        "candidate_route_count": len(candidate_urls),
        "editor_candidates_checked": editor_candidates_checked,
        "strong_signature_match_count": len(strong_matches),
        "max_similarity_ratio": round(max_similarity, 4),
        "max_external_link_match_ratio": round(max_external_ratio, 4),
    }
    if len(strong_matches) != 1:
        raise RuntimeError("identity_not_found:" + json.dumps(metrics, sort_keys=True))
    draft_id, proof = next(iter(strong_matches.items()))
    metrics.update({
        "matched_title_exact": bool(proof["title_match"]),
        "matched_similarity_ratio": proof["similarity_ratio"],
        "matched_length_ratio": proof["length_ratio"],
        "matched_prefix": proof["prefix_match"],
        "matched_suffix": proof["suffix_match"],
        "matched_external_link_count": proof["matched_external_link_count"],
        "expected_external_link_count": proof["expected_external_link_count"],
    })
    return draft_id, metrics


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


def safe_result(result: dict, discovery: dict[str, object], draft_id: str) -> dict:
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
    out["identity_discovery"] = "read_only_ui_and_existing_routes"
    out["stable_identity_hash"] = hashlib.sha256(draft_id.encode("utf-8")).hexdigest()[:12]
    return out


def main() -> int:
    try:
        destination, title = destination_contract()
        _presented, expected_visible, expected_urls = expected_contract(title)
        draft_id, discovery = discover_identity(title, expected_visible, expected_urls)
        result = audit_with_identity(destination, title, draft_id)
        print(json.dumps(safe_result(result, discovery, draft_id), ensure_ascii=False, sort_keys=True))
        return 0 if result.get("status") == "audit_passed" else 2
    except Exception as exc:
        message = str(exc)
        metrics: dict[str, object] = {}
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
