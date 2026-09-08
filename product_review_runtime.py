#!/usr/bin/env python3
"""Run Product Review with the production provider/quota reliability contract.

Run305 closes a provider-resilience gap found by real ONE-SHOT Run38. The Daily
portfolio planner launched ``pipeline.py`` directly, so the product-only child did
not install the production runtime layers that own Gemini timeout accounting and
verified HTTP 503 handling.

This entrypoint is intentionally narrower than ``production_pipeline.py``:
- Run203 runtime-state isolation is installed so mutable quota state stays off main;
- Run209 timeout/RPD fail-closed accounting is installed;
- the existing transient-recovery layer remains active;
- Run303 provider-verified HTTP 503 handling is installed;
- article generation, publication, Reader Value, eyecatch, and model-routing layers
  are not installed here.

The Product Review workflow's explicit model order, max-review cap, and local Gemini
request budget therefore remain unchanged.
"""
from __future__ import annotations

from typing import Any


PRODUCT_REVIEW_PROVIDER_LAYER_ORDER = (
    "run203_runtime_state_channel.install",
    "gemini_timeout_rpd_fail_closed.install",
    "gemini_transient_recovery.install",
    "gemini_provider_resilience.install",
)


def install_product_review_provider_runtime(pipeline_module: Any) -> Any:
    """Install only provider/quota layers required by the product-only child."""
    import run203_runtime_state_channel
    import gemini_timeout_rpd_fail_closed
    import gemini_transient_recovery
    import gemini_provider_resilience

    run203_runtime_state_channel.install(pipeline_module)
    gemini_timeout_rpd_fail_closed.install(pipeline_module)
    gemini_transient_recovery.install(pipeline_module)
    gemini_provider_resilience.install(pipeline_module)
    return pipeline_module


def main() -> None:
    import pipeline

    install_product_review_provider_runtime(pipeline)
    pipeline.main()


if __name__ == "__main__":
    main()
