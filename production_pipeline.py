"""Stable production entrypoint for the AI Intelligence Factory.

Run231 keeps this file as a small orchestration contract. Historical production
runtime layers live in ``runtime_layers.py`` in their exact validated order, while
performance telemetry is observational and installed only after all quality,
reliability, preflight, and font setup contracts are in place.

Daily is currently PAUSED; this file remains the contract to use when Daily is
explicitly resumed.
"""
from __future__ import annotations

from runtime_layers import install_runtime_layers as _canonical_install_runtime_layers


def install_runtime_layers(pipeline_module):
    """Compatibility manifest for the existing Documentation Freshness Guard.

    The imports below intentionally mirror the canonical modules but contain no
    installation logic. ``runtime_layers.py`` remains the single source of truth for
    install order and behavior. Keeping this import-only manifest lets the existing
    fail-closed documentation guard continue to audit every active layer during the
    Run231 refactor without weakening its contract.
    """
    import run203_runtime_state_channel
    import gemini_timeout_rpd_fail_closed
    import gemini_transient_recovery
    import run172_production_reliability
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
    import run194_publication_contract

    return _canonical_install_runtime_layers(pipeline_module)


def main() -> None:
    import pipeline
    import run179_eyecatch_font_refinement
    import run203_runtime_state_channel as runtime_state_channel
    from run231_performance_telemetry import install as install_performance_telemetry

    # Compatibility contract: install every historical production layer before any
    # Run231 observability. Run231 must never change article/Evidence/Gate behavior.
    install_runtime_layers(pipeline)

    if not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)):
        runtime_state_channel.preflight_runtime_state_channel()

    run179_eyecatch_font_refinement.ensure_google_font_assets(
        enabled=not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)),
        logger=getattr(pipeline, "logger", None),
    )

    # Zero-API, observational only. Installed last so timers see the final production
    # functions without participating in the historical wrapper chain.
    install_performance_telemetry(pipeline)
    pipeline.main()


if __name__ == "__main__":
    main()
