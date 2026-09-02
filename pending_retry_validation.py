#!/usr/bin/env python3
"""Low-cost Production fast lane for recovering one high-value Pending Retry article.

This entrypoint exists for a narrow business goal: when the normal article pipeline
has already paid the collection/screening cost and a Deep Dive failed transiently,
do not spend another run discovering fresh candidates before attempting recovery.

Safety contract:
- installs the exact current Production runtime/publication layers;
- proves runtime-state writability before any Gemini reservation;
- caps this fast lane at three Pending Retry requests so one transient provider
  failure can still leave room for one generation and one quality recompose;
- cools a model for the rest of this fast-lane run after its first HTTP 503, while
  the normal Production Run205 policy remains unchanged at two occurrences;
- permits at most one Reader Value recompose, only when factual/evidence blockers
  are absent and the existing reader bridge reports repairable reader-only reasons;
- reuses the persistent daily counters and all global Deep Dive/provider caps;
- ranks the fetched Pending Retry backlog by screening score, while preserving the
  core query's stable order as the tie-breaker;
- stops immediately after the first successful article;
- never publishes to note.com; downstream Note Ready Sync remains fail-closed and
  public note release stays human-only.
"""
from __future__ import annotations

import os
from typing import Any, MutableMapping

FAST_LANE_PENDING_RETRY_REQUEST_BUDGET = 3
FAST_LANE_503_COOLDOWN_THRESHOLD = 1
FAST_LANE_ENV = "AIIF_PENDING_RETRY_FAST_LANE"


def prepare_fast_lane_env(env: MutableMapping[str, str] | None = None) -> MutableMapping[str, str]:
    """Pin narrow fast-lane controls before ``pipeline`` is imported."""
    target = env if env is not None else os.environ
    target["GEMINI_PENDING_RETRY_REQUEST_BUDGET"] = str(FAST_LANE_PENDING_RETRY_REQUEST_BUDGET)
    target[FAST_LANE_ENV] = "1"
    return target


def _score(item: dict[str, Any]) -> float:
    try:
        return float(item.get("screening_score") or 0)
    except (TypeError, ValueError):
        return 0.0


def prioritize_pending_items(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return sorted(list(items or []), key=_score, reverse=True)


def run_pending_retry_lane(pipeline_module, items: list[dict[str, Any]] | None, *, success_target: int = 1) -> dict[str, int]:
    attempted = 0
    succeeded = 0
    success_target = max(1, int(success_target or 1))

    for rank, item in enumerate(prioritize_pending_items(items), start=1):
        if succeeded >= success_target:
            break
        pending_budget = getattr(pipeline_module, "PENDING_RETRY_REQUEST_BUDGET")
        deep_budget = getattr(pipeline_module, "DEEP_DIVE_MODEL_BUDGET")
        run_budget = getattr(pipeline_module, "GEMINI_BUDGET")
        pool = getattr(pipeline_module, "DEEP_DIVE_MODEL_POOL")
        has_model = getattr(pipeline_module, "_model_pool_has_session_candidate")
        if not pending_budget.can_request():
            break
        if not deep_budget.can_request() or not run_budget.can_request() or not has_model(pool):
            break

        repo = item.get("repo") or {}
        name = repo.get("nameWithOwner") or "Pending Retry"
        logger = getattr(pipeline_module, "logger", None)
        if logger is not None:
            logger.info(
                "[PENDING RETRY FAST LANE] rank=%s score=%s candidate=%s",
                rank,
                item.get("screening_score"),
                name,
            )

        attempted += 1
        report = pipeline_module.generate_intelligence_report(
            repo,
            item.get("notion_page_id"),
            item.get("screening_score"),
            item.get("screening_reason", ""),
            candidate_rank=rank,
            candidate_origin="pending_retry",
        )
        if report:
            succeeded += 1

    return {"attempted": attempted, "succeeded": succeeded}


def main() -> int:
    prepare_fast_lane_env()

    import gemini_transient_recovery
    import pipeline
    import production_pipeline
    import run179_eyecatch_font_refinement
    import run203_runtime_state_channel as runtime_state_channel

    production_pipeline.install_runtime_layers(pipeline)
    gemini_transient_recovery.configure_cooldown_threshold(
        pipeline,
        FAST_LANE_503_COOLDOWN_THRESHOLD,
    )

    if not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)):
        runtime_state_channel.preflight_runtime_state_channel()
    run179_eyecatch_font_refinement.ensure_google_font_assets(
        enabled=not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)),
        logger=getattr(pipeline, "logger", None),
    )

    pipeline.reset_article_audit_for_production_run()
    pipeline.reset_article_style_memory()
    pipeline.initialize_runtime()
    funnel = pipeline.reset_deep_dive_gate_funnel()

    items = pipeline.get_pending_retry_items(limit=100)
    if items is None:
        raise RuntimeError("Pending Retry read failed")

    result = run_pending_retry_lane(pipeline, items, success_target=1)
    pipeline.logger.info(
        "[PENDING RETRY FAST LANE RESULT] backlog=%s attempted=%s succeeded=%s",
        len(items), result["attempted"], result["succeeded"],
    )
    pipeline.finalize_deep_dive_observability(funnel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
