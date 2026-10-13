#!/usr/bin/env python3
"""Exact one-article recovery for a Quality-PASS / Ready-asset persistence failure.

This lane does not scan recent rows and does not run Fresh acquisition. It fetches one
Content Intelligence page by its exact 32-hex page id, applies the published-terminal
admission guard, then reuses the current Production article path with persistence enabled.
A successful return therefore means the normal Ready asset contract and Notion Ready
persistence completed; note draft creation remains a separate downstream workflow.
"""
from __future__ import annotations

import argparse
import json
import re
from typing import Any, Callable


def _normalize_sync_id(value: str) -> str:
    sync_id = re.sub(r"[^0-9a-fA-F]", "", str(value or "")).lower()
    if len(sync_id) != 32:
        raise ValueError("sync_id must be exactly 32 hex characters")
    return sync_id


def _selected_name(prop: dict[str, Any] | None) -> str:
    return str((((prop or {}).get("select") or {}).get("name") or "")).strip()


def load_exact_existing_item(pipeline_module, sync_id: str) -> dict[str, Any] | None:
    """Rehydrate one existing Content Intelligence row by exact page id.

    This deliberately bypasses ``get_regen_test_items`` because that helper is a bounded
    recent-row scan (max 100), not an exact-address lookup.
    """
    sync_id = _normalize_sync_id(sync_id)
    try:
        response = pipeline_module.requests.get(
            f"https://api.notion.com/v1/pages/{sync_id}",
            headers=pipeline_module._notion_headers(),
            timeout=10,
        )
    except Exception:
        return None
    if int(getattr(response, "status_code", 0) or 0) != 200:
        return None

    page = response.json() or {}
    page_id = _normalize_sync_id(str(page.get("id") or ""))
    if page_id != sync_id:
        return None
    props = page.get("properties") or {}

    plain = pipeline_module._notion_plain_text
    name = plain(props.get(pipeline_module.PROP_NAME, {})).strip()
    page_url = str((props.get(pipeline_module.PROP_URL, {}) or {}).get("url") or "").strip()
    if not name or not page_url:
        return None

    source = _selected_name(props.get(pipeline_module.PROP_SOURCE)) or "HackerNews"
    summary = plain(props.get(pipeline_module.PROP_SOURCE_SUMMARY, {})).strip()
    engagement = (props.get(pipeline_module.PROP_ENGAGEMENT, {}) or {}).get("number") or 0
    screening_score = (props.get(pipeline_module.PROP_SCREENING_SCORE, {}) or {}).get("number")
    screening_reason = plain(props.get(pipeline_module.PROP_SCREENING_REASON, {})).strip()
    published = ((props.get(pipeline_module.PROP_PUBLISHED_AT, {}) or {}).get("date") or {}).get("start")
    license_text = plain(props.get(pipeline_module.PROP_LICENSE, {})).strip()

    repo = {
        "nameWithOwner": name,
        "description": summary or "既存記事のReady asset persistence recovery",
        "url": page_url,
        "stargazerCount": int(engagement or 0),
        "source": source,
        "publishedAt": published,
        "sourceContext": "",
        "sourceDetails": {"external_url": page_url},
        "licenseInfo": ({"spdxId": license_text} if source == "GitHub" and license_text else None),
        "notion_page_id": sync_id,
    }
    return {
        "notion_page_id": sync_id,
        "screening_score": int(screening_score) if screening_score is not None else int(
            getattr(pipeline_module, "NOTION_SAVE_THRESHOLD_SCORE", 60)
        ),
        "screening_reason": screening_reason or "Ready asset persistence recovery",
        "repo": repo,
    }


def _persisted_generation_ready(report: Any) -> bool:
    if isinstance(report, tuple) and len(report) >= 2:
        return str(report[1] or "").strip().lower() == "accepted"
    return bool(report)


def run_exact_ready_asset_recovery(
    pipeline_module,
    sync_id: str,
    *,
    load_exact: Callable[[Any, str], dict[str, Any] | None] | None = None,
    regeneration_decision: Callable[[str], tuple[bool, str]] | None = None,
) -> dict[str, Any]:
    """Recover exactly one non-terminal article through current Production persistence."""
    sync_id = _normalize_sync_id(sync_id)
    if regeneration_decision is None:
        from operational_output_contract import automatic_regeneration_decision
        regeneration_decision = automatic_regeneration_decision
    allowed, reason = regeneration_decision(sync_id)
    if not allowed:
        return {"status": "blocked_terminal", "sync_id": sync_id, "reason": reason, "ready": False}

    loader = load_exact or load_exact_existing_item
    item = loader(pipeline_module, sync_id)
    if not item:
        return {"status": "exact_target_missing", "sync_id": sync_id, "ready": False}
    if _normalize_sync_id(str(item.get("notion_page_id") or "")) != sync_id:
        return {"status": "exact_target_mismatch", "sync_id": sync_id, "ready": False}

    repo = dict(item.get("repo") or {})
    legal_gate = getattr(pipeline_module, "legal_safety_gate", None)
    if callable(legal_gate):
        safe, license_status = legal_gate(repo)
        if not safe:
            return {
                "status": "blocked_legal",
                "sync_id": sync_id,
                "reason": str(license_status or "legal_safety_gate"),
                "ready": False,
            }

    report = pipeline_module.generate_intelligence_report(
        repo,
        notion_page_id=sync_id,
        screening_score=item.get("screening_score"),
        screening_reason=item.get("screening_reason", "Ready asset persistence recovery"),
        candidate_rank=1,
        candidate_origin="ready_asset_recovery",
        persist_results=True,
    )
    ready = _persisted_generation_ready(report)
    return {
        "status": "ready_recovered" if ready else "not_ready",
        "sync_id": sync_id,
        "ready": ready,
        "delivery_reason": reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-id", required=True)
    args = parser.parse_args()

    import note_manuscript
    import pipeline
    import run179_eyecatch_font_refinement as run179
    from pending_retry_validation import install_current_production_article_stack

    install_current_production_article_stack(pipeline, note_manuscript)
    run179.ensure_google_font_assets(enabled=True, logger=getattr(pipeline, "logger", None))
    run179.require_production_japanese_font()
    pipeline.reset_article_audit_for_production_run()
    pipeline.reset_article_style_memory()
    pipeline.initialize_runtime()

    result = run_exact_ready_asset_recovery(pipeline, args.sync_id)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"ready_recovered", "blocked_terminal"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
