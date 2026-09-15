#!/usr/bin/env python3
"""Low-cost Production fast lane for recovering one high-value Pending Retry article.

This entrypoint exists for a narrow business goal: when the normal article pipeline
has already paid the collection/screening cost and a Deep Dive failed transiently,
do not spend another run discovering fresh candidates before attempting recovery.

Safety contract:
- installs the exact current Production article/runtime/publication stack, including
  current precision/recovery overlays, before applying fast-lane-only controls;
- proves runtime-state writability before any Gemini reservation;
- caps this fast lane at four provider-visible Pending Retry article requests: at most
  three initial-generation sends allow the reproduced 503 -> 503 -> success fallback
  sequence, and one final request is reserved for a Production-authorized
  post-generation quality repair;
- model-assisted eyecatch layout is not part of article-quality validation and is
  rejected before reservation in this lane, so it cannot consume a fifth or spare send;
- attempts exactly one Pending Retry article candidate per validation run and never
  advances to a second article when the first candidate fails or a provider is down;
- cools a model for the rest of this fast-lane run after its first HTTP 503;
- permits at most one Reader Value recompose under the same current Production
  recovery policy when factual/evidence blockers are absent;
- reuses the persistent daily counters and all global Deep Dive/provider caps;
- ranks the fetched Pending Retry backlog by screening score, while preserving the
  core query's stable order as the tie-breaker;
- counts ``succeeded`` only when the non-persistent Production return explicitly says
  ``accepted``; ``rejected``, no generation, and unknown return shapes are distinct;
- an accepted non-persistent manuscript is a quality-pass result only, never a Notion
  Ready/persistence success;
- never publishes to note.com; downstream Note Ready Sync remains fail-closed and
  public note release stays human-only.

Run356 fixes a parity defect proven by live ONE-SHOT #45: this fast lane previously
installed only the historical runtime stack, so newer Production overlays such as
Run349/350/351/352 were absent even though this module claimed Production parity.

The 2026-09-15 reserve fix is deliberately narrower than a provider-budget redesign.
The live one-article validation proved that two transient 503 fallbacks plus one
successful generation consumed all three dedicated Pending Retry sends before the
Production quality stack could perform its one justified repair. The minimum bounded
cap for that reproduced path is therefore four provider-visible article sends.
Provider failures still consume the existing global, persistent and Deep Dive counters;
no failed provider-visible request is refunded. Pre-send safety rejection is not a
provider-visible send and therefore does not consume this validation-only send ceiling.
"""
from __future__ import annotations

import os
from typing import Any, MutableMapping

FAST_LANE_INITIAL_GENERATION_SEND_CEILING = 3
FAST_LANE_POST_GENERATION_REPAIR_RESERVE = 1
FAST_LANE_PENDING_RETRY_REQUEST_BUDGET = (
    FAST_LANE_INITIAL_GENERATION_SEND_CEILING + FAST_LANE_POST_GENERATION_REPAIR_RESERVE
)
FAST_LANE_ARTICLE_ATTEMPT_LIMIT = 1
FAST_LANE_503_COOLDOWN_THRESHOLD = 1
FAST_LANE_ENV = "AIIF_PENDING_RETRY_FAST_LANE"
FAST_LANE_EXCLUDED_MODELS = frozenset({"gemini-3.6-flash"})
VALIDATION_OUTCOME_ACCEPTED = "accepted"
VALIDATION_OUTCOME_REJECTED = "rejected"
VALIDATION_OUTCOME_NOT_GENERATED = "not_generated"
VALIDATION_OUTCOME_UNVERIFIED = "unverified"


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


def classify_nonpersistent_report(report: Any) -> str:
    """Classify the explicit ``persist_results=False`` Production return fail-closed.

    ``pipeline.generate_intelligence_report`` returns ``(manuscript, status)`` in this
    mode. A manuscript is intentionally truthy even when status is ``rejected`` so the
    diagnostic artifact can be saved; truthiness therefore must never mean quality
    success. Unknown/legacy return shapes remain ``unverified`` rather than being
    promoted to success.
    """
    if report is None:
        return VALIDATION_OUTCOME_NOT_GENERATED
    if isinstance(report, tuple) and len(report) >= 2:
        status = str(report[1] or "").strip().lower()
        if status == VALIDATION_OUTCOME_ACCEPTED:
            return VALIDATION_OUTCOME_ACCEPTED
        if status == VALIDATION_OUTCOME_REJECTED:
            return VALIDATION_OUTCOME_REJECTED
    return VALIDATION_OUTCOME_UNVERIFIED


