from __future__ import annotations

from typing import Any, Mapping


class PostScreeningDryRunError(RuntimeError):
    """Fail-closed contract violation for provider-free post-screening audit."""


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PostScreeningDryRunError(f"{label} must be an object")
    return value


def _score(value: object, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise PostScreeningDryRunError(f"{label} must be an integer") from exc
    if not 0 <= parsed <= 100:
        raise PostScreeningDryRunError(f"{label} must be between 0 and 100")
    return parsed


def audit_post_screening_route(pipeline_module: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Audit production routing after screening without provider calls or writes.

    This deliberately does not invoke ``calibrate_candidates`` because that path is a
    Gemini call. It evaluates the exact Production thresholds and stops fail-closed when
    calibration is required. It also never fakes a Notion page id: production Deep Dive
    selection requires a persisted Stock row, so Deep Dive remains blocked until both a
    final calibrated score and successful Stock persistence exist.
    """
    root = _mapping(payload, "payload")
    if root.get("schema_version") != 1:
        raise PostScreeningDryRunError("schema_version must be 1")
    if root.get("lane") != "x_saved_post_screening_dry_run":
        raise PostScreeningDryRunError("lane must be x_saved_post_screening_dry_run")
    if root.get("factory_write") is not False:
        raise PostScreeningDryRunError("factory_write must be false")
    if root.get("model_calls_allowed") != 0:
        raise PostScreeningDryRunError("model_calls_allowed must be 0")

    result = _mapping(root.get("screening_result"), "screening_result")
    if result.get("screening_id") != "X0001":
        raise PostScreeningDryRunError("screening_id must be X0001")
    raw_score = _score(result.get("score"), "screening_result.score")
    commercial_score = _score(result.get("commercial_score"), "screening_result.commercial_score")
    shelf_life_score = _score(result.get("shelf_life_score"), "screening_result.shelf_life_score")
    topic = str(result.get("portfolio_topic") or "").strip()
    if not topic:
        raise PostScreeningDryRunError("screening_result.portfolio_topic is required")

    stock_threshold = int(getattr(pipeline_module, "NOTION_SAVE_THRESHOLD_SCORE"))
    calibration_enabled = bool(getattr(pipeline_module, "ENABLE_GLOBAL_CALIBRATION"))
    calibration_min = int(getattr(pipeline_module, "GLOBAL_CALIBRATION_MIN_RAW_SCORE"))
    top_n = int(getattr(pipeline_module, "TOP_N_FOR_DEEP_DIVE"))

    raw_stock_threshold_pass = raw_score >= stock_threshold
    calibration_required = calibration_enabled and raw_score >= calibration_min

    if calibration_required:
        status = "CALIBRATION_REQUIRED"
        final_score = None
        final_stock_threshold_pass = None
        stock_route = "DEFERRED_PENDING_CALIBRATION"
        deep_dive_route = "BLOCKED_PENDING_CALIBRATION_AND_STOCK_PERSISTENCE"
    else:
        status = "POST_SCREENING_ROUTE_AUDITED"
        final_score = raw_score
        final_stock_threshold_pass = final_score >= stock_threshold
        stock_route = "ELIGIBLE_AFTER_PERSISTENCE" if final_stock_threshold_pass else "BELOW_STOCK_THRESHOLD"
        deep_dive_route = (
            "ELIGIBLE_FOR_SELECTION_ONLY_AFTER_STOCK_PERSISTENCE"
            if final_stock_threshold_pass
            else "NOT_ELIGIBLE"
        )

    return {
        "schema_version": 1,
        "lane": "x_saved_post_screening_dry_run",
        "status": status,
        "screening_id": "X0001",
        "raw_score": raw_score,
        "commercial_score": commercial_score,
        "shelf_life_score": shelf_life_score,
        "portfolio_topic": topic,
        "stock_threshold": stock_threshold,
        "raw_stock_threshold_pass": raw_stock_threshold_pass,
        "global_calibration_enabled": calibration_enabled,
        "global_calibration_min_raw_score": calibration_min,
        "calibration_required": calibration_required,
        "calibration_executed": False,
        "final_score": final_score,
        "final_stock_threshold_pass": final_stock_threshold_pass,
        "stock_route": stock_route,
        "stock_persisted": False,
        "top_n_for_deep_dive": top_n,
        "deep_dive_route": deep_dive_route,
        "deep_dive_selected": False,
        "model_calls": 0,
        "source_fetch_calls": 0,
        "apify_calls": 0,
        "fetchlayer_calls": 0,
        "factory_write": False,
        "generation_executed": False,
        "publication_executed": False,
    }
