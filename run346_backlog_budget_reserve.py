"""Run346/374: partition existing Deep Dive budget across fresh, backlog, and Ready Rescue.

Fresh generation must not consume capacity required by Deferred/Pending recovery. Run374
reserves one Ready Rescue request for an already-persisted Needs Editorial Review article.
The slot may be consumed by the preflight rescue before Fresh; if it is not consumed, it
remains withheld for the historical final rescue after backlog. All capacity is carved from
the existing per-run cap; this layer never adds Gemini calls or raises the original budget.
"""
from __future__ import annotations

import os
from functools import wraps

_INSTALLED_ATTR = "_run346_backlog_budget_reserve_installed"
_ORIGINAL_BUDGET_ATTR = "_run346_original_deep_dive_budget"
_READY_RESCUE_RESERVE_ATTR = "_run374_ready_rescue_reserved_requests"
_READY_RESCUE_CONSUMED_ATTR = "_run374_ready_rescue_slot_consumed"
_DEFAULT_READY_RESCUE_RESERVE = 1


def _reserve_requests(pipeline) -> int:
    pending = max(0, int(getattr(pipeline, "GEMINI_PENDING_RETRY_REQUEST_BUDGET", 0) or 0))
    deferred = max(0, int(getattr(pipeline, "DEFERRED_DEEP_DIVE_MAX_PER_RUN", 0) or 0))
    configured = os.environ.get("GEMINI_BACKLOG_RESERVED_REQUESTS", "").strip()
    if configured:
        return max(0, int(configured))
    return pending + deferred


def _ready_rescue_requests() -> int:
    configured = os.environ.get("GEMINI_READY_RESCUE_RESERVED_REQUESTS", "").strip()
    if configured:
        return max(0, int(configured))
    return _DEFAULT_READY_RESCUE_RESERVE


def install(pipeline):
    if getattr(pipeline, _INSTALLED_ATTR, False):
        return pipeline
    budget = getattr(pipeline, "DEEP_DIVE_MODEL_BUDGET", None)
    original_backlog = getattr(pipeline, "process_article_backlog", None)
    if budget is None or not callable(original_backlog):
        if getattr(pipeline, "__file__", None):
            raise RuntimeError("Run346 requires DEEP_DIVE_MODEL_BUDGET and process_article_backlog")
        return pipeline

    original_cap = max(0, int(getattr(budget, "budget", 0) or 0))
    backlog_reserve = min(original_cap, _reserve_requests(pipeline))
    rescue_reserve = min(max(0, original_cap - backlog_reserve), _ready_rescue_requests())
    fresh_cap = max(0, original_cap - backlog_reserve - rescue_reserve)
    backlog_cap = max(0, original_cap - rescue_reserve)
    setattr(pipeline, _ORIGINAL_BUDGET_ATTR, original_cap)
    setattr(pipeline, _READY_RESCUE_RESERVE_ATTR, rescue_reserve)
    setattr(pipeline, _READY_RESCUE_CONSUMED_ATTR, False)
    budget.budget = fresh_cap
    logger = getattr(pipeline, "logger", None)
    if logger:
        logger.info(
            "[RUN346 BUDGET PARTITION] total=%s fresh=%s backlog_reserve=%s ready_rescue=%s (no quota increase)",
            original_cap, fresh_cap, backlog_reserve, rescue_reserve,
        )

    @wraps(original_backlog)
    def process_article_backlog_with_reserved_budget(pending_items, generated_count, next_candidate_rank):
        # If preflight already spent Ready Rescue, its one request is no longer withheld and
        # the backlog can use the full remaining cumulative cap. Otherwise keep that final
        # rescue request reserved exactly as before.
        rescue_consumed = bool(getattr(pipeline, _READY_RESCUE_CONSUMED_ATTR, False))
        effective_backlog_cap = original_cap if rescue_consumed else backlog_cap
        budget.budget = effective_backlog_cap
        if logger:
            logger.info(
                "[RUN346 BACKLOG RELEASE] used=%s backlog_cap=%s total_cap=%s ready_rescue=%s consumed=%s pending=%s",
                getattr(budget, "used", 0), effective_backlog_cap, original_cap, rescue_reserve,
                rescue_consumed, len(pending_items or []),
            )
        result = original_backlog(pending_items, generated_count, next_candidate_rank)
        # The outer Run374 wrapper may spend the withheld slot only when preflight did not.
        budget.budget = original_cap
        return result

    pipeline.process_article_backlog = process_article_backlog_with_reserved_budget

    # Install after Run346 so Run374 sees the partitioned Fresh cap, can offer its single
    # preflight slot before main(), and can still wrap the final backlog surface.
    import run374_ready_rescue
    run374_ready_rescue.install(pipeline)

    setattr(pipeline, _INSTALLED_ATTR, True)
    return pipeline
