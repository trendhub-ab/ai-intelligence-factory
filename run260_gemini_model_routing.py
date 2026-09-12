"""Run260/261/278/371: bounded Gemini primary / quality-repair routing.

Business goal
-------------
Improve Ready yield without weakening Fact/Evidence/Publication/Reader gates and
without increasing the existing Deep Dive request ceiling. Fresh article Deep Dive
uses Gemini 3.7 first by default. Dynamic model-based quality repair uses Gemini 3.8
first. Gemini 3.6 and 3.5 remain fallbacks.

Run261 production evidence proved that wrapping only ``_call_model_pool`` was not a
strong enough contract: the live quality-retry path is entered through
``_call_deep_dive_pool``. Therefore this layer enforces the same routing there.

Run278 production falsification found a different failure tail: a *single logical*
quality repair could fan out across all four Flash models and consume 4/12 Deep Dive
requests while a usable draft already existed. Quality repair is therefore bounded to
the preferred model plus one distinct fallback (2 provider-visible model attempts).
Fresh Deep Dive keeps the full pool.

Run371 fixes an operator-order bug exposed by bounded Pending Retry recovery. The old
install path always prepended ``DEFAULT_DEEP_DIVE_POOL`` after reading explicit config,
so an operator request for 3.8-first still executed 3.7-first. Production now keeps the
established 3.7-first default when there is no explicit override, while an explicit
configured pool keeps its exact order and only appends missing default fallbacks after
that order. Quotas, per-model budgets, request ceilings, and Gate policy are unchanged.
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
QUALITY_RETRY_MAX_DISTINCT_MODELS = 2


def _dedupe(models: Iterable[str]) -> list[str]:
    out: list[str] = []
    for raw in models:
        model = str(raw or "").strip()
        if model and model not in out:
            out.append(model)
    return out


def _configured_deep_dive_pool(pipeline_module: Any) -> tuple[list[str], bool]:
    """Return configured pool plus whether it is an explicit operator override.

    The pre-Run260 core default is a singleton 3.6 pool. Treat only that exact value
    (or an empty value) as implicit. Any other non-empty ordering is explicit and must
    retain operator order. Missing Run260 defaults are appended later as fallbacks.
    """
    configured = _dedupe(getattr(pipeline_module, "DEEP_DIVE_MODEL_POOL", []) or [])
    if not configured or configured == ["gemini-3.6-flash"]:
        return list(DEFAULT_DEEP_DIVE_POOL), False
    return configured, True


def _production_pool(pipeline_module: Any) -> list[str]:
    configured, explicit = _configured_deep_dive_pool(pipeline_module)
    if not explicit:
        return _dedupe(DEFAULT_DEEP_DIVE_POOL)
    return _dedupe([*configured, *DEFAULT_DEEP_DIVE_POOL])


def _quality_first_pool(pool: Iterable[str]) -> list[str]:
    """Prefer 3.8 only for an already-authorized model-based repair call."""
    existing = _dedupe(pool)
    preferred = [QUALITY_MODEL, *FALLBACK_MODELS, PRIMARY_MODEL]
    return _dedupe([m for m in preferred if m in existing] + existing)


def _bounded_quality_pool(pool: Iterable[str]) -> list[str]:
    """Keep one preferred repair model plus one distinct fallback.

    This is a *routing* bound, not a request budget. Provider-visible failures remain
    counted by the existing counters and Run172 still decides transport retry/failover.
    """
    return _quality_first_pool(pool)[:QUALITY_RETRY_MAX_DISTINCT_MODELS]


def _is_quality_repair_kind(kind: str) -> bool:
    value = str(kind or "").strip().lower()
    return value == "quality_retry" or any(
        token in value for token in ("quality_repair", "quality_rescue", "recompose", "reader_repair")
    )


def _replace_pool_argument(args: tuple, kwargs: dict, new_pool: list[str]) -> tuple[tuple, dict]:
    if "pool" in kwargs:
        updated = dict(kwargs)
        updated["pool"] = new_pool
        return args, updated
    if len(args) >= 5:
        values = list(args)
        values[4] = new_pool
        return tuple(values), kwargs
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
    """Install bounded routing without changing any existing request/gate budget."""
    if bool(getattr(pipeline_module, _INSTALLED_ATTR, False)):
        return pipeline_module

    original = getattr(pipeline_module, "_call_model_pool", None)
    original_deep_dive = getattr(pipeline_module, "_call_deep_dive_pool", None)
    if not callable(original):
        raise RuntimeError("pipeline._call_model_pool is required for Run260")
    if not callable(original_deep_dive):
        raise RuntimeError("pipeline._call_deep_dive_pool is required for Run261")

    production_pool = _production_pool(pipeline_module)
    pipeline_module.DEEP_DIVE_MODEL_POOL = production_pool
    pipeline_module.DEEP_DIVE_MODEL_CANDIDATES = list(production_pool)

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
            args2, kwargs2 = _replace_pool_argument(args, kwargs, _bounded_quality_pool(current_pool))
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
        if not _is_quality_repair_kind(kind):
            return original_deep_dive(
                prompt,
                config,
                kind,
                request_context=request_context,
                request_origin=request_origin,
            )
        quality_pool = _bounded_quality_pool(
            getattr(pipeline_module, "DEEP_DIVE_MODEL_POOL", production_pool)
        )
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
    pipeline_module.QUALITY_RETRY_MAX_DISTINCT_MODELS = QUALITY_RETRY_MAX_DISTINCT_MODELS
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
