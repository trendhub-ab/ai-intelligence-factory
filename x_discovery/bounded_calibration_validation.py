from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from x_discovery.bounded_factory_validation import (
    BoundedValidationError,
    build_screening_repo,
    validate_saved_candidate,
)


class BoundedCalibrationError(RuntimeError):
    """Fail-closed contract violation for saved-X Global Calibration validation."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BoundedCalibrationError(f"could not read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BoundedCalibrationError(f"{label} must be an object")
    return payload


def _require_int(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise BoundedCalibrationError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise BoundedCalibrationError(f"{label} must be an integer") from exc
    if not 0 <= parsed <= 100:
        raise BoundedCalibrationError(f"{label} must be between 0 and 100")
    return parsed


def validate_saved_screening_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != 1:
        raise BoundedCalibrationError("screening result schema_version must be 1")
    if payload.get("lane") != "x_saved_post_screening_dry_run":
        raise BoundedCalibrationError("screening result lane is invalid")
    if payload.get("factory_write") is not False:
        raise BoundedCalibrationError("screening result factory_write must be false")
    if payload.get("model_calls_allowed") != 0:
        raise BoundedCalibrationError("saved screening fixture must not authorize model calls")

    provenance = payload.get("observation_provenance")
    result = payload.get("screening_result")
    if not isinstance(provenance, Mapping) or not isinstance(result, Mapping):
        raise BoundedCalibrationError("screening provenance/result must be objects")
    if result.get("screening_id") != "X0001":
        raise BoundedCalibrationError("screening_id must be X0001")

    score = _require_int(result.get("score"), "score")
    commercial = _require_int(result.get("commercial_score"), "commercial_score")
    shelf = _require_int(result.get("shelf_life_score"), "shelf_life_score")
    topic = str(result.get("portfolio_topic") or "").strip().upper()
    if not topic:
        raise BoundedCalibrationError("portfolio_topic is required")
    if provenance.get("consensus", {}).get("score") != score:
        raise BoundedCalibrationError("saved screening score disagrees with provenance consensus")

    return {
        "screening_id": "X0001",
        "score": score,
        "commercial_score": commercial,
        "shelf_life_score": shelf,
        "portfolio_topic": topic,
        "tracking_eligible": bool(result.get("tracking_eligible")),
        "tracking_reason": str(result.get("tracking_reason") or "").strip(),
        "reason": str(result.get("reason") or "").strip(),
        "canonical_url": str(provenance.get("canonical_url") or "").strip(),
        "x_post_id": str(provenance.get("x_post_id") or "").strip(),
    }


def build_calibration_item(candidate_payload: Mapping[str, Any], screening_payload: Mapping[str, Any]) -> dict[str, Any]:
    try:
        candidate = validate_saved_candidate(candidate_payload)
    except BoundedValidationError as exc:
        raise BoundedCalibrationError(str(exc)) from exc
    screening = validate_saved_screening_result(screening_payload)
    if candidate["canonical_url"] != screening["canonical_url"]:
        raise BoundedCalibrationError("candidate URL disagrees with saved screening result")
    if candidate["x_post_id"] != screening["x_post_id"]:
        raise BoundedCalibrationError("X provenance disagrees with saved screening result")

    repo = build_screening_repo(candidate)
    return {
        "screening_id": "X0001",
        "repo": repo,
        "raw_score": screening["score"],
        "final_score": None,
        "score": screening["score"],
        "raw_commercial_score": screening["commercial_score"],
        "commercial_score": screening["commercial_score"],
        "raw_shelf_life_score": screening["shelf_life_score"],
        "shelf_life_score": screening["shelf_life_score"],
        "raw_portfolio_topic": screening["portfolio_topic"],
        "portfolio_topic": screening["portfolio_topic"],
        "tracking_eligible": screening["tracking_eligible"],
        "tracking_reason": screening["tracking_reason"],
        "reason": screening["reason"],
        "calibrated": False,
        "screening_status": "completed",
        "notion_page_id": None,
    }


def run_calibration_boundary(
    pipeline_module: Any,
    candidate_payload: Mapping[str, Any],
    screening_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Reach the real Global Calibration prompt boundary with zero provider/write calls."""
    item = build_calibration_item(candidate_payload, screening_payload)
    if not bool(getattr(pipeline_module, "ENABLE_GLOBAL_CALIBRATION", False)):
        raise BoundedCalibrationError("Global Calibration must be enabled for this validation")
    minimum = int(getattr(pipeline_module, "GLOBAL_CALIBRATION_MIN_RAW_SCORE"))
    if item["raw_score"] < minimum:
        raise BoundedCalibrationError("saved screening result is below Calibration threshold")

    prompt = pipeline_module._calibration_prompt([item])
    if not isinstance(prompt, str) or not prompt.strip():
        raise BoundedCalibrationError("Factory calibration prompt could not be constructed")

    return {
        "schema_version": 1,
        "lane": "x_saved_candidate_calibration_validation",
        "status": "CALIBRATION_BOUNDARY_READY",
        "candidate_count": 1,
        "screening_id": "X0001",
        "canonical_url": item["repo"]["url"],
        "x_post_id": item["repo"]["x_discovery_provenance"]["post_id"],
        "raw_score": item["raw_score"],
        "raw_commercial_score": item["raw_commercial_score"],
        "raw_shelf_life_score": item["raw_shelf_life_score"],
        "raw_portfolio_topic": item["raw_portfolio_topic"],
        "calibration_min_raw_score": minimum,
        "calibration_prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "calibration_prompt_chars": len(prompt),
        "operation_model_request_ceiling": 1,
        "calibration_executed": False,
        "model_calls": 0,
        "stock_persisted": False,
        "deep_dive_selected": False,
        "notion_calls": 0,
        "source_fetch_calls": 0,
        "apify_calls": 0,
        "fetchlayer_calls": 0,
        "factory_write": False,
        "generation_executed": False,
        "publication_executed": False,
    }


def run_from_paths(pipeline_module: Any, candidate_path: Path, screening_path: Path) -> dict[str, Any]:
    runner = run_calibration_boundary
    if os.environ.get("AIIF_X_CALIBRATION_EXECUTE", "").lower() == "true":
        from x_discovery.calibration_once import run_once
        runner = run_once
    result = runner(
        pipeline_module,
        _load_json(candidate_path, "candidate payload"),
        _load_json(screening_path, "screening payload"),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result
