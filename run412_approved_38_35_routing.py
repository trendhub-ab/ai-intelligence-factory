"""Run412: use only the operator-confirmed available Gemini 3.8/3.5 capacity.

Scope is the explicit owner-approved Run399 article-apply lane only.  The operator
confirmed two Gemini 3.8 Flash requests and thirteen Gemini 3.5 Flash requests remain
available for this execution.  3.7/3.6 are therefore excluded from this lane without
changing normal Production routing, model budgets, or any quality gate.

Fresh Deep Dive order: 3.8 -> 3.5.
Quality / Reader repair order: 3.5 -> 3.8, preserving the scarcer 3.8 capacity while
still keeping it as the distinct fallback.
"""
from __future__ import annotations

from typing import Any

import run260_gemini_model_routing as routing

_INSTALLED_ATTR = "_run412_approved_38_35_routing_installed"
APPROVED_ORIGIN = "approved_article_apply"
PRIMARY_POOL = ["gemini-3.8-flash", "gemini-3.5-flash"]
REPAIR_POOL = ["gemini-3.5-flash", "gemini-3.8-flash"]


def install(pipeline_module: Any) -> Any:
    if bool(getattr(pipeline_module, _INSTALLED_ATTR, False)):
        return pipeline_module

    original = getattr(pipeline_module, "_call_deep_dive_pool", None)
    call_model_pool = getattr(pipeline_module, "_call_model_pool", None)
    if not callable(original) or not callable(call_model_pool):
        raise RuntimeError("Run412 requires installed Deep Dive/provider routing")

    def call_deep_dive_pool_with_available_models(
        prompt: str,
        config: dict | None = None,
        kind: str = "deep_dive",
        request_context: str = "",
        request_origin: str = "new",
    ):
        origin = str(request_origin or "new").strip()
        if origin != APPROVED_ORIGIN:
            return original(
                prompt,
                config,
                kind,
                request_context=request_context,
                request_origin=request_origin,
            )

        pool = REPAIR_POOL if routing._is_quality_repair_kind(kind) else PRIMARY_POOL
        logger = getattr(pipeline_module, "logger", None)
        if logger is not None:
            logger.info(
                "[RUN412 APPROVED AVAILABLE ROUTE] kind=%s pool=%s normal_routing_unchanged=true",
                kind,
                ",".join(pool),
            )

        # Call the installed provider/model layer directly so 3.7/3.6 cannot be
        # reintroduced by the ordinary Deep Dive route. Existing per-run and persistent
        # counters remain authoritative. Run260 may only bound/reorder this two-model
        # set for repair kinds; it cannot add another model.
        return pipeline_module._call_model_pool(
            prompt,
            config,
            kind,
            0,
            list(pool),
            deep_dive=True,
            request_context=request_context,
            request_origin=request_origin,
        )

    pipeline_module._call_deep_dive_pool = call_deep_dive_pool_with_available_models
    pipeline_module.RUN412_APPROVED_AVAILABLE_MODELS = tuple(PRIMARY_POOL)
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
