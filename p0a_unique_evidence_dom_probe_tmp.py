#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json

import note_document_contract as contract
import note_document_dom as dom
import note_draft_automation as note_base
import run190_note_persistent_cloud as cloud
import run291_note_private_draft_audit as audit291
import p0a_readonly_ui_discovery_tmp as discovery


def main() -> int:
    destination, title = discovery.destination_contract()
    presented, expected_visible, expected_urls = discovery.expected_contract(title)
    if not expected_urls:
        print(json.dumps({
            "status": "probe_failed_safe",
            "diagnostic_code": "no_expected_external_evidence_links",
            "read_only": True,
            "zero_gemini_calls": True,
            "draft_mutation": False,
            "public_release": False,
        }, sort_keys=True))
        return 2

    candidates = cloud._recent_private_edit_urls(cloud._profile_dir())
    checked = 0
    readable = 0
    full_external: dict[str, dict] = {}
    source_full_external: dict[str, dict] = {}
    title_exact_count = 0
    max_similarity = 0.0
    max_external_ratio = 0.0
    selected_url = ""
    selected_id = ""
    selected_proof: dict = {}
    seeded = False

    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            for candidate in candidates:
                try:
                    page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(700)
                    seeded = discovery.ensure_auth(context, page, candidate, seeded)
                    if not audit291._is_note_edit_url(str(page.url or "")):
                        continue
                    checked += 1
                    measured = discovery.candidate_signature(page, title, expected_visible, expected_urls)
                    if not measured:
                        continue
                    readable += 1
                    draft_id, metrics = measured
                    similarity = float(metrics["similarity_ratio"])
                    external_ratio = float(metrics["external_link_match_ratio"])
                    max_similarity = max(max_similarity, similarity)
                    max_external_ratio = max(max_external_ratio, external_ratio)
                    if metrics["title_match"]:
                        title_exact_count += 1
                    if (
                        int(metrics["expected_external_link_count"]) > 0
                        and int(metrics["matched_external_link_count"]) == int(metrics["expected_external_link_count"])
                    ):
                        full_external[draft_id] = metrics
                        if metrics["source_present"]:
                            source_full_external[draft_id] = metrics
                except Exception:
                    continue

            safe = {
                "status": "evidence_probe_complete",
                "read_only": True,
                "zero_gemini_calls": True,
                "draft_mutation": False,
                "public_release": False,
                "history_candidate_count": len(candidates),
                "editor_candidates_checked": checked,
                "readable_candidate_count": readable,
                "expected_external_link_count": len(expected_urls),
                "full_external_match_count": len(full_external),
                "full_external_with_source_count": len(source_full_external),
                "title_exact_candidate_count": title_exact_count,
                "max_similarity_ratio": round(max_similarity, 4),
                "max_external_link_match_ratio": round(max_external_ratio, 4),
            }

            if len(source_full_external) != 1:
                safe["diagnostic_code"] = "unique_evidence_identity_not_proven"
                print(json.dumps(safe, sort_keys=True))
                return 2

            selected_id, selected_proof = next(iter(source_full_external.items()))
            for candidate in candidates:
                try:
                    candidate_id = discovery.lifecycle.draft_identity_from_url(candidate)
                except Exception:
                    continue
                if candidate_id == selected_id:
                    selected_url = candidate
                    break
            if not selected_url:
                safe["diagnostic_code"] = "selected_route_not_resolved"
                print(json.dumps(safe, sort_keys=True))
                return 2

            page.goto(selected_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(800)
            seeded = discovery.ensure_auth(context, page, selected_url, seeded)
            if not audit291._is_note_edit_url(str(page.url or "")):
                safe["diagnostic_code"] = "selected_route_left_editor"
                print(json.dumps(safe, sort_keys=True))
                return 2

            title_field = note_base._find_title(page)
            body = note_base._find_body(page, title_field)
            snapshot = dom.snapshot_note_body(body)
            safe.update(dom.safe_snapshot_diagnostics(snapshot))
            safe.update({
                "identity_proof_mode": "unique_complete_external_evidence_set",
                "stable_identity_hash": hashlib.sha256(selected_id.encode("utf-8")).hexdigest()[:12],
                "matched_title_exact": bool(selected_proof["title_match"]),
                "matched_similarity_ratio": selected_proof["similarity_ratio"],
                "matched_length_ratio": selected_proof["length_ratio"],
                "matched_prefix": bool(selected_proof["prefix_match"]),
                "matched_suffix": bool(selected_proof["suffix_match"]),
                "selected_source_present": bool(selected_proof["source_present"]),
                "normalization_policy_version": contract.NORMALIZATION_POLICY_VERSION,
            })
            actual_doc = None
            try:
                actual_doc = dom.document_from_note_snapshot(
                    snapshot,
                    allowed_normalizations=(contract.NOTE_LIST_ITEM_PARAGRAPH_WRAPPER,),
                )
                safe["actual_dom_convertible"] = True
                safe["actual_canonical_top_level_count"] = len(actual_doc.children)
            except contract.CanonicalContractError as exc:
                safe["actual_dom_convertible"] = False
                safe["actual_dom_conversion_code"] = exc.code

            try:
                expected_doc = contract.normalize_document(contract.parse_presentation_markdown(presented))
                safe["expected_canonical_top_level_count"] = len(expected_doc.children)
                if actual_doc is not None:
                    receipt = contract.compare_documents(expected_doc, actual_doc)
                    safe.update({
                        "canonical_match_to_current": receipt["canonical_match"],
                        "mismatch_category": receipt["mismatch_category"],
                        "mismatch_path": receipt["mismatch_path"],
                    })
            except contract.CanonicalContractError as exc:
                safe["expected_contract_parse_ok"] = False
                safe["expected_contract_parse_code"] = exc.code
            else:
                safe["expected_contract_parse_ok"] = True

            safe["status"] = "dom_observed"
            print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
            return 0
        finally:
            context.close()


if __name__ == "__main__":
    raise SystemExit(main())
