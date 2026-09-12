"""Canonical production runtime-layer installation order.

Run231 moves the production patch stack out of ``production_pipeline.py`` without
changing its behavior.  The order below is a compatibility contract: later layers
intentionally wrap or refine functions installed by earlier layers.

Run357 adds a stable interaction contract inside this canonical module instead of
adding another numbered patch module.  The contract fixes one proven cross-layer
self-contradiction: final Japanese polish used to translate a leaked ``WATCH`` code
into a phrase that the immediately-following Human Appeal gate itself classified as
generic monitoring.  The contract changes only that deterministic self-generated
surface; it does not bypass Human Appeal, relax Fact/Evidence, or change model calls.

Do not reorder, remove, or merge a layer here unless its own regression suite proves
that the resulting production behavior is equivalent or intentionally superseded.
"""
from __future__ import annotations

import re


RUNTIME_LAYER_ORDER = (
    "run203_runtime_state_channel.install",
    "gemini_timeout_rpd_fail_closed.install",
    "gemini_transient_recovery.install",
    "run260_gemini_model_routing.install",
    "run172_production_reliability.install",
    "gemini_provider_resilience.install",
    "run173_operational_yield.install",
    "run174_monthly_digest_integrity.install",
    "run175_semantic_fact_precision.install",
    "run223_technical_claim_precision.install",
    "run224_multiplier_deterministic_rescue.install",
    "run227_japanese_surface_integrity.install",
    "run176_scope_fidelity.install",
    "run177_paid_funnel_alignment.install",
    "run226_reader_delight_planning.install",
    "run228_reader_rhythm_planning.install",
    "run178_eyecatch_editorial_layout_optimizer.install",
    "run179_eyecatch_font_refinement.install",
    "run180_eyecatch_semantic_layout.install",
    "run181_eyecatch_visual_balance.install",
    "run182_eyecatch_conclusion_emphasis.install",
    "run183_eyecatch_emphasis_scale.install",
    "reader_value_review_bridge.install",
    "run208_reader_value_repair.install",
    "run222_note_presentation_integrity.install_pipeline",
    "run296_editorial_format_v2.install",
    "run248_first_real_publish_quality_calibration.install",
    "run249_final_publication_surface_gate.install",
    "run194_publication_contract.install",
)


# Run357 cross-layer invariant.
# Base pipeline._apply_final_japanese_polish maps leaked WATCH to
# 「今後の動きを注視する」, while validate_human_appeal_gate interprets 注視/様子を見る
# without a concrete action as action_collapsed_to_generic_monitoring.  We deliberately
# keep the Human Appeal rule intact and normalize only the phrase created by the system
# itself.  The replacement is a real WATCH decision: wait for new primary evidence and
# then re-evaluate.  It also satisfies the existing concrete-action vocabulary via 待ち.
_MANAGEMENT_WATCH_TOKEN_RE = re.compile(r"(?<![A-Za-z])WATCH(?![A-Za-z])")
_LEGACY_SELF_CONFLICTING_WATCH_PHRASE = "今後の動きを注視する"
_PUBLIC_WATCH_DECISION_PHRASE = "新しい一次情報が出るまで待ち、出た時点で再評価する"


def install_quality_interaction_contract(pipeline_module):
    """Prevent deterministic cleanup from creating a later quality-gate violation.

    Scope is intentionally narrow:
    - applies only when the incoming article actually contains an uppercase standalone
      MANAGEMENT ``WATCH`` token;
    - rewrites only the exact legacy phrase produced by the existing deterministic polish;
    - does not suppress or special-case any quality gate;
    - performs zero provider/API calls.
    """
    p = pipeline_module
    marker = "_run357_quality_interaction_contract_installed"
    if bool(getattr(p, marker, False)):
        return p

    original = getattr(p, "_apply_final_japanese_polish", None)
    if not callable(original):
        return p

    def apply_final_japanese_polish_with_interaction_contract(parsed: dict):
        incoming = dict(parsed or {})
        original_article = str(incoming.get("note_draft") or "")
        had_management_watch_leak = bool(_MANAGEMENT_WATCH_TOKEN_RE.search(original_article))

        out, changes = original(parsed)
        out = dict(out or {})
        changes = list(changes or [])

        if had_management_watch_leak:
            article = str(out.get("note_draft") or "")
            rewritten, count = re.subn(
                re.escape(_LEGACY_SELF_CONFLICTING_WATCH_PHRASE),
                _PUBLIC_WATCH_DECISION_PHRASE,
                article,
            )
            if count:
                out["note_draft"] = rewritten
                changes.append(f"note_draft:watch_quality_interaction_contract:{count}")

        return out, changes

    p._apply_final_japanese_polish = apply_final_japanese_polish_with_interaction_contract
    setattr(p, marker, True)
    setattr(p, "RUN357_QUALITY_INTERACTION_CONTRACT", True)
    return p