def _empty_lane_result() -> dict[str, int]:
    return {
        "attempted": 0,
        # Backward-compatible key. In this non-persistent lane it now means explicit
        # quality-pass (accepted), never merely "a truthy manuscript was returned".
        "succeeded": 0,
        "quality_passed": 0,
        "quality_failed": 0,
        "not_generated": 0,
        "unverified": 0,
    }


def run_pending_retry_lane(
    pipeline_module,
    items: list[dict[str, Any]] | None,
    *,
    success_target: int = 1,
    article_attempt_limit: int = FAST_LANE_ARTICLE_ATTEMPT_LIMIT,
) -> dict[str, int]:
    """Attempt a bounded number of *articles*, independently of model-request fallback.

    The validation lane defaults to one article candidate. ``generate_intelligence_report`` may
    still consume more than one provider request for that same candidate under the Production
    fallback/recovery policy, but a failed first candidate must never cause the validation run to
    move on to a second article implicitly.
    """
    result = _empty_lane_result()
    success_target = max(1, int(success_target or 1))
    article_attempt_limit = max(1, int(article_attempt_limit or 1))

    for rank, item in enumerate(prioritize_pending_items(items), start=1):
        if result["quality_passed"] >= success_target or result["attempted"] >= article_attempt_limit:
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
                "[PENDING RETRY FAST LANE] rank=%s score=%s candidate=%s article_attempt=%s/%s request_cap=%s repair_reserve=%s",
                rank,
                item.get("screening_score"),
                name,
                result["attempted"] + 1,
                article_attempt_limit,
                FAST_LANE_PENDING_RETRY_REQUEST_BUDGET,
                FAST_LANE_POST_GENERATION_REPAIR_RESERVE,
            )

        result["attempted"] += 1
        report = pipeline_module.generate_intelligence_report(
            repo,
            item.get("notion_page_id"),
            item.get("screening_score"),
            item.get("screening_reason", ""),
            candidate_rank=rank,
            candidate_origin="pending_retry",
            persist_results=False,
        )
        outcome = classify_nonpersistent_report(report)
        if outcome == VALIDATION_OUTCOME_ACCEPTED:
            result["quality_passed"] += 1
            result["succeeded"] += 1
        elif outcome == VALIDATION_OUTCOME_REJECTED:
            result["quality_failed"] += 1
        elif outcome == VALIDATION_OUTCOME_NOT_GENERATED:
            result["not_generated"] += 1
        else:
            result["unverified"] += 1
        if logger is not None:
            logger.info(
                "[PENDING RETRY VALIDATION OUTCOME] candidate=%s outcome=%s quality_passed=%s ready_persisted=false",
                name,
                outcome,
                outcome == VALIDATION_OUTCOME_ACCEPTED,
            )

    return result


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


def _normalized_model_id(model_name: Any) -> str:
    value = str(model_name or "").strip().lower()
    while value.startswith("models/"):
        value = value[len("models/"):]
    return value


def _model_is_excluded(model_name: Any) -> bool:
    """Honor the operator ban for every Gemini 3.6 alias, not only one exact ID."""
    value = _normalized_model_id(model_name)
    return (
        value in FAST_LANE_EXCLUDED_MODELS
        or value == "gemini-3.6"
        or value.startswith("gemini-3.6-")
    )


