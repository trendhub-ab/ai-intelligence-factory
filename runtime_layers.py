"""Canonical production runtime-layer installation order.

Run231 moves the production patch stack out of ``production_pipeline.py`` without
changing its behavior.  The order below is a compatibility contract: later layers
intentionally wrap or refine functions installed by earlier layers.

Do not reorder, remove, or merge a layer here unless its own regression suite proves
that the resulting production behavior is equivalent or intentionally superseded.
"""
from __future__ import annotations


RUNTIME_LAYER_ORDER = (
    "run203_runtime_state_channel.install",
    "gemini_timeout_rpd_fail_closed.install",
    "gemini_transient_recovery.install",
    "run172_production_reliability.install",
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
    "run194_publication_contract.install",
)


def install_runtime_layers(pipeline_module):
    """Install every validated production layer in the historical canonical order."""
    import run203_runtime_state_channel as runtime_state_channel
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

    runtime_state_channel.install(pipeline_module)

    # Provider RPD telemetry proved that transport timeouts can still consume daily quota.
    # Keep the pre-send reservation fail-closed while preserving the existing per-model
    # safety ceilings configured by Production workflows.
    gemini_timeout_rpd_fail_closed.install(pipeline_module)
    gemini_transient_recovery.install(pipeline_module)
    run172_production_reliability.install(pipeline_module)
    run173_operational_yield.install(pipeline_module)
    run174_monthly_digest_integrity.install(pipeline_module)
    run175_semantic_fact_precision.install(pipeline_module)

    # Technical/factual precision stack.  Run224 is a zero-API deterministic rescue for
    # the narrow multiplier-scope failure detected by Run223; Run227 blocks only
    # high-confidence broken Japanese and delegates repair to the existing bounded path.
    run223_technical_claim_precision.install(pipeline_module)
    run224_multiplier_deterministic_rescue.install(pipeline_module)
    run227_japanese_surface_integrity.install(pipeline_module)
    run176_scope_fidelity.install(pipeline_module)
    run177_paid_funnel_alignment.install(pipeline_module)

    # Reader planning changes only the existing generation prompt.  These layers add no
    # model call and must remain in this order so Run228 refines the Run226 plan.
    run226_reader_delight_planning.install(pipeline_module)
    run228_reader_rhythm_planning.install(pipeline_module)

    # Eyecatch layers are deliberately ordered refinements of the same renderer.
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

    # Presentation-only but publication-material: keep CTA ordering after evidence and
    # disclaimer without changing Evidence/Decision semantics.
    run222_note_presentation_integrity.install_pipeline(pipeline_module)
    run194_publication_contract.install(pipeline_module)
    return pipeline_module
