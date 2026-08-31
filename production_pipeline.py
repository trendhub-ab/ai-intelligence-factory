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
    import reader_value_review_bridge

    run172_production_reliability.install(pipeline_module)
    run173_operational_yield.install(pipeline_module)
    run174_monthly_digest_integrity.install(pipeline_module)
    run175_semantic_fact_precision.install(pipeline_module)
    reader_value_review_bridge.install(pipeline_module)
    return pipeline_module


def main() -> None:
    import pipeline

    install_runtime_layers(pipeline)
    pipeline.main()


if __name__ == "__main__":
    main()
