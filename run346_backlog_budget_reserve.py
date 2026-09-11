"""Run346: reserve existing Deep Dive budget for Deferred/Pending recovery.

Fresh generation could consume the full per-run Deep Dive cap before backlog recovery,
leaving Pending Retry with a dedicated budget but no shared model budget. This layer
partitions the existing cap; it never adds Gemini calls or raises the original cap.
"""
from __future__ import annotations

import os
from functools import wraps

_INSTALLED_ATTR = "_run346_backlog_budget_reserve_installed"
_ORIGINAL_BUDGET_ATTR = "_run346_original_deep_dive_budget"


def _reserve_requests(pipeline) -> int:
    pending = max(0, int(getattr(pipeline, "GEMINI_PENDING_RETRY_REQUEST_BUDGET", 0) or 0))
    deferred = max(0, int(getattr(pipeline, "DEFERRED_DEEP_DIVE_MAX_PER_RUN", 0) or 0))
    configured = os.environ.get("GEMINI_BACKLOG_RESERVED_REQUESTS", "").strip()
    if configured:
        return max(0, int(configured))
    return pending + deferred


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
    reserve = min(original_cap, _reserve_requests(pipeline))
    fresh_cap = max(0, original_cap - reserve)
    setattr(pipeline, _ORIGINAL_BUDGET_ATTR, original_cap)
    budget.budget = fresh_cap
    logger = getattr(pipeline, "logger", None)
    if logger:
        logger.info("[RUN346 BUDGET PARTITION] total=%s fresh=%s backlog_reserve=%s (no quota increase)", original_cap, fresh_cap, reserve)

    @wraps(original_backlog)
    def process_article_backlog_with_reserved_budget(pending_items, generated_count, next_candidate_rank):
        # Release only the withheld capacity. Used requests are never reset.
        budget.budget = original_cap
        if logger:
            logger.info("[RUN346 BACKLOG RELEASE] used=%s total_cap=%s pending=%s", getattr(budget, "used", 0), original_cap, len(pending_items or []))
        return original_backlog(pending_items, generated_count, next_candidate_rank)

    pipeline.process_article_backlog = process_article_backlog_with_reserved_budget
    setattr(pipeline, _INSTALLED_ATTR, True)
    return pipeline
