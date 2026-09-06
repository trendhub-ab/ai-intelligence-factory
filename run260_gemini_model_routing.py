"""Run260/261: bounded Gemini 3.7 primary / 3.8 quality-repair routing.

Business goal
-------------
Improve Ready yield without weakening Fact/Evidence/Publication/Reader gates and
without increasing the existing Deep Dive request ceiling. Fresh article Deep Dive
uses Gemini 3.7 first. Dynamic model-based quality repair uses Gemini 3.8 first.
Gemini 3.6 and 3.5 remain fallbacks. Existing deterministic zero-API rescue remains
untouched.

Run261 production evidence proved that wrapping only ``_call_model_pool`` was not a
strong enough contract: the live quality-retry path is entered through
``_call_deep_dive_pool``.  Therefore this layer now enforces the same bounded routing
at that actual production entrypoint as well.  It still creates no new provider call
path, retry loop, budget, gate change, or publication action.
"""
from __future__ import annotations

import os
from typing import Any, Iterable

_INSTALLED_ATTR = "_run260_gemini_model_routing_installed"
_ORIGINAL_CALL_ATTR = "_run260_original_call_model_pool"
_ORIGINAL_DEEP_DIVE_ATTR = "_run261_original_call_deep_dive_pool"

PRIMARY_MODEL = "gemini-3.7-flash"
QUALITY_MODEL = "gemini-3.8-flash"
FALLBACK_MODELS = ("gemini-3.6-flash", "gemini-3.5-flash")
DEFAULT_DEEP_DIVE_POOL = (PRIMARY_MODEL, QUALITY_MODEL, *FALLBACK_MODELS)
DEFAULT_QUALITY_POOL = (QUALITY_MODEL, *FALLBACK_MODELS, PRIMARY_MODEL)
DEFAULT_FLASH_SAFETY_BUDGET = 18


def _dedupe(models: Iterable[str]) -> list[str]:
    out: list[str] = []
    for raw in models:
        model = str(raw or "").strip()
        if model and model not in out:
            out.append(model)
    return out


def _configured_deep_dive_pool(pipeline_module: Any) -> list[str]:
    """Use explicit Production config when present; otherwise use Run260 defaults."""
    configured = _dedupe(getattr(pipeline_module, "DEEP_DIVE_MODEL_POOL", []) or [])
    # The pre-Run260 code defaulted to a single 3.6 model when no workflow env existed.
    # Treat that legacy singleton as an implicit default, not an operator override.
    if configured == ["gemini-3.6-flash"]:
        return list(DEFAULT_DEEP_DIVE_POOL)
    return configured or list(DEFAULT_DEEP_DIVE_POOL)


def _quality_first_pool(pool: Iterable[str]) -> list[str]:
    """Prefer 3.8 only for an already-authorized model-based repair call."""
    existing = _dedupe(pool)
    preferred = [QUALITY_MODEL, *FALLBACK_MODELS, PRIMARY_MODEL]
    return _dedupe([m for m in preferred if m in existing] + existing)


def _is_quality_repair_kind(kind: str) -> bool:
    value = str(kind or "").strip().lower()
    # Current dynamic recomposition uses quality_retry. Keep narrow forward-compatible
    # labels for model-based repair/rescue without touching ordinary deep_dive calls.
    return value == "quality_retry" or any(
        token in value for token in ("quality_repair", "quality_rescue", "recompose", "reader_repair")
    )


def _replace_pool_argument(args: tuple, kwargs: dict, new_pool: list[str]) -> tuple[tuple, dict]:
    """Replace _call_model_pool's pool argument while preserving its public signature."""
    if "pool" in kwargs:
        updated = dict(kwargs)
        updated["pool"] = new_pool
        return args, updated
    if len(args) >= 5:
        values = list(args)
        values[4] = new_pool
        return tuple(values), kwargs
    # Defensive path for a future keyword-only call shape.
    updated = dict(kwargs)
    updated["pool"] = new_pool
    return args, updated


def _request_kind(args: tuple, kwargs: dict) -> str:
    if "kind" in kwargs:
        return str(kwargs.get("kind") or "")
    return str(args[2] if len(args) >= 3 else "")


