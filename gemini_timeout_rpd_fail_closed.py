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

Run303 also corrects an observability inconsistency: pipeline._generate_via_chat still emits a
legacy "released unobserved timeout reservation" message after calling release_unobserved. Once
Run209 replaces that method with a no-op, the message is false. A narrow logger filter rewrites
only that stale message when the logger supports standard logging filters; lightweight test
loggers remain compatible and the accounting behavior itself is unchanged.
"""
from __future__ import annotations

from typing import Any


_STALE_RELEASE_PREFIX = "[GEMINI PERSISTENT RECONCILE] released unobserved timeout reservation"


class _Run209TimeoutLogConsistencyFilter:
    """Rewrite only the legacy timeout-release message after Run209 suppresses release."""

    def filter(self, record) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:
            return True
        if rendered.startswith(_STALE_RELEASE_PREFIX):
            record.msg = rendered.replace(
                "released unobserved timeout reservation",
                "release suppressed by Run209; timeout reservation kept",
                1,
            )
            record.args = ()
        return True


def install(pipeline_module: Any):
    """Replace timeout reservation release with a fail-closed no-op on the live counter."""
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

    logger = getattr(pipeline_module, "logger", None)
    add_filter = getattr(logger, "addFilter", None) if logger is not None else None
    if callable(add_filter) and not bool(getattr(logger, "_run303_timeout_log_filter_installed", False)):
        add_filter(_Run209TimeoutLogConsistencyFilter())
        try:
            setattr(logger, "_run303_timeout_log_filter_installed", True)
        except Exception:
            pass

    setattr(counter, "_run209_timeout_rpd_fail_closed_installed", True)
    setattr(pipeline_module, "RUN209_TIMEOUT_RPD_FAIL_CLOSED", True)
    return pipeline_module
