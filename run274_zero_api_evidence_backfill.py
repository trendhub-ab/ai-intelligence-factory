"""Run274 — zero-API Evidence Backfill headroom.

Real Production showed that candidates rejected by Evidence preflight before any Gemini
request were still consuming ``MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS`` in ``pipeline.main``.
That reduced the chance of reaching an evidence-ready candidate even though no model
quota had been spent.

This compatibility layer does not add a provider call and does not relax any gate. When
(and only when) the existing funnel proves that a candidate increased
``deep_dive_calls_avoided`` during ``generate_intelligence_report``, it returns one unit
of bounded candidate-attempt headroom to the current run. Existing Gemini global,
per-model and Deep-Dive request budgets remain authoritative.
"""
from __future__ import annotations

import os
from typing import Any

_INSTALLED_ATTR = "_run274_zero_api_evidence_backfill_installed"
_COMPENSATIONS_ATTR = "_run274_zero_api_evidence_backfill_compensations"
_FUNNEL_ID_ATTR = "_run274_zero_api_evidence_backfill_funnel_id"
_BASE_CAP_ATTR = "_run274_zero_api_evidence_backfill_base_cap"
HEADROOM_ENV = "MAX_ZERO_API_EVIDENCE_BACKFILL_HEADROOM"


def _bounded_headroom() -> int:
    try:
        value = int(os.getenv(HEADROOM_ENV, "5"))
    except (TypeError, ValueError):
        value = 5
    return max(0, min(8, value))


def _persist_results(args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool:
    if "persist_results" in kwargs:
        return bool(kwargs["persist_results"])
    # generate_intelligence_report(repo, notion_page_id, screening_score,
    # screening_reason, persist_results, ...)
    if len(args) >= 5:
        return bool(args[4])
    return True


def install(pipeline_module: Any) -> Any:
    """Return bounded attempt headroom only for proven zero-model Evidence rejects."""
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original = pipeline_module.generate_intelligence_report
    base_cap = int(getattr(pipeline_module, "MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS", 7))
    setattr(pipeline_module, _BASE_CAP_ATTR, base_cap)
    setattr(pipeline_module, _COMPENSATIONS_ATTR, 0)
    setattr(pipeline_module, _FUNNEL_ID_ATTR, None)

    def wrapped_generate_intelligence_report(*args: Any, **kwargs: Any):
        if not _persist_results(args, kwargs):
            return original(*args, **kwargs)

        funnel = pipeline_module._active_gate_funnel(True)
        funnel_id = id(funnel) if funnel is not None else None
        previous_funnel_id = getattr(pipeline_module, _FUNNEL_ID_ATTR, None)
        if funnel_id != previous_funnel_id:
            # A new Production funnel means a new run in the same Python process.
            setattr(pipeline_module, _FUNNEL_ID_ATTR, funnel_id)
            setattr(pipeline_module, _COMPENSATIONS_ATTR, 0)
            setattr(pipeline_module, "MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS", base_cap)

        before_avoided = int((funnel.counters if funnel else {}).get("deep_dive_calls_avoided", 0))
        result = original(*args, **kwargs)
        after_avoided = int((funnel.counters if funnel else {}).get("deep_dive_calls_avoided", 0))

        if after_avoided > before_avoided:
            used = int(getattr(pipeline_module, _COMPENSATIONS_ATTR, 0))
            headroom = _bounded_headroom()
            if used < headroom:
                used += 1
                setattr(pipeline_module, _COMPENSATIONS_ATTR, used)
                new_cap = base_cap + used
                setattr(pipeline_module, "MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS", new_cap)
                logger = getattr(pipeline_module, "logger", None)
                if logger is not None:
                    logger.info(
                        "[RUN274 ZERO-API BACKFILL] Evidence preflight avoided Gemini; "
                        "candidate headroom returned %s/%s, effective_scan_cap=%s, model_attempt_cap=%s",
                        used, headroom, new_cap, base_cap,
                    )
        return result

    pipeline_module.generate_intelligence_report = wrapped_generate_intelligence_report
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
