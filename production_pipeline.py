"""Stable production entrypoint for the AI Intelligence Factory.

Run231 keeps this file as a small orchestration contract. Historical production
runtime layers live in ``runtime_layers.py`` in their exact validated order, while
performance telemetry is observational and installed only after all quality,
reliability, preflight, font, and compatibility contracts are in place.

Daily is currently PAUSED; this file remains the contract to use when Daily is
explicitly resumed.

Run305 also makes this file the sole root entrypoint for the bounded Product Review
child. An explicit environment flag selects a narrow provider/quota-only runtime;
raw root-level ``pipeline.main()`` bypasses remain prohibited.
"""
from __future__ import annotations

import json
import os

from runtime_layers import install_runtime_layers as _canonical_install_runtime_layers


PRODUCT_REVIEW_PROVIDER_LAYER_ORDER = (
    "run203_runtime_state_channel.install",
    "gemini_timeout_rpd_fail_closed.install",
    "gemini_transient_recovery.install",
    "gemini_provider_resilience.install",
)


def install_product_review_provider_runtime(pipeline_module):
    """Install only provider/quota safety required by the product-only child.

    Run260 is intentionally excluded so Product Review keeps its explicit
    3.6 -> 3.7 -> 3.8 -> 3.5 model order rather than inheriting article routing.
    Article/publication/Reader Value/eyecatch layers are also deliberately absent.
    """
    import run203_runtime_state_channel as runtime_state_channel
    import gemini_timeout_rpd_fail_closed
    import gemini_transient_recovery
    import gemini_provider_resilience

    runtime_state_channel.install(pipeline_module)
    gemini_timeout_rpd_fail_closed.install(pipeline_module)
    gemini_transient_recovery.install(pipeline_module)
    gemini_provider_resilience.install(pipeline_module)
    return pipeline_module


def _product_review_runtime_requested() -> bool:
    return os.environ.get("AIIF_PRODUCT_REVIEW_RUNTIME", "").strip().lower() == "true"


def _run_product_review_runtime() -> None:
    """Run product-only pipeline through the narrow Run305 provider runtime."""
    import pipeline
    import run203_runtime_state_channel as runtime_state_channel

    install_product_review_provider_runtime(pipeline)
    if not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)):
        runtime_state_channel.preflight_runtime_state_channel()
    pipeline.main()


def install_runtime_layers(pipeline_module):
    """Compatibility manifest for the existing Documentation Freshness Guard.

    The imports below intentionally mirror the canonical modules but contain no
    installation logic. ``runtime_layers.py`` remains the single source of truth for
    install order and behavior. Keeping this import-only manifest lets the existing
    fail-closed documentation guard continue to audit every active layer during the
    Run231 refactor without weakening its contract.
    """
    import run203_runtime_state_channel
    import gemini_timeout_rpd_fail_closed
    import gemini_transient_recovery
    import run260_gemini_model_routing
    import run172_production_reliability
    import gemini_provider_resilience
    import run173_operational_yield
    import run174_monthly_digest_integrity
    import run175_semantic_fact_precision
    import run223_technical_claim_precision
    import run224_multiplier_deterministic_rescue
    import run227_japanese_surface_integrity
    import run176_scope_fidelity
    import run177_paid_funnel_alignment
    import run226_reader_delight_planning
    import run228_reader_rhythm_planning
    import run178_eyecatch_editorial_layout_optimizer
    import run179_eyecatch_font_refinement
    import run180_eyecatch_semantic_layout
    import run181_eyecatch_visual_balance
    import run182_eyecatch_conclusion_emphasis
    import run183_eyecatch_emphasis_scale
    import reader_value_review_bridge
    import run208_reader_value_repair
    import run222_note_presentation_integrity
    import run296_editorial_format_v2
    import run248_first_real_publish_quality_calibration
    import run249_final_publication_surface_gate
    import run194_publication_contract

    return _canonical_install_runtime_layers(pipeline_module)


# Runtime compatibility contract: callers historically imported
# ``production_pipeline.install_runtime_layers`` and some regression contracts inspect
# that callable's source to verify wrapper order. Point the public runtime symbol at
# the canonical implementation so those callers observe the real Source of Truth,
# while the import-only function above remains available to static documentation
# freshness analysis. This avoids duplicating installation logic or weakening guards.
install_runtime_layers = _canonical_install_runtime_layers


