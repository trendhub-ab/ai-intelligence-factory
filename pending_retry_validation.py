#!/usr/bin/env python3
"""Low-cost Production fast lane for recovering one high-value Pending Retry article.

This entrypoint exists for a narrow business goal: when the normal article pipeline
has already paid the collection/screening cost and a Deep Dive failed transiently,
do not spend another run discovering fresh candidates before attempting recovery.

Safety contract:
- installs the exact current Production article/runtime/publication stack, including
  current precision/recovery overlays, before applying fast-lane-only controls;
- proves runtime-state writability before any Gemini reservation;
- caps this fast lane at three Pending Retry requests so two provider failures can
  still leave one cross-model generation opportunity; this is an explicit fast-lane
  cap and does not raise any persistent per-model or global provider safety ceiling;
- cools a model for the rest of this fast-lane run after its first HTTP 503;
- permits at most one Reader Value recompose under the same current Production
  recovery policy when factual/evidence blockers are absent;
- reuses the persistent daily counters and all global Deep Dive/provider caps;
- ranks the fetched Pending Retry backlog by screening score, while preserving the
  core query's stable order as the tie-breaker;
- stops immediately after the first successful article;
- never publishes to note.com; downstream Note Ready Sync remains fail-closed and
  public note release stays human-only.

Run356 fixes a parity defect proven by live ONE-SHOT #45: this fast lane previously
installed only the historical runtime stack, so newer Production overlays such as
Run349/350/351/352 were absent even though this module claimed Production parity.
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


def install_current_production_article_stack(pipeline_module, note_manuscript_module):
    """Install the same current article-quality overlays as production_pipeline.main().

    Fast-lane transport controls are deliberately excluded here and installed by main()
    only after parity is established. Keep this order synchronized with Production.
    """
    import production_pipeline
    from source_normalization import install as install_source_normalization
    from run231_performance_telemetry import install as install_performance_telemetry
    from run268_business_source_strategy import install as install_run268_business_source_strategy
    from run269_business_source_precision import install as install_run269_business_source_precision
    from run283_numeric_evidence_equivalence import install as install_run283_numeric_evidence_equivalence
    from run284_reader_recovery_precision import install as install_run284_reader_recovery_precision
    from run287_publication_date_provenance import install as install_run287_publication_date_provenance
    from reader_quality_precision import install as install_reader_quality_precision

    install_source_normalization(pipeline_module)
    production_pipeline.install_runtime_layers(pipeline_module)
    production_pipeline.install_run349_score_narrative_negation_precision(pipeline_module)
    install_run283_numeric_evidence_equivalence(pipeline_module)
    install_run268_business_source_strategy(pipeline_module)
    install_run269_business_source_precision(pipeline_module)
    install_reader_quality_precision(pipeline_module)
    install_run284_reader_recovery_precision(pipeline_module)
    install_run287_publication_date_provenance(note_manuscript_module, pipeline_module)
    install_performance_telemetry(pipeline_module)
    return pipeline_module


def main() -> int:
    prepare_fast_lane_env()

    import gemini_transient_recovery
    import note_manuscript
    import pipeline
    import run179_eyecatch_font_refinement
    import run203_runtime_state_channel as runtime_state_channel

    install_current_production_article_stack(pipeline, note_manuscript)
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
