from __future__ import annotations

from typing import Any

from deep_dive_portfolio import select_stocked_deep_dive_candidates


class PostCalibrationDryRunError(RuntimeError):
    """Fail-closed contract violation for provider-free post-calibration audit."""


def _score(value: object, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise PostCalibrationDryRunError(f"{label} must be an integer") from exc
    if not 0 <= parsed <= 100:
        raise PostCalibrationDryRunError(f"{label} must be between 0 and 100")
    return parsed


def _attach_profit_metadata(item: dict, commercial: object, shelf: object) -> None:
    item["commercial_score"] = _score(commercial, "commercial_score")
    item["shelf_life_score"] = _score(shelf, "shelf_life_score")
    # Deterministic ordering proxy is irrelevant for a one-item boundary audit.
    item["deep_dive_priority_score"] = float(item.get("score") or 0)
    item["shelf_life"] = "EVERGREEN" if item["shelf_life_score"] >= 75 else "CURRENT"


def _attach_portfolio_topic(item: dict, topic: object, raw_topic: object) -> None:
    normalized = str(topic or raw_topic or "OTHER").strip().upper() or "OTHER"
    item["portfolio_topic"] = normalized


def _select_with_real_stock_guard(*, final_score: int, stock_threshold: int, persisted: bool) -> list[dict]:
    item = {
        "score": final_score,
        "commercial_score": 90,
        "shelf_life_score": 80,
        "portfolio_topic": "SECURITY",
        "raw_portfolio_topic": "SECURITY",
        "repo": {
            "nameWithOwner": "Defense Factory",
            "url": "https://openai.com/the-defense-factory",
            "source": "XDiscoverySavedPrimary",
            "stargazerCount": 0,
            "description": "Provider-free post-calibration boundary simulation.",
        },
        # This marker is deliberately synthetic and is never written anywhere. Its sole
        # purpose is to exercise the real deterministic guard that requires persistence.
        "notion_page_id": "__SIMULATED_STOCK_PERSISTENCE__" if persisted else None,
    }
    return select_stocked_deep_dive_candidates(
        [item],
        notion_save_threshold_score=stock_threshold,
        attach_profit_metadata=_attach_profit_metadata,
        attach_portfolio_topic=_attach_portfolio_topic,
        enable_profit_priority=True,
        profit_score_neutral=50.0,
        top_n_for_deep_dive=3,
        evergreen_portfolio_min=0,
        evergreen_priority_tolerance=0.0,
        apply_content_portfolio_balance_fn=lambda ordered, _visible: ordered,
        apply_publication_reliability_slot_fn=lambda ordered, _visible: ordered,
    )


def audit_post_calibration_counterexamples(pipeline_policy: Any) -> dict[str, Any]:
    """Exercise threshold/persistence counterexamples with zero provider or write calls.

    This does not pretend calibration happened. It asks what the deterministic Production
    routing would do *after* a hypothetical calibrated Final Score is known. The cases
    straddle the live Stock threshold and separately toggle the persistence prerequisite.
    """
    stock_threshold = int(getattr(pipeline_policy, "NOTION_SAVE_THRESHOLD_SCORE"))
    top_n = int(getattr(pipeline_policy, "TOP_N_FOR_DEEP_DIVE"))
    if stock_threshold <= 0 or stock_threshold > 100:
        raise PostCalibrationDryRunError("NOTION_SAVE_THRESHOLD_SCORE must be between 1 and 100")
    if top_n <= 0:
        raise PostCalibrationDryRunError("TOP_N_FOR_DEEP_DIVE must be positive")

    below = stock_threshold - 1
    at = stock_threshold

    below_selected = _select_with_real_stock_guard(
        final_score=below, stock_threshold=stock_threshold, persisted=False
    )
    threshold_unpersisted = _select_with_real_stock_guard(
        final_score=at, stock_threshold=stock_threshold, persisted=False
    )
    threshold_persisted = _select_with_real_stock_guard(
        final_score=at, stock_threshold=stock_threshold, persisted=True
    )
    defense_unpersisted = _select_with_real_stock_guard(
        final_score=88, stock_threshold=stock_threshold, persisted=False
    )
    defense_persisted = _select_with_real_stock_guard(
        final_score=88, stock_threshold=stock_threshold, persisted=True
    )

    if below_selected:
        raise PostCalibrationDryRunError("below-threshold candidate reached Deep Dive")
    if threshold_unpersisted:
        raise PostCalibrationDryRunError("unpersisted threshold candidate reached Deep Dive")
    if len(threshold_persisted) != 1:
        raise PostCalibrationDryRunError("persisted threshold candidate did not reach Deep Dive selector")
    if defense_unpersisted:
        raise PostCalibrationDryRunError("unpersisted Defense Factory candidate reached Deep Dive")
    expected_defense_persisted = 88 >= stock_threshold
    if bool(defense_persisted) != expected_defense_persisted:
        raise PostCalibrationDryRunError("Defense Factory persisted simulation disagrees with Stock threshold")

    return {
        "schema_version": 1,
        "lane": "x_saved_post_calibration_counterexample_audit",
        "status": "POST_CALIBRATION_GUARDS_VERIFIED",
        "stock_threshold": stock_threshold,
        "top_n_for_deep_dive": top_n,
        "cases": {
            "below_threshold_unpersisted": {
                "final_score": below,
                "deep_dive_selected": False,
            },
            "at_threshold_unpersisted": {
                "final_score": at,
                "deep_dive_selected": False,
                "blocked_by": "stock_persistence_required",
            },
            "at_threshold_persisted_simulation": {
                "final_score": at,
                "deep_dive_selected": True,
                "simulation_only": True,
            },
            "defense_88_unpersisted": {
                "final_score": 88,
                "deep_dive_selected": False,
                "blocked_by": "stock_persistence_required",
            },
            "defense_88_persisted_simulation": {
                "final_score": 88,
                "deep_dive_selected": expected_defense_persisted,
                "simulation_only": True,
            },
        },
        "calibration_executed": False,
        "stock_persisted": False,
        "model_calls": 0,
        "notion_calls": 0,
        "source_fetch_calls": 0,
        "apify_calls": 0,
        "fetchlayer_calls": 0,
        "factory_write": False,
        "generation_executed": False,
        "publication_executed": False,
    }
