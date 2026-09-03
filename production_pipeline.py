"""Stable production entrypoint for the AI Intelligence Factory.

Install reliability layers in an explicit order, then enter the unchanged pipeline main.
Daily is currently PAUSED; this file is the contract to use when Daily is explicitly resumed.
"""
from __future__ import annotations


def install_runtime_layers(pipeline_module):
    import run203_runtime_state_channel as runtime_state_channel
    import gemini_timeout_rpd_fail_closed
    import gemini_transient_recovery
    import run172_production_reliability
    import run173_operational_yield
    import run174_monthly_digest_integrity
    import run175_semantic_fact_precision
    import run223_technical_claim_precision
    import run176_scope_fidelity
    import run177_paid_funnel_alignment
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

    runtime_state_channel.install(pipeline_module)
    # Provider RPD telemetry proved that transport timeouts can still consume daily quota.
    # Keep the pre-send reservation fail-closed while preserving the existing 18-request
    # per-model safety ceiling configured by the Production workflows.
    gemini_timeout_rpd_fail_closed.install(pipeline_module)
    gemini_transient_recovery.install(pipeline_module)
    run172_production_reliability.install(pipeline_module)
    run173_operational_yield.install(pipeline_module)
    run174_monthly_digest_integrity.install(pipeline_module)
    run175_semantic_fact_precision.install(pipeline_module)
    # Run223 extends semantic precision to method-specific parameters, scoped breaking changes,
    # benchmark/expectation multipliers, first-party dates and obvious Japanese particle damage.
    run223_technical_claim_precision.install(pipeline_module)
    run176_scope_fidelity.install(pipeline_module)
    run177_paid_funnel_alignment.install(pipeline_module)
    run178_eyecatch_editorial_layout_optimizer.install(pipeline_module)
    run179_eyecatch_font_refinement.install(pipeline_module)
    run180_eyecatch_semantic_layout.install(pipeline_module)
    run181_eyecatch_visual_balance.install(pipeline_module)
    run182_eyecatch_conclusion_emphasis.install(pipeline_module)
    run183_eyecatch_emphasis_scale.install(pipeline_module)
    reader_value_review_bridge.install(pipeline_module)
    # Reader-only dynamic repair is installed after the historical bridge so it can
    # selectively override only the bridge's reader_value_review_no_retry decision.
    run208_reader_value_repair.install(pipeline_module)
    # Run222 is presentation-only but publication-material: it moves the subscription CTA
    # after Sources/Evidence + disclaimer while leaving Evidence/Decision semantics unchanged.
    run222_note_presentation_integrity.install_pipeline(pipeline_module)
    run194_publication_contract.install(pipeline_module)
    return pipeline_module


def main() -> None:
    import pipeline
    import run179_eyecatch_font_refinement
    import run203_runtime_state_channel as runtime_state_channel

    install_runtime_layers(pipeline)
    if not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)):
        runtime_state_channel.preflight_runtime_state_channel()
    run179_eyecatch_font_refinement.ensure_google_font_assets(
        enabled=not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)),
        logger=getattr(pipeline, "logger", None),
    )
    pipeline.main()


if __name__ == "__main__":
    main()
