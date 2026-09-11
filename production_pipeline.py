"""Stable production entrypoint for the AI Intelligence Factory.

Run231 keeps this file as a small orchestration contract. Historical production
runtime layers live in ``runtime_layers.py`` in their exact validated order, while
performance telemetry is observational and installed only after all quality,
reliability, preflight, font, and compatibility contracts are in place.

Daily is currently PAUSED; this file remains the contract to use when Daily is
explicitly resumed.

Run305 also makes this file the sole root entrypoint for the bounded Product Review
child. An explicit environment flag selects a narrow provider/quota-only runtime;
direct core-pipeline bypasses from other root executables remain prohibited.
"""
from __future__ import annotations

import json
import os

from runtime_layers import install_runtime_layers as _canonical_install_runtime_layers


PRODUCT_REVIEW_PROVIDER_LAYER_ORDER = (
    "run203_runtime_state_channel.install",
    "gemini_timeout_rpd_fail_closed.install",
    "gemini_transient_recovery.install",
    "gemini_provider_resilience.install",
)


def install_product_review_provider_runtime(pipeline_module):
    """Install only provider/quota safety required by the product-only child."""
    import run203_runtime_state_channel as runtime_state_channel
    import gemini_timeout_rpd_fail_closed
    import gemini_transient_recovery
    import gemini_provider_resilience

    runtime_state_channel.install(pipeline_module)
    gemini_timeout_rpd_fail_closed.install(pipeline_module)
    gemini_transient_recovery.install(pipeline_module)
    gemini_provider_resilience.install(pipeline_module)
    return pipeline_module


def _product_review_runtime_requested() -> bool:
    return os.environ.get("AIIF_PRODUCT_REVIEW_RUNTIME", "").strip().lower() == "true"


def install_runtime_layers(pipeline_module):
    """Compatibility manifest for the existing Documentation Freshness Guard."""
    import run203_runtime_state_channel
    import gemini_timeout_rpd_fail_closed
    import gemini_transient_recovery
    import run260_gemini_model_routing
    import run172_production_reliability
    import gemini_provider_resilience
    import run173_operational_yield
    import run174_monthly_digest_integrity
    import run175_semantic_fact_precision
    import run223_technical_claim_precision
    import run224_multiplier_deterministic_rescue
    import run227_japanese_surface_integrity
    import run176_scope_fidelity
    import run177_paid_funnel_alignment
    import run226_reader_delight_planning
    import run228_reader_rhythm_planning
    import run178_eyecatch_editorial_layout_optimizer
    import run179_eyecatch_font_refinement
    import run180_eyecatch_semantic_layout
    import run181_eyecatch_visual_balance
    import run182_eyecatch_conclusion_emphasis
    import run183_eyecatch_emphasis_scale
    import reader_value_review_bridge
    import run208_reader_value_repair
    import run222_note_presentation_integrity
    import run296_editorial_format_v2
    import run248_first_real_publish_quality_calibration
    import run249_final_publication_surface_gate
    import run194_publication_contract

    return _canonical_install_runtime_layers(pipeline_module)


install_runtime_layers = _canonical_install_runtime_layers


