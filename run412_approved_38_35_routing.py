"""Run412: temporary approved-lane routing through operator-confirmed free capacity.

This overlay is active only when the explicit owner-approved Run399 workflow sets
``ARTICLE_REVALIDATION_AVAILABLE_MODEL_POOL``. It changes no normal Production route.
For the current RubyGems apply the operator confirmed Gemini 3.8 and 3.5 capacity is
available, while 3.7/3.6 should not be used.
"""
from __future__ import annotations

import os
from typing import Any

import run260_gemini_model_routing as routing

_INSTALLED_ATTR = "_run412_approved_38_35_routing_installed"
APPROVED_ORIGIN = "approved_article_apply"
ENV_KEY = "ARTICLE_REVALIDATION_AVAILABLE_MODEL_POOL"
ALLOWED_MODELS = {"gemini-3.8-flash", "gemini-3.5-flash"}


def _configured_pool() -> list[str]:
    raw = os.environ.get(ENV_KEY, "").strip()
    if not raw:
        return []
    models: list[str] = []
    for value in raw.split(","):
        model = value.strip()
        if model and model not in models:
            models.append(model)
    if not models or any(model not in ALLOWED_MODELS for model in models):
        raise RuntimeError("Run412 available model pool contains an unapproved model")
    return models


def install(pipeline_module: Any) -> Any:
    if bool(getattr(pipeline_module, _INSTALLED_ATTR, False)):
        return pipeline_module

    configured = _configured_pool()
    if not configured:
        return pipeline_module

    original = getattr(pipeline_module, "_call_deep_dive_pool", None)
    call_model_pool = getattr(pipeline_module, "_call_model_pool", None)
    if not callable(original) or not callable(call_model_pool):
        raise RuntimeError("Run412 requires installed Deep Dive/provider routing")

    primary_pool = list(configured)
    repair_pool = list(reversed(configured)) if configured == ["gemini-3.8-flash", "gemini-3.5-flash"] else list(configured)

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

        pool = repair_pool if routing._is_quality_repair_kind(kind) else primary_pool
        logger = getattr(pipeline_module, "logger", None)
        if logger is not None:
            logger.info(
                "[RUN412 APPROVED AVAILABLE ROUTE] kind=%s pool=%s normal_routing_unchanged=true",
                kind,
                ",".join(pool),
            )

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
    pipeline_module.RUN412_APPROVED_AVAILABLE_MODELS = tuple(primary_pool)
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