def install_runtime_layers(pipeline_module):
    """Install every validated production layer in the historical canonical order."""
    import run203_runtime_state_channel as runtime_state_channel
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

    runtime_state_channel.install(pipeline_module)

    # Provider RPD telemetry proved that transport timeouts can still consume daily quota.
    # Keep the pre-send reservation fail-closed while preserving the existing per-model
    # safety ceilings configured by Production workflows.
    gemini_timeout_rpd_fail_closed.install(pipeline_module)
    gemini_transient_recovery.install(pipeline_module)
    # Run260 changes routing only: 3.7 is fresh Deep Dive primary, 3.8 is preferred for
    # model-based quality repair, and existing request/gate budgets remain authoritative.
    run260_gemini_model_routing.install(pipeline_module)
    run172_production_reliability.install(pipeline_module)
    # Run303 supersedes only Run172's provider-transport fail-fast behavior. A single
    # structured HTTP 503 now receives one bounded same-model confirmation retry; only
    # two consecutive verified 503s open the run-local model circuit. No gate changes.
    gemini_provider_resilience.install(pipeline_module)
    run173_operational_yield.install(pipeline_module)
    run174_monthly_digest_integrity.install(pipeline_module)
    run175_semantic_fact_precision.install(pipeline_module)

    # Technical/factual precision stack.  Run224 is a zero-API deterministic rescue for
    # the narrow multiplier-scope failure detected by Run223; Run227 blocks only
    # high-confidence broken Japanese and delegates repair to the existing bounded path.
    run223_technical_claim_precision.install(pipeline_module)
    run224_multiplier_deterministic_rescue.install(pipeline_module)
    run227_japanese_surface_integrity.install(pipeline_module)
    run176_scope_fidelity.install(pipeline_module)
    run177_paid_funnel_alignment.install(pipeline_module)

    # Reader planning changes only the existing generation prompt.  These layers add no
    # model call and must remain in this order so Run228 refines the Run226 plan.
    run226_reader_delight_planning.install(pipeline_module)
    run228_reader_rhythm_planning.install(pipeline_module)

    # Eyecatch layers are deliberately ordered refinements of the same renderer.
    run178_eyecatch_editorial_layout_optimizer.install(pipeline_module)
    run179_eyecatch_font_refinement.install(pipeline_module)
    run180_eyecatch_semantic_layout.install(pipeline_module)
    run181_eyecatch_visual_balance.install(pipeline_module)
    run182_eyecatch_conclusion_emphasis.install(pipeline_module)
    run183_eyecatch_emphasis_scale.install(pipeline_module)

    reader_value_review_bridge.install(pipeline_module)
    # Reader-only dynamic repair is installed after the historical bridge so it can
    # selectively override only the bridge's reader_value_review_no_retry decision.
    run208_reader_value_repair.install(pipeline_module)

    # Presentation-only but publication-material: keep CTA ordering after evidence and
    # disclaimer without changing Evidence/Decision semantics.
    run222_note_presentation_integrity.install_pipeline(pipeline_module)

    # First real-draft visual review policy. Run296 deliberately sits after Run222 so it
    # can normalize the final reader header/CTA surface while retaining Sources-before-CTA,
    # and after Run183 so it can tighten the existing single-call eyecatch direction without
    # adding another provider request.
    run296_editorial_format_v2.install(pipeline_module)

    # First-real-publish calibration is zero-provider-call and deliberately sits after all
    # article/eyecatch/presentation layers.  Run249 then rechecks the reader-first public
    # projection so late title/summary assembly cannot bypass Reader Value diagnostics.
    # Run357 is an internal interaction contract, not another runtime layer: it prevents
    # the deterministic WATCH cleanup from manufacturing a Human Appeal failure of its own.
    # The canonical layer manifest remains unchanged so Run279 continues to prove the
    # historical module.install sequence, while runtime_layers.py itself remains covered by
    # Publication Contract provenance.
    run248_first_real_publish_quality_calibration.install(pipeline_module)
    run249_final_publication_surface_gate.install(pipeline_module)
    install_quality_interaction_contract(pipeline_module)
    run194_publication_contract.install(pipeline_module)
    return pipeline_module