def _workflow_dispatch_mode() -> str:
    explicit = os.environ.get("AIIF_ONE_SHOT_MODE", "").strip()
    if explicit:
        return explicit
    event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()
    if not event_path:
        return ""
    try:
        with open(event_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return str((payload.get("inputs") or {}).get("mode") or "").strip()
    except (OSError, ValueError, TypeError):
        return ""


def main() -> None:
    if _product_review_runtime_requested():
        _run_product_review_runtime()
        return

    import note_manuscript
    import pipeline
    import run179_eyecatch_font_refinement
    import run203_runtime_state_channel as runtime_state_channel
    from article_revalidation import install_full_recovery, run_article_revalidation
    from current_policy_ready_recovery import run_current_policy_ready_recovery
    from source_normalization import install as install_source_normalization
    from run231_performance_telemetry import install as install_performance_telemetry
    from run268_business_source_strategy import install as install_run268_business_source_strategy
    from run269_business_source_precision import install as install_run269_business_source_precision
    from run283_numeric_evidence_equivalence import install as install_run283_numeric_evidence_equivalence
    from run284_reader_recovery_precision import install as install_run284_reader_recovery_precision
    from run287_publication_date_provenance import install as install_run287_publication_date_provenance
    from reader_quality_precision import install as install_reader_quality_precision

    install_source_normalization(pipeline)
    install_runtime_layers(pipeline)
    install_run283_numeric_evidence_equivalence(pipeline)
    install_run268_business_source_strategy(pipeline)
    install_run269_business_source_precision(pipeline)
    install_reader_quality_precision(pipeline)
    install_run284_reader_recovery_precision(pipeline)
    install_run287_publication_date_provenance(note_manuscript, pipeline)

    mode = _workflow_dispatch_mode()

    if mode == "x_saved_candidate_validation":
        from pathlib import Path
        from x_discovery.bounded_factory_validation import BoundedValidationError, run_from_path
        candidate_path = os.environ.get("AIIF_X_SAVED_CANDIDATE_PATH", "").strip()
        if not candidate_path:
            raise BoundedValidationError("AIIF_X_SAVED_CANDIDATE_PATH is required")
        run_from_path(pipeline, Path(candidate_path))
        return

    if mode == "x_saved_candidate_calibration_validation":
        from pathlib import Path
        from x_discovery.bounded_calibration_validation import BoundedCalibrationError, run_from_paths
        candidate_path = os.environ.get("AIIF_X_SAVED_CANDIDATE_PATH", "").strip()
        screening_path = os.environ.get("AIIF_X_SAVED_SCREENING_PATH", "").strip()
        if not candidate_path:
            raise BoundedCalibrationError("AIIF_X_SAVED_CANDIDATE_PATH is required")
        if not screening_path:
            raise BoundedCalibrationError("AIIF_X_SAVED_SCREENING_PATH is required")
        run_from_paths(pipeline, Path(candidate_path), Path(screening_path))
        return

    if mode == "x_saved_candidate_stock_once":
        from pathlib import Path
        from x_discovery.stock_once import StockOnceError, run_from_paths
        candidate_path = os.environ.get("AIIF_X_SAVED_CANDIDATE_PATH", "").strip()
        observation_path = os.environ.get("AIIF_X_CALIBRATION_OBSERVATION_PATH", "").strip()
        if not candidate_path:
            raise StockOnceError("AIIF_X_SAVED_CANDIDATE_PATH is required")
        if not observation_path:
            raise StockOnceError("AIIF_X_CALIBRATION_OBSERVATION_PATH is required")
        run_from_paths(pipeline, Path(candidate_path), Path(observation_path))
        return

    if mode == "x_saved_stock_deep_dive_handoff":
        from pathlib import Path
        from x_discovery.stock_deep_dive_handoff import StockHandoffError, run_from_paths
        candidate_path = os.environ.get("AIIF_X_SAVED_CANDIDATE_PATH", "").strip()
        calibration_path = os.environ.get("AIIF_X_CALIBRATION_OBSERVATION_PATH", "").strip()
        stock_path = os.environ.get("AIIF_X_STOCK_OBSERVATION_PATH", "").strip()
        if not all((candidate_path, calibration_path, stock_path)):
            raise StockHandoffError("candidate, Calibration and Stock paths are required")
        run_from_paths(pipeline, Path(candidate_path), Path(calibration_path), Path(stock_path))
        return

    # One non-persistent Deep Dive generation proof from the already persisted Stock.
    # Screening, Calibration and Stock persistence are never re-run here. The operation
    # owns a durable create-only claim and permits exactly one model request, no Quality
    # Retry, no Gemini URL/Search tools, no Notion write, and no publication.
    if mode == "x_saved_stock_deep_dive_once":
        from pathlib import Path
        from x_discovery.deep_dive_once import DeepDiveOnceError, run_from_paths
        candidate_path = os.environ.get("AIIF_X_SAVED_CANDIDATE_PATH", "").strip()
        calibration_path = os.environ.get("AIIF_X_CALIBRATION_OBSERVATION_PATH", "").strip()
        stock_path = os.environ.get("AIIF_X_STOCK_OBSERVATION_PATH", "").strip()
        if not all((candidate_path, calibration_path, stock_path)):
            raise DeepDiveOnceError("candidate, Calibration and Stock paths are required")
        run_from_paths(pipeline, Path(candidate_path), Path(calibration_path), Path(stock_path))
        return

    if not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)):
        runtime_state_channel.preflight_runtime_state_channel()

    run179_eyecatch_font_refinement.ensure_google_font_assets(
        enabled=not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)),
        logger=getattr(pipeline, "logger", None),
    )

    install_performance_telemetry(pipeline)

    if mode == "current_policy_ready_recovery":
        run_current_policy_ready_recovery(pipeline)
        return
    if mode == "article_validation":
        run_article_revalidation(pipeline)
        return
    if mode == "pending_retry_validation":
        run_article_revalidation(pipeline, pending_only=True)
        return
    if mode == "full":
        install_full_recovery(pipeline)

    pipeline.main()


def _run_product_review_runtime() -> None:
    import pipeline
    import run203_runtime_state_channel as runtime_state_channel
    install_product_review_provider_runtime(pipeline)
    if not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)):
        runtime_state_channel.preflight_runtime_state_channel()
    pipeline.main()


if __name__ == "__main__":
    main()
