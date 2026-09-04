"""Stable production entrypoint for the AI Intelligence Factory.

Run231 keeps this file as a small orchestration contract.  Historical production
runtime layers live in ``runtime_layers.py`` in their exact validated order, while
performance telemetry is observational and installed only after all quality,
reliability, preflight, and font setup contracts are in place.

Daily is currently PAUSED; this file remains the contract to use when Daily is
explicitly resumed.
"""
from __future__ import annotations

from runtime_layers import install_runtime_layers


def main() -> None:
    import pipeline
    import run179_eyecatch_font_refinement
    import run203_runtime_state_channel as runtime_state_channel
    from run231_performance_telemetry import install as install_performance_telemetry

    # Compatibility contract: install every historical production layer before any
    # Run231 observability.  Run231 must never change article/Evidence/Gate behavior.
    install_runtime_layers(pipeline)

    if not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)):
        runtime_state_channel.preflight_runtime_state_channel()

    run179_eyecatch_font_refinement.ensure_google_font_assets(
        enabled=not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)),
        logger=getattr(pipeline, "logger", None),
    )

    # Zero-API, observational only.  Installed last so timers see the final production
    # functions without participating in the historical wrapper chain.
    install_performance_telemetry(pipeline)
    pipeline.main()


if __name__ == "__main__":
    main()
