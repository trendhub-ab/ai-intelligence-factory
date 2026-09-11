"""Provider-free proof that the real saved Stock can enter Deep Dive selection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from x_discovery.bounded_factory_validation import build_screening_repo, validate_saved_candidate


EXPECTED_STOCK_SHA256 = "97a9823e4e25ccd974a8b31366f248e8d0814a6d9778c66b05bc81124a695d85"


class StockHandoffError(RuntimeError):
    pass


def build_selected_item(pipeline: Any, candidate: dict, calibration: dict, stock: dict) -> tuple[dict, dict]:
    """Rebuild the one persisted Defense Factory item and pass the real selector."""
    saved = validate_saved_candidate(candidate)
    expected = {
        "status": "STOCK_SAVED", "operation": "defense-factory-stock-20260911",
        "canonical_url": saved["canonical_url"], "x_post_id": saved["x_post_id"],
        "final_score": 88, "stock_persisted": True, "notion_writes": 1,
        "model_calls": 0, "deep_dive_selected": False,
    }
    for key, value in expected.items():
        if stock.get(key) != value:
            raise StockHandoffError(f"unexpected Stock observation field: {key}")
    if (calibration.get("status") != "CALIBRATION_COMPLETED"
            or calibration.get("final_score") != stock["final_score"]
            or calibration.get("canonical_url") != stock["canonical_url"]):
        raise StockHandoffError("Calibration and Stock observations disagree")
    page_id = str(stock.get("notion_page_id") or "").strip()
    if not page_id:
        raise StockHandoffError("persisted Notion page ID is required")
    row = calibration.get("calibration_result") or {}
    repo = build_screening_repo(saved)
    repo["source"] = "OfficialVendor"
    item = {
        "screening_id": "X0001", "repo": repo,
        "raw_score": calibration["raw_score"], "final_score": calibration["final_score"],
        "score": calibration["final_score"],
        "commercial_score": row.get("commercial_score"),
        "shelf_life_score": row.get("shelf_life_score"),
        "portfolio_topic": row.get("portfolio_topic"),
        "raw_portfolio_topic": calibration.get("raw_portfolio_topic"),
        "tracking_eligible": row.get("tracking_eligible"),
        "tracking_reason": row.get("tracking_reason"),
        "reason": row.get("reason"), "calibrated": True,
        "screening_status": "completed", "notion_page_id": page_id,
    }
    selected = pipeline._select_stocked_deep_dive_candidates([item])
    if len(selected) != 1 or selected[0].get("notion_page_id") != page_id:
        raise StockHandoffError("real Stock was not selected by Production Deep Dive policy")
    return saved, selected[0]


def run(pipeline: Any, candidate: dict, calibration: dict, stock: dict) -> dict:
    saved, item = build_selected_item(pipeline, candidate, calibration, stock)
    return {
        "schema_version": 1, "lane": "x_saved_stock_deep_dive_handoff",
        "status": "DEEP_DIVE_SELECTION_READY", "canonical_url": saved["canonical_url"],
        "notion_page_id": item["notion_page_id"], "final_score": item["final_score"],
        "stock_persisted": True, "deep_dive_selected": True,
        "model_calls": 0, "notion_writes": 0, "generation_executed": False,
        "publication_executed": False, "factory_write": False,
    }


def run_from_paths(pipeline: Any, candidate_path: Path, calibration_path: Path, stock_path: Path) -> dict:
    stock_raw = stock_path.read_bytes()
    if hashlib.sha256(stock_raw).hexdigest() != EXPECTED_STOCK_SHA256:
        raise StockHandoffError("Stock observation changed")
    result = run(pipeline, json.loads(candidate_path.read_text()),
                 json.loads(calibration_path.read_text()), json.loads(stock_raw))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result