def install_validation_model_exclusions(pipeline_module):
    """Enforce operator exclusions and the provider-visible validation send ceiling.

    Routing overlays can restore their default pool, so env-only removal is not
    sufficient. The final sender guard rejects Gemini 3.6 aliases before reservation.
    Its local ceiling follows the pipeline's usage-audit attempt record when available;
    therefore a local/persistent pre-send rejection does not masquerade as a provider
    send, while 429/503/provider-visible failures remain counted. Model-assisted
    eyecatch layout is unnecessary for article-quality validation and is rejected before
    reservation in this lane.
    """
    if getattr(pipeline_module, "_pending_validation_exclusions_installed", False):
        return pipeline_module
    original = pipeline_module._generate_via_chat
    excluded = FAST_LANE_EXCLUDED_MODELS
    runtime_excluded: set[str] = set(excluded)
    for attr in ("DEEP_DIVE_MODEL_POOL", "DEEP_DIVE_MODEL_CANDIDATES", "SCREENING_MODEL_POOL"):
        pool = getattr(pipeline_module, attr, None)
        if pool is not None:
            runtime_excluded.update(str(m) for m in pool if _model_is_excluded(m))
            setattr(pipeline_module, attr, [m for m in pool if not _model_is_excluded(m)])
    pipeline_module.SESSION_UNAVAILABLE_MODELS.update(runtime_excluded)

    sends = 0

    def _audit_attempt_count() -> int | None:
        audit = getattr(pipeline_module, "GEMINI_USAGE_AUDIT", None)
        records = getattr(audit, "records", None)
        return len(records) if isinstance(records, list) else None

    def guarded_send(model_name, *args, **kwargs):
        nonlocal sends
        if _model_is_excluded(model_name):
            raise pipeline_module.NoAvailableModelError(
                "Operator excluded Gemini 3.6 from validation, including fallback and aliases"
            )
        request_kind = str(kwargs.get("request_kind") or "").strip().lower()
        if request_kind == "eyecatch_layout":
            raise pipeline_module.NoAvailableModelError(
                "Pending Retry validation skips model-assisted eyecatch layout"
            )
        if sends >= FAST_LANE_PENDING_RETRY_REQUEST_BUDGET:
            raise pipeline_module.NoAvailableModelError("Validation total provider-send ceiling reached")

        before = _audit_attempt_count()
        try:
            return original(model_name, *args, **kwargs)
        finally:
            after = _audit_attempt_count()
            if before is not None and after is not None:
                # _consume_gemini_request records the attempt only after all pre-send
                # local/persistent budgets have admitted it. A 429/503 still leaves one
                # audit record, while a pre-send rejection leaves zero.
                sends += max(0, after - before)
            else:
                # Lightweight tests/legacy adapters may not expose the audit object.
                # Preserve the previous conservative admission accounting there.
                sends += 1

    pipeline_module._generate_via_chat = guarded_send
    pipeline_module._pending_validation_exclusions_installed = True
    pipeline_module.logger.info(
        "[VALIDATION MODEL EXCLUSIONS] excluded=%s pool=%s model_eyecatch=false send_cap=%s",
        sorted(runtime_excluded), pipeline_module.DEEP_DIVE_MODEL_POOL,
        FAST_LANE_PENDING_RETRY_REQUEST_BUDGET,
    )
    return pipeline_module


def main() -> int:
    prepare_fast_lane_env()

    import gemini_transient_recovery
    import note_manuscript
    import pipeline
    import run179_eyecatch_font_refinement
    import run203_runtime_state_channel as runtime_state_channel

    install_current_production_article_stack(pipeline, note_manuscript)
    install_validation_model_exclusions(pipeline)
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

    result = run_pending_retry_lane(
        pipeline,
        items,
        success_target=1,
        article_attempt_limit=FAST_LANE_ARTICLE_ATTEMPT_LIMIT,
    )
    pipeline.logger.info(
        "[PENDING RETRY FAST LANE RESULT] backlog=%s attempted=%s quality_passed=%s quality_failed=%s not_generated=%s unverified=%s ready_persisted=0 article_limit=%s request_cap=%s repair_reserve=%s",
        len(items),
        result["attempted"],
        result["quality_passed"],
        result["quality_failed"],
        result["not_generated"],
        result["unverified"],
        FAST_LANE_ARTICLE_ATTEMPT_LIMIT,
        FAST_LANE_PENDING_RETRY_REQUEST_BUDGET,
        FAST_LANE_POST_GENERATION_REPAIR_RESERVE,
    )
    pipeline.finalize_deep_dive_observability(funnel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
