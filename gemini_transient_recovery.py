"""Bounded recovery policy for transient Gemini provider outages.

HTTP 503 is transient, so a single occurrence must not permanently blacklist a
model for the whole run. Production evidence from ONE-SHOT #14 also proved the
opposite extreme is too expensive: repeatedly re-probing the same 503ing model
can consume scarce daily requests without producing a Ready article.

Default Production policy:
- first 503 for a model -> fallback for the current candidate, keep the model
  eligible for one later recovery probe in the same run;
- second 503 for the same model -> place that model in run-local cooldown by
  delegating to the existing SESSION_UNAVAILABLE_MODELS guard;
- 404 / unsupported model -> hard session unavailable (unchanged);
- daily quota / persistent safety cap -> session exhausted (unchanged);
- repeated transport timeout circuit breaker -> session unavailable (unchanged).

Narrow validation entrypoints may lower the run-local 503 cooldown threshold when
their request budget is intentionally tiny. Lowering it never creates a new request
path; it only stops spending scarce repair capacity on a model that already returned
503 during that validation run. The normal Production default remains two occurrences.

This module is operational infrastructure, not publication policy. It is kept
outside the runNNN publication-layer namespace so transport-only changes do not
invalidate otherwise-current Ready manuscripts.
"""
from __future__ import annotations

from typing import Any

_INSTALL_FLAG = "_aiif_transient_503_recovery_installed"
_ORIGINAL_MARKER = "_aiif_original_mark_model_unavailable"
_COUNTER_ATTR = "_aiif_transient_503_counts"
_THRESHOLD_ATTR = "_aiif_transient_503_cooldown_threshold"
_DEFAULT_COOLDOWN_THRESHOLD = 2


def _is_transient_503(reason: Any) -> bool:
    text = str(reason or "").strip().lower()
    return text == "503" or text.startswith("503 ") or text.startswith("503:")


def configure_cooldown_threshold(pipeline_module: Any, threshold: int) -> Any:
    """Set a stricter run-local 503 cooldown threshold for a bounded entrypoint.

    Threshold must be at least one. The setting lives only on the in-process pipeline
    module, so it cannot persist across runs or weaken the normal Production default.
    """
    value = int(threshold)
    if value < 1:
        raise ValueError("503 cooldown threshold must be >= 1")
    setattr(pipeline_module, _THRESHOLD_ATTR, value)
    return pipeline_module


def _cooldown_threshold(pipeline_module: Any) -> int:
    try:
        return max(1, int(getattr(pipeline_module, _THRESHOLD_ATTR, _DEFAULT_COOLDOWN_THRESHOLD)))
    except (TypeError, ValueError):
        return _DEFAULT_COOLDOWN_THRESHOLD


def install(pipeline_module):
    """Allow bounded recovery after 503, then cool down the model."""
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        return pipeline_module

    original = getattr(pipeline_module, "_mark_model_unavailable", None)
    if not callable(original):
        raise RuntimeError("pipeline._mark_model_unavailable is required")

    setattr(pipeline_module, _ORIGINAL_MARKER, original)
    if not isinstance(getattr(pipeline_module, _COUNTER_ATTR, None), dict):
        setattr(pipeline_module, _COUNTER_ATTR, {})
    if not hasattr(pipeline_module, _THRESHOLD_ATTR):
        setattr(pipeline_module, _THRESHOLD_ATTR, _DEFAULT_COOLDOWN_THRESHOLD)

    def mark_model_unavailable(model_name: str, reason: str = "") -> None:
        if _is_transient_503(reason):
            counts = getattr(pipeline_module, _COUNTER_ATTR)
            counts[model_name] = int(counts.get(model_name, 0) or 0) + 1
            occurrence = counts[model_name]
            threshold = _cooldown_threshold(pipeline_module)
            logger = getattr(pipeline_module, "logger", None)

            if occurrence < threshold:
                if logger is not None:
                    logger.warning(
                        "[MODEL TRANSIENT 503] %s occurrence=%s threshold=%s; fallback for this candidate, "
                        "a later recovery probe remains eligible",
                        model_name,
                        occurrence,
                        threshold,
                    )
                # Do not add to SESSION_UNAVAILABLE_MODELS yet. The core caller
                # still breaks out of this model for the current candidate.
                return

            if logger is not None:
                logger.warning(
                    "[MODEL TRANSIENT COOLDOWN] %s occurrence=%s threshold=%s; "
                    "skip for rest of run",
                    model_name,
                    occurrence,
                    threshold,
                )
            # Reuse the existing run-local unavailable guard rather than creating
            # another model-selection mechanism. This is intentionally not quota
            # exhaustion and does not persist across runs.
            original(model_name, f"transient_503_cooldown:{occurrence}")
            return

        original(model_name, reason)

    pipeline_module._mark_model_unavailable = mark_model_unavailable
    setattr(pipeline_module, _INSTALL_FLAG, True)
    return pipeline_module
