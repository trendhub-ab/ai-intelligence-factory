"""Fail-closed Gemini RPD accounting for transport timeouts.

Google AI Studio provider-side RPD telemetry showed that requests ending in a client-side
transport/watchdog timeout can still count against the provider's daily request quota. The
legacy reconciliation path released those unobserved reservations, making the repository-local
counter optimistic versus the provider.

Run209 deliberately changes only that accounting behavior:
- the existing per-model daily safety budgets remain authoritative (18 for Flash in Production);
- timeout reservations are kept instead of decremented;
- 429/503 and all other provider-visible errors were already counted and remain unchanged;
- model selection, retry budgets, quality gates, publication policy, and Daily PAUSED are untouched.

This is installed as infrastructure by ``production_pipeline.install_runtime_layers`` after the
runtime-state channel is installed, so both normal Production and the Pending Retry fast lane use
the same conservative accounting contract.
"""
from __future__ import annotations

from typing import Any


def install(pipeline_module: Any):
    """Replace timeout reservation release with a fail-closed no-op on the live counter.

    ``pipeline._generate_via_chat`` calls ``PERSISTENT_GEMINI_COUNTER.release_unobserved`` only
    for transport/watchdog timeout families. Keeping the reservation here therefore makes the
    repository-local RPD counter conservative without changing the underlying counter schema or
    the configured daily budget.
    """
    counter = getattr(pipeline_module, "PERSISTENT_GEMINI_COUNTER", None)
    if counter is None:
        raise RuntimeError("Run209 requires PERSISTENT_GEMINI_COUNTER")

    if bool(getattr(counter, "_run209_timeout_rpd_fail_closed_installed", False)):
        return pipeline_module

    original_release = getattr(counter, "release_unobserved", None)
    if not callable(original_release):
        raise RuntimeError("Run209 requires release_unobserved on persistent Gemini counter")

    setattr(counter, "_run209_original_release_unobserved", original_release)

    def keep_timeout_reservation(kind: str, model_name: str = "default") -> None:
        logger = getattr(pipeline_module, "logger", None)
        if logger is not None:
            logger.warning(
                "[GEMINI RPD FAIL-CLOSED] timeout reservation kept "
                "model=%s kind=%s; configured daily safety budget remains authoritative",
                model_name,
                kind,
            )
        return None

    counter.release_unobserved = keep_timeout_reservation
    setattr(counter, "_run209_timeout_rpd_fail_closed_installed", True)
    setattr(pipeline_module, "RUN209_TIMEOUT_RPD_FAIL_CLOSED", True)
    return pipeline_module
