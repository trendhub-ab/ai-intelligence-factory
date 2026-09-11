"""Canonical production runtime-layer installation order.

Run231 moves the production patch stack out of ``production_pipeline.py`` without
changing its behavior. The order below is a compatibility contract.
"""
from __future__ import annotations

RUNTIME_LAYER_ORDER = (
    "run203_runtime_state_channel.install",
    "gemini_timeout_rpd_fail_closed.install",
    "gemini_transient_recovery.install",
    "run260_gemini_model_routing.install",
    "run172_production_reliability.install",
    "gemini_provider_resilience.install",
    "run173_operational_yield.install",
    "run174_monthly_digest_integrity.install",
    "run175_semantic_fact_precision.install",
    "run223_technical_claim_precision.install",
    "run224_multiplier_deterministic_rescue.install",
    "run227_japanese_surface_integrity.install",
    "run176_scope_fidelity.install",
    "run177_paid_funnel_alignment.install",
    "run226_reader_delight_planning.install",
    "run228_reader_rhythm_planning.install",
    "run178_eyecatch_editorial_layout_optimizer.install",
    "run179_eyecatch_font_refinement.install",
    "run180_eyecatch_semantic_layout.install",
    "run181_eyecatch_visual_balance.install",
    "run182_eyecatch_conclusion_emphasis.install",
    "run183_eyecatch_emphasis_scale.install",
    "reader_value_review_bridge.install",
    "run208_reader_value_repair.install",
    "run222_note_presentation_integrity.install_pipeline",
    "run296_editorial_format_v2.install",
    "run248_first_real_publish_quality_calibration.install",
    "run249_final_publication_surface_gate.install",
    "run194_publication_contract.install",
    "run346_backlog_budget_reserve.install",
)


def install_runtime_layers(pipeline_module):
    """Install every validated production layer in the historical canonical order."""
    import run203_runtime_state_channel as runtime_state_channel
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
    import run346_backlog_budget_reserve

    runtime_state_channel.install(pipeline_module)
    gemini_timeout_rpd_fail_closed.install(pipeline_module)
    gemini_transient_recovery.install(pipeline_module)
    run260_gemini_model_routing.install(pipeline_module)
    run172_production_reliability.install(pipeline_module)
    gemini_provider_resilience.install(pipeline_module)
    run173_operational_yield.install(pipeline_module)
    run174_monthly_digest_integrity.install(pipeline_module)
    run175_semantic_fact_precision.install(pipeline_module)
    run223_technical_claim_precision.install(pipeline_module)
    run224_multiplier_deterministic_rescue.install(pipeline_module)
    run227_japanese_surface_integrity.install(pipeline_module)
    run176_scope_fidelity.install(pipeline_module)
    run177_paid_funnel_alignment.install(pipeline_module)
    run226_reader_delight_planning.install(pipeline_module)
    run228_reader_rhythm_planning.install(pipeline_module)
    run178_eyecatch_editorial_layout_optimizer.install(pipeline_module)
    run179_eyecatch_font_refinement.install(pipeline_module)
    run180_eyecatch_semantic_layout.install(pipeline_module)
    run181_eyecatch_visual_balance.install(pipeline_module)
    run182_eyecatch_conclusion_emphasis.install(pipeline_module)
    run183_eyecatch_emphasis_scale.install(pipeline_module)
    reader_value_review_bridge.install(pipeline_module)
    run208_reader_value_repair.install(pipeline_module)
    run222_note_presentation_integrity.install_pipeline(pipeline_module)
    run296_editorial_format_v2.install(pipeline_module)
    run248_first_real_publish_quality_calibration.install(pipeline_module)
    run249_final_publication_surface_gate.install(pipeline_module)
    run194_publication_contract.install(pipeline_module)

    # Run346 is budget partitioning only. Install last so it sees the final canonical
    # backlog helper and final Deep Dive budget object. It does not alter gates/routing.
    run346_backlog_budget_reserve.install(pipeline_module)
    return pipeline_module