def _request_pool(args: tuple, kwargs: dict, fallback: list[str]) -> list[str]:
    if "pool" in kwargs:
        return _dedupe(kwargs.get("pool") or fallback)
    if len(args) >= 5:
        return _dedupe(args[4] or fallback)
    return list(fallback)


def install(pipeline_module: Any) -> Any:
    """Install Run260/261 routing without changing any existing request/gate budget."""
    if bool(getattr(pipeline_module, _INSTALLED_ATTR, False)):
        return pipeline_module

    original = getattr(pipeline_module, "_call_model_pool", None)
    original_deep_dive = getattr(pipeline_module, "_call_deep_dive_pool", None)
    if not callable(original):
        raise RuntimeError("pipeline._call_model_pool is required for Run260")
    if not callable(original_deep_dive):
        raise RuntimeError("pipeline._call_deep_dive_pool is required for Run261")

    production_pool = _configured_deep_dive_pool(pipeline_module)
    # Run260's production contract requires the new primary/quality models. If an old
    # workflow supplies the historical pool, upgrade it deterministically while keeping
    # 3.6/3.5 as fallbacks. Explicit extra models remain after the canonical four.
    production_pool = _dedupe(list(DEFAULT_DEEP_DIVE_POOL) + production_pool)
    pipeline_module.DEEP_DIVE_MODEL_POOL = production_pool
    pipeline_module.DEEP_DIVE_MODEL_CANDIDATES = list(production_pool)

    # Gemini 3.8 has a Free Tier, but project-visible limits remain authoritative.
    # Keep the Factory's existing conservative 18-request Flash ceiling unless the
    # operator explicitly lowers it. Never raise above the established Flash safety cap.
    try:
        requested_budget = int(os.environ.get("GEMINI_38_FLASH_DAILY_BUDGET", str(DEFAULT_FLASH_SAFETY_BUDGET)))
    except (TypeError, ValueError):
        requested_budget = DEFAULT_FLASH_SAFETY_BUDGET
    quality_budget = max(0, min(DEFAULT_FLASH_SAFETY_BUDGET, requested_budget))

    model_budgets = getattr(pipeline_module, "MODEL_DAILY_BUDGETS", None)
    if isinstance(model_budgets, dict):
        model_budgets[QUALITY_MODEL] = quality_budget
    persistent = getattr(pipeline_module, "PERSISTENT_GEMINI_COUNTER", None)
    if persistent is not None and isinstance(getattr(persistent, "model_budgets", None), dict):
        persistent.model_budgets[QUALITY_MODEL] = quality_budget

    setattr(pipeline_module, _ORIGINAL_CALL_ATTR, original)
    setattr(pipeline_module, _ORIGINAL_DEEP_DIVE_ATTR, original_deep_dive)

    def call_model_pool_run260(*args, **kwargs):
        kind = _request_kind(args, kwargs)
        current_pool = _request_pool(args, kwargs, production_pool)
        if _is_quality_repair_kind(kind):
            args2, kwargs2 = _replace_pool_argument(args, kwargs, _quality_first_pool(current_pool))
            return original(*args2, **kwargs2)
        return original(*args, **kwargs)

    pipeline_module._call_model_pool = call_model_pool_run260

    def call_deep_dive_pool_run261(
        prompt: str,
        config: dict | None = None,
        kind: str = "deep_dive",
        request_context: str = "",
        request_origin: str = "new",
    ):
        """Enforce quality-first routing at the production Deep Dive entrypoint.

        This delegates exactly once to the existing model-pool caller. Its existing
        retry/fallback logic and the authoritative Deep Dive request counter remain the
        only mechanisms that can create provider attempts.
        """
        if not _is_quality_repair_kind(kind):
            return original_deep_dive(
                prompt,
                config,
                kind,
                request_context=request_context,
                request_origin=request_origin,
            )
        quality_pool = _quality_first_pool(getattr(pipeline_module, "DEEP_DIVE_MODEL_POOL", production_pool))
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

    pipeline_module._call_deep_dive_pool = call_deep_dive_pool_run261
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
