"""Bounded recovery policy for transient Gemini provider outages.

Google documents HTTP 503 as a temporary service-unavailable/overload condition.
The core pipeline already retries a model once, falls back across the configured
model pool, enforces per-run Deep Dive caps, persistent daily safety counters,
and a timeout circuit breaker.  Therefore a 503 must stop only the current
model attempt/candidate path; it must not permanently blacklist that model for
the rest of the run.

Hard unavailability remains unchanged:
- 404 / unsupported model -> session unavailable
- daily quota / persistent safety cap -> session exhausted
- repeated transport timeout circuit breaker -> session unavailable

This module is operational infrastructure, not publication policy.  It is kept
outside the runNNN publication-layer namespace so transport-only changes do not
invalidate otherwise-current Ready manuscripts.
"""
from __future__ import annotations

from typing import Any

_INSTALL_FLAG = "_aiif_transient_503_recovery_installed"
_ORIGINAL_MARKER = "_aiif_original_mark_model_unavailable"
_COUNTER_ATTR = "_aiif_transient_503_counts"


def _is_transient_503(reason: Any) -> bool:
    text = str(reason or "").strip().lower()
    return text == "503" or text.startswith("503 ") or text.startswith("503:")


def install(pipeline_module):
    """Keep 503 recoverable for later candidates while preserving hard guards."""
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        return pipeline_module

    original = getattr(pipeline_module, "_mark_model_unavailable", None)
    if not callable(original):
        raise RuntimeError("pipeline._mark_model_unavailable is required")

    setattr(pipeline_module, _ORIGINAL_MARKER, original)
    if not isinstance(getattr(pipeline_module, _COUNTER_ATTR, None), dict):
        setattr(pipeline_module, _COUNTER_ATTR, {})

    def mark_model_unavailable(model_name: str, reason: str = "") -> None:
        if _is_transient_503(reason):
            counts = getattr(pipeline_module, _COUNTER_ATTR)
            counts[model_name] = int(counts.get(model_name, 0) or 0) + 1
            logger = getattr(pipeline_module, "logger", None)
            if logger is not None:
                logger.warning(
                    "[MODEL TRANSIENT 503] %s occurrence=%s; "
                    "fallback for this candidate, eligible for bounded recovery later in run",
                    model_name,
                    counts[model_name],
                )
            # Intentionally do not add to SESSION_UNAVAILABLE_MODELS.  The caller
            # still breaks out of this model and falls back, so there is no hot loop.
            return
        original(model_name, reason)

    pipeline_module._mark_model_unavailable = mark_model_unavailable
    setattr(pipeline_module, _INSTALL_FLAG, True)
    return pipeline_module
