"""Run260/261/278/371/373/374: bounded Gemini primary / quality-repair routing.

Business goal
-------------
Improve Ready yield without weakening Fact/Evidence/Publication/Reader gates and
without increasing the existing Deep Dive request ceiling. Fresh article Deep Dive
uses Gemini 3.7 first by default. Dynamic model-based quality repair uses Gemini 3.8
first. Gemini 3.6 and 3.5 remain fallbacks unless an operator explicitly excludes a
model for a Pending Retry lane.

Run261 production evidence proved that wrapping only ``_call_model_pool`` was not a
strong enough contract: the live quality-retry path is entered through
``_call_deep_dive_pool``. Therefore this layer enforces the same routing there.

Run278 production falsification found a different failure tail: a *single logical*
quality repair could fan out across all four Flash models and consume 4/12 Deep Dive
requests while a usable draft already existed. Quality repair is therefore bounded to
the preferred model plus one distinct fallback (2 provider-visible model attempts).
Fresh Deep Dive keeps the full pool.

Run371 fixes an operator-order bug exposed by bounded Pending Retry recovery. Explicit
operator model order is preserved exactly before missing default fallbacks are appended.
Run373 additionally distinguishes the historical core three-model pool from a real
operator override: that legacy default is implicit and must still normalize to the
canonical 3.7 -> 3.8 -> 3.6 -> 3.5 fresh Deep Dive order.

Run374 fixes the interaction between bounded quality-repair routing and the operator
Pending Retry exclusion list. Excluded models are removed *before* the two-model quality
pool is sliced, so an excluded 3.6 cannot consume the only fallback slot and prevent
3.5 from being tried.
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
LEGACY_IMPLICIT_DEEP_DIVE_POOLS = (
    ("gemini-3.6-flash",),
    ("gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.5-flash"),
)
_PENDING_RETRY_ORIGINS = frozenset({"pending_retry", "pending_retry_validation"})
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
    """Return configured pool plus whether it is an explicit operator override."""
    configured = _dedupe(getattr(pipeline_module, "DEEP_DIVE_MODEL_POOL", []) or [])
    configured_tuple = tuple(configured)
    if not configured or configured_tuple in LEGACY_IMPLICIT_DEEP_DIVE_POOLS:
        return list(DEFAULT_DEEP_DIVE_POOL), False
    return configured, True


def _production_pool(pipeline_module: Any) -> list[str]:
    configured, explicit = _configured_deep_dive_pool(pipeline_module)
    if not explicit:
        return _dedupe(DEFAULT_DEEP_DIVE_POOL)
    return _dedupe([*configured, *DEFAULT_DEEP_DIVE_POOL])


def _quality_first_pool(pool: Iterable[str]) -> list[str]:
    existing = _dedupe(pool)
    preferred = [QUALITY_MODEL, *FALLBACK_MODELS, PRIMARY_MODEL]
    return _dedupe([m for m in preferred if m in existing] + existing)


def _bounded_quality_pool(pool: Iterable[str]) -> list[str]:
    return _quality_first_pool(pool)[:QUALITY_RETRY_MAX_DISTINCT_MODELS]


def _pending_retry_excluded_models(request_origin: str) -> frozenset[str]:
    if str(request_origin or "").strip() not in _PENDING_RETRY_ORIGINS:
        return frozenset()
    raw = str(os.environ.get("GEMINI_PENDING_RETRY_EXCLUDED_MODELS", "") or "")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def _pool_after_pending_exclusions(pool: Iterable[str], request_origin: str) -> list[str]:
    excluded = _pending_retry_excluded_models(request_origin)
    if not excluded:
        return _dedupe(pool)
    return [model for model in _dedupe(pool) if model not in excluded]


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


def _request_origin(args: tuple, kwargs: dict) -> str:
    if "request_origin" in kwargs:
        return str(kwargs.get("request_origin") or "new")
    return "new"


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
            origin = _request_origin(args, kwargs)
            eligible_pool = _pool_after_pending_exclusions(current_pool, origin)
            args2, kwargs2 = _replace_pool_argument(args, kwargs, _bounded_quality_pool(eligible_pool))
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
        eligible_pool = _pool_after_pending_exclusions(
            getattr(pipeline_module, "DEEP_DIVE_MODEL_POOL", production_pool),
            request_origin,
        )
        quality_pool = _bounded_quality_pool(eligible_pool)
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
