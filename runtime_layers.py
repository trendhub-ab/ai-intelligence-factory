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

Run358 adds a second narrow precision contract for two defects reproduced from a real
Production manuscript: a slash-delimited acronym with an inline Japanese gloss could
be split into an unexplained sub-token, and seven-character topic fragments could be
mistaken for a repeated insight.  The precision contract can only remove those proven
false-positive signals; it never converts genuine density, Fact, Evidence, Publication,
or final-surface failures into PASS.

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


# Run358 reader-signal precision contract.
# The production RubyGems specimen exposed two deterministic false positives:
# 1. ``CI/CD（自動ビルド環境）`` was split and ``CI`` was reported as unexplained even
#    though the whole compound had an adjacent Japanese gloss. ``SF`` was also treated as
#    specialist jargon despite being ordinary Japanese editorial vocabulary.
# 2. The 7-character cross-paragraph detector treated topic-bearing fragments such as
#    「エージェントの」「エージェントが」「ドキュメント生成」 as repeated insight.
# We only demote these reproduced false positives. Existing density/jargon/final-surface
# reviews stay authoritative and Fact/Evidence/Publication are untouched.
_READER_PRECISION_COMMON_ACRONYMS = {
    "AI", "API", "LLM", "OSS", "URL", "UI", "UX", "DB", "CPU", "GPU", "ID", "SF",
}
_READER_PRECISION_ACRONYM_RE = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9-]{1,8})(?![A-Za-z0-9])")
_READER_PRECISION_COMPOUND_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/.+-")
_READER_PRECISION_REPEAT_FRAGMENT_LEN = 9


def _reader_precision_prose(article: str) -> str:
    return re.sub(r"^#{1,6}\s+.*$", "", str(article or ""), flags=re.MULTILINE)


def _reader_precision_compound(prose: str, start: int, end: int) -> str:
    left = start
    right = end
    while left > 0 and prose[left - 1] in _READER_PRECISION_COMPOUND_CHARS:
        left -= 1
    while right < len(prose) and prose[right] in _READER_PRECISION_COMPOUND_CHARS:
        right += 1
    return prose[left:right]


def _reader_precision_unexplained_acronyms(article: str) -> list[str]:
    """Return only acronyms that are not common and lack a local/compound gloss."""
    prose = _reader_precision_prose(article)
    unexplained: list[str] = []
    for match in _READER_PRECISION_ACRONYM_RE.finditer(prose):
        token = match.group(1)
        if token in _READER_PRECISION_COMMON_ACRONYMS or token in unexplained:
            continue
        compound = _reader_precision_compound(prose, match.start(1), match.end(1))
        near = prose[max(0, match.start() - 90):match.end() + 120]
        direct_explained = bool(re.search(
            rf"(?:{re.escape(token)}\s*[（(].{{2,70}}[）)]|"
            rf"[（(].{{2,70}}[）)]\s*{re.escape(token)}|"
            rf".{{3,90}}[（(]{re.escape(token)}[）)]|"
            rf"{re.escape(token)}(?:とは|は、|は){{1}}.{{4,80}}"
            rf"(?:仕組み|方式|規格|標準|ツール|モデル|プロトコル|ルール))",
            near,
            re.S,
        ))
        compound_glossed = bool(
            compound
            and compound != token
            and re.search(
                rf"{re.escape(compound)}\s*[（(][^）)\n]{{2,70}}[）)]",
                near,
            )
        )
        if not (direct_explained or compound_glossed):
            unexplained.append(token)
    return unexplained


def _reader_precision_repetitive_insight(article: str) -> bool:
    """Detect repeated wording without treating short topic nouns as repeated insight.

    The historical 7-character detector was shorter than common Japanese topic phrases.
    Nine characters keeps the zero-API behavior while requiring a more distinctive span.
    We still require multiple overlapping long fragments to recur in at least three distinct
    paragraphs, so genuinely duplicated explanation remains detectable.
    """
    prose = _reader_precision_prose(article)
    paragraphs = [x.strip() for x in re.split(r"\n\s*\n", prose) if x.strip()]
    fragment_paragraphs: dict[str, set[int]] = {}
    n = _READER_PRECISION_REPEAT_FRAGMENT_LEN
    for paragraph_index, paragraph in enumerate(paragraphs):
        compact = re.sub(
            r"https?://\S+|`[^`]+`|[A-Za-z0-9_.:/+-]+|"
            r"[\s。、！？!?「」『』（）()【】#*_>・:：;；,，.-]+",
            "",
            paragraph,
        )
        if len(compact) < n:
            continue
        seen = {compact[index:index + n] for index in range(len(compact) - n + 1)}
        for fragment in seen:
            fragment_paragraphs.setdefault(fragment, set()).add(paragraph_index)
    repeated = [fragment for fragment, owners in fragment_paragraphs.items() if len(owners) >= 3]
    return len(repeated) >= 2


def install_reader_signal_precision_contract(pipeline_module):
    """Demote only reproduced reader-signal false positives; never create a new PASS path."""
    p = pipeline_module
    marker = "_run358_reader_signal_precision_contract_installed"
    if bool(getattr(p, marker, False)):
        return p

    target_name = "_reader_experience_signals"
    original = getattr(p, target_name, None)
    if not callable(original):
        target_name = "_reader_experience_signals_impl"
        original = getattr(p, target_name, None)
    if not callable(original):
        return p

    def reader_experience_signals_with_precision(article: str, *args, **kwargs):
        signals = dict(original(article, *args, **kwargs) or {})

        precise_acronyms = _reader_precision_unexplained_acronyms(article)
        signals["unexplained_jargon"] = precise_acronyms[:8]
        accessibility_issues = list(signals.get("accessibility_issues") or [])
        if not precise_acronyms and "unexplained_acronyms" in accessibility_issues:
            accessibility_issues = [x for x in accessibility_issues if x != "unexplained_acronyms"]
            signals["accessibility_issues"] = accessibility_issues
            if not accessibility_issues:
                signals["accessibility"] = "GOOD"

        if bool(signals.get("repetitive_insight")) and not _reader_precision_repetitive_insight(article):
            signals["repetitive_insight"] = False
            enjoyment_issues = [
                x for x in list(signals.get("enjoyment_issues") or []) if x != "repetitive_insight"
            ]
            signals["enjoyment_issues"] = enjoyment_issues
            if not enjoyment_issues:
                signals["reader_enjoyment"] = "GOOD"

        signals["reader_signal_precision_contract"] = "run358"
        return signals

    setattr(p, target_name, reader_experience_signals_with_precision)
    setattr(p, marker, True)
    setattr(p, "RUN358_READER_SIGNAL_PRECISION_CONTRACT", True)
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
    # Run358 is a zero-provider-call precision correction over the canonical reader
    # diagnostics. It removes only reproduced false positives and leaves all genuine
    # density/jargon/final-surface diagnostics available to Run208/248/249.
    install_reader_signal_precision_contract(pipeline_module)
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
    # Run357/358 are internal interaction/precision contracts, not numbered runtime layers.
    # The canonical layer manifest remains unchanged so Run279 continues to prove the
    # historical module.install sequence, while runtime_layers.py itself remains covered by
    # Publication Contract provenance.
    run248_first_real_publish_quality_calibration.install(pipeline_module)
    run249_final_publication_surface_gate.install(pipeline_module)
    install_quality_interaction_contract(pipeline_module)
    run194_publication_contract.install(pipeline_module)
    return pipeline_module