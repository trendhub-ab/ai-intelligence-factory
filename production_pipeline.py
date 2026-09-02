"""Stable production entrypoint for the AI Intelligence Factory.

Install reliability layers in an explicit order, then enter the unchanged pipeline main.
Daily is currently PAUSED; this file is the contract to use when Daily is explicitly resumed.
"""
from __future__ import annotations


def install_runtime_layers(pipeline_module):
    import run203_runtime_state_channel as runtime_state_channel
    import gemini_transient_recovery
    import run172_production_reliability
    import run173_operational_yield
    import run174_monthly_digest_integrity
    import run175_semantic_fact_precision
    import run176_scope_fidelity
    import run177_paid_funnel_alignment
    import run178_eyecatch_editorial_layout_optimizer
    import run179_eyecatch_font_refinement
    import run180_eyecatch_semantic_layout
    import run181_eyecatch_visual_balance
    import run182_eyecatch_conclusion_emphasis
    import run183_eyecatch_emphasis_scale
    import reader_value_review_bridge
    import run194_publication_contract

    # Mutable operational state must be redirected before any production layer can
    # inspect or write it. Protected main remains code/provenance only. These infra
    # aliases are intentionally outside the publication-policy Run-layer manifest.
    runtime_state_channel.install(pipeline_module)
    # HTTP 503 is provider-transient: fall back for the current candidate but do not
    # blacklist the model for the whole run. Existing 404/quota/timeout guards remain.
    gemini_transient_recovery.install(pipeline_module)
    run172_production_reliability.install(pipeline_module)
    run173_operational_yield.install(pipeline_module)
    run174_monthly_digest_integrity.install(pipeline_module)
    run175_semantic_fact_precision.install(pipeline_module)
    run176_scope_fidelity.install(pipeline_module)
    run177_paid_funnel_alignment.install(pipeline_module)
    run178_eyecatch_editorial_layout_optimizer.install(pipeline_module)
    run179_eyecatch_font_refinement.install(pipeline_module)
    run180_eyecatch_semantic_layout.install(pipeline_module)
    run181_eyecatch_visual_balance.install(pipeline_module)
    run182_eyecatch_conclusion_emphasis.install(pipeline_module)
    run183_eyecatch_emphasis_scale.install(pipeline_module)
    reader_value_review_bridge.install(pipeline_module)
    # Stamp persisted Ready manuscripts only after every current article-quality and
    # eyecatch layer has been installed. Downstream note publication paths require this
    # exact contract and therefore cannot silently reuse historical Ready inventory.
    run194_publication_contract.install(pipeline_module)
    return pipeline_module


def main() -> None:
    import pipeline
    import run179_eyecatch_font_refinement
    import run203_runtime_state_channel as runtime_state_channel

    install_runtime_layers(pipeline)
    if not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)):
        # Prove GH_PAT can write the isolated state branch before any Gemini reserve.
        # This converts future protection/permission drift into a cheap preflight failure
        # instead of the misleading "no available model" symptom seen in Run202.
        runtime_state_channel.preflight_runtime_state_channel()
    run179_eyecatch_font_refinement.ensure_google_font_assets(
        enabled=not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)),
        logger=getattr(pipeline, "logger", None),
    )
    pipeline.main()


if __name__ == "__main__":
    main()