def _workflow_dispatch_mode() -> str:
    """Return the ONE-SHOT workflow mode without changing normal/local execution.

    GitHub Actions exposes workflow_dispatch inputs through ``GITHUB_EVENT_PATH``.
    An explicit ``AIIF_ONE_SHOT_MODE`` is accepted for hermetic tests and controlled
    local validation. Unknown/missing values deliberately fall back to the normal
    production path; the workflow itself still owns the allowlist/fail-closed check.
    """
    explicit = os.environ.get("AIIF_ONE_SHOT_MODE", "").strip()
    if explicit:
        return explicit
    event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()
    if not event_path:
        return ""
    try:
        with open(event_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return str((payload.get("inputs") or {}).get("mode") or "").strip()
    except (OSError, ValueError, TypeError):
        return ""


def main() -> None:
    # Run305: Product Review is still a child process, but every root executable must
    # enter through this sole production authority. Branch before article imports so
    # product-only execution does not install or initialize article/publication layers.
    if _product_review_runtime_requested():
        _run_product_review_runtime()
        return

    import note_manuscript
    import pipeline
    import run179_eyecatch_font_refinement
    import run203_runtime_state_channel as runtime_state_channel
    from article_revalidation import install_full_recovery, run_article_revalidation
    from current_policy_ready_recovery import run_current_policy_ready_recovery
    from source_normalization import install as install_source_normalization
    from run231_performance_telemetry import install as install_performance_telemetry
    from run268_business_source_strategy import install as install_run268_business_source_strategy
    from run269_business_source_precision import install as install_run269_business_source_precision
    from run283_numeric_evidence_equivalence import install as install_run283_numeric_evidence_equivalence
    from run284_reader_recovery_precision import install as install_run284_reader_recovery_precision
    from run287_publication_date_provenance import install as install_run287_publication_date_provenance
    from reader_quality_precision import install as install_reader_quality_precision

    # Run235 Stage3A structural extraction. These functions are pure and zero-API.
    # Install them before the historical runtime wrapper chain so every later layer sees
    # the canonical source-normalization surface without changing wrapper order.
    install_source_normalization(pipeline)

    # Compatibility contract: install every historical production layer before any
    # current strategy overlay. Historical quality/reliability wrapper order must not
    # change when source acquisition strategy changes.
    install_runtime_layers(pipeline)

    # Run283 is a current zero-API Fact precision overlay, not a historical runtime-layer
    # mutation. It filters only proven cross-language numeric false positives and remains
    # separately fingerprinted by Publication Contract.
    install_run283_numeric_evidence_equivalence(pipeline)

    # Run268 is the source/business architecture authority: four active sources,
    # OfficialVendor replacing Product Hunt, and Proposal-First product semantics.
    install_run268_business_source_strategy(pipeline)

    # Run269 is precision-only. It keeps Run268's architecture and tightens the two
    # live network acquisition surfaces after real smoke testing exposed vendor-nav and
    # HN typo false positives. No provider/model/Notion path is introduced here.
    install_run269_business_source_precision(pipeline)

    # Run275 is a zero-API publication-quality precision overlay derived from real Run31
    # artifacts. It corrects only reproducible Reader signal false positives (opening
    # bridge, visible heading rhythm, later acronym explanation) and one malformed
    # Japanese particle collision. Genuine dense-reader failures remain REVIEW.
    install_reader_quality_precision(pipeline)

    # Run284 is derived from two real current-policy recovery attempts. It removes one
    # deterministic Japanese corruption rule for every Production article, and authorizes
    # one existing Reader Value quality-repair call only inside the explicit Run282 recovery
    # lane when Evidence is already SUFFICIENT and all blockers are reader-only.
    install_run284_reader_recovery_precision(pipeline)

    # Run287 keeps discovery timestamps honest on the public manuscript. Hacker News
    # item time is labeled as the HN post date and can never masquerade as the external
    # primary source's publication/update date. This is deterministic and zero-provider.
    install_run287_publication_date_provenance(note_manuscript, pipeline)

    if not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)):
        runtime_state_channel.preflight_runtime_state_channel()

    run179_eyecatch_font_refinement.ensure_google_font_assets(
        enabled=not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)),
        logger=getattr(pipeline, "logger", None),
    )

    # The direct-import compatibility bridge in pipeline.py owns the legacy/internal
    # renderer installation. Do not import legacy_eyecatch_renderer again here: the live
    # publication renderer remains usable when that obsolete module itself is absent.

    # Zero-API, observational only. Installed last so timers see the final production
    # functions without participating in the historical wrapper chain.
    install_performance_telemetry(pipeline)

    mode = _workflow_dispatch_mode()

    # Run282: current-policy Ready recovery is an explicit, bounded business-write lane.
    # It never enters fresh acquisition/screening/Product Review and regenerates at most
    # one historical Ready row on its original Notion page. The canonical quality stack
    # still owns the manuscript bytes, status, and fail-closed outcome.
    if mode == "current_policy_ready_recovery":
        run_current_policy_ready_recovery(pipeline)
        return

    # Run277: article_validation must validate an *existing non-Ready* candidate.
    # Fresh acquisition would be defeated by the authoritative Notion dedupe and would
    # silently change the validation target after every Gate fix. The dedicated lane is
    # read-only (persist_results=False) and bounded.
    if mode == "article_validation":
        run_article_revalidation(pipeline)
        return

    # Run276: pending_retry_validation must consume a real persisted pending-retry
    # candidate rather than a fresh candidate. One item max, persist_results=False.
    if mode == "pending_retry_validation":
        run_article_revalidation(pipeline, pending_only=True)
        return

    # Run277 production repair lane. Outside this explicit mode the historical runtime
    # policy remains unchanged.
    if mode == "full":
        install_full_recovery(pipeline)

    pipeline.main()


if __name__ == "__main__":
    main()
