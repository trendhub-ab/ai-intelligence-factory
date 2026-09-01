"""Stable production entrypoint for the AI Intelligence Factory.

Install reliability layers in an explicit order, then enter the unchanged pipeline main.
Daily is currently PAUSED; this file is the contract to use when Daily is explicitly resumed.
"""
from __future__ import annotations


def install_runtime_layers(pipeline_module):
    import run172_production_reliability
    import run173_operational_yield
    import run174_monthly_digest_integrity
    import run175_semantic_fact_precision
    import run176_scope_fidelity
    import run177_paid_funnel_alignment
    import run178_eyecatch_editorial_layout_optimizer
    import run179_eyecatch_font_refinement
    import reader_value_review_bridge

    run172_production_reliability.install(pipeline_module)
    run173_operational_yield.install(pipeline_module)
    run174_monthly_digest_integrity.install(pipeline_module)
    run175_semantic_fact_precision.install(pipeline_module)
    run176_scope_fidelity.install(pipeline_module)
    run177_paid_funnel_alignment.install(pipeline_module)
    run178_eyecatch_editorial_layout_optimizer.install(pipeline_module)
    run179_eyecatch_font_refinement.install(pipeline_module)
    reader_value_review_bridge.install(pipeline_module)
    return pipeline_module


def main() -> None:
    import pipeline
    import run179_eyecatch_font_refinement

    install_runtime_layers(pipeline)
    run179_eyecatch_font_refinement.ensure_google_font_assets(
        enabled=not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)),
        logger=getattr(pipeline, "logger", None),
    )
    pipeline.main()


if __name__ == "__main__":
    main()
