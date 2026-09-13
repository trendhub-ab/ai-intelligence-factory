"""Run408: preserve approved-lane quality fallback across a pre-send model cap.

Real approved Run399 #10 reproduced a routing gap between Run260 and the persistent
Gemini counter. Run260 intentionally bounds one quality-repair call to two *configured
models* (3.7 then 3.6), but the persistent counter can reject 3.6 before any provider
request is sent. In that state the logical repair has consumed only one provider-visible
attempt, while the bounded list is already exhausted and an available 3.5 fallback is
never reached.

This overlay applies only to candidate_origin=approved_article_apply and only to
model-based quality/reader repair kinds. It reuses Run260's quality-first ordering but
passes the full configured production pool to the already-installed provider/budget
layer. All existing request budgets remain authoritative; a persistent-cap rejection
still consumes no local Deep Dive slot. Normal Daily/article_validation/pending_retry
keep Run260's historical two-configured-model bound.
"""
from __future__ import annotations

from typing import Any

import run260_gemini_model_routing as routing

_INSTALLED_ATTR = "_run408_approved_quality_fallback_installed"
APPROVED_ORIGIN = "approved_article_apply"


def install(pipeline_module: Any) -> Any:
    if bool(getattr(pipeline_module, _INSTALLED_ATTR, False)):
        return pipeline_module

    original = getattr(pipeline_module, "_call_deep_dive_pool", None)
    call_model_pool = getattr(pipeline_module, "_call_model_pool", None)
    if not callable(original) or not callable(call_model_pool):
        raise RuntimeError("Run408 requires installed Deep Dive/provider routing")

    def call_deep_dive_pool_with_approved_fallback(
        prompt: str,
        config: dict | None = None,
        kind: str = "deep_dive",
        request_context: str = "",
        request_origin: str = "new",
    ):
        origin = str(request_origin or "new").strip()
        if origin != APPROVED_ORIGIN or not routing._is_quality_repair_kind(kind):
            return original(
                prompt,
                config,
                kind,
                request_context=request_context,
                request_origin=request_origin,
            )

        configured = list(getattr(pipeline_module, "DEEP_DIVE_MODEL_POOL", []) or [])
        quality_pool = routing._quality_first_pool(configured)
        if not quality_pool:
            raise RuntimeError("Run408 approved quality pool is empty")

        logger = getattr(pipeline_module, "logger", None)
        if logger is not None:
            logger.info(
                "[RUN408 APPROVED QUALITY FALLBACK] kind=%s pool=%s budgets_unchanged=true",
                kind,
                ",".join(quality_pool),
            )

        # _call_model_pool is the final provider-resilience layer at this point. It owns
        # provider attempts, session circuits and all local/persistent budget checks.
        return pipeline_module._call_model_pool(
            prompt,
            config,
            kind,
            0,
            quality_pool,
            deep_dive=True,
            request_context=request_context,
            request_origin=request_origin,
        )

    pipeline_module._call_deep_dive_pool = call_deep_dive_pool_with_approved_fallback
    pipeline_module.RUN408_APPROVED_QUALITY_FALLBACK = True
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
