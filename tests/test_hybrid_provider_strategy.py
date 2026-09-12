from hybrid_provider_strategy import (
    GEMINI_ONLY,
    HYBRID_GROQ_GEMINI,
    GEMINI_ONLY_BACKUP_BRANCH,
    GEMINI_ONLY_BACKUP_SHA,
    HybridRoutingError,
    assert_backup_contract,
    estimate_provider_calls,
    gemini_call_reduction,
    resolve_mode,
    route_stage,
)


def test_default_mode_preserves_gemini_only():
    assert resolve_mode({}) == GEMINI_ONLY
    for stage in ("screening", "calibration", "decision_plan", "article_writer"):
        decision = route_stage(stage, env={})
        assert decision.provider == "gemini"
        assert decision.allow_cross_provider_fallback is False


def test_hybrid_routes_only_preprocessing_to_groq():
    assert route_stage("screening", mode=HYBRID_GROQ_GEMINI).provider == "groq"
    assert route_stage("calibration", mode=HYBRID_GROQ_GEMINI).provider == "groq"
    assert route_stage("decision_plan", mode=HYBRID_GROQ_GEMINI).provider == "groq"
    assert route_stage("article_writer", mode=HYBRID_GROQ_GEMINI).provider == "gemini"


def test_local_quality_gates_never_become_provider_calls():
    for stage in (
        "evidence_sufficiency", "fact_gate", "editorial_gate",
        "publication_gate", "human_appeal_gate", "note_manuscript",
    ):
        decision = route_stage(stage, mode=HYBRID_GROQ_GEMINI)
        assert decision.provider == "local"
        assert decision.business_writes == 0


def test_no_silent_groq_to_gemini_fallback_contract():
    for stage in ("screening", "calibration", "decision_plan"):
        decision = route_stage(stage, mode=HYBRID_GROQ_GEMINI)
        assert decision.provider == "groq"
        assert decision.allow_cross_provider_fallback is False


def test_unknown_mode_and_stage_fail_closed():
    try:
        resolve_mode({"AIIF_PROVIDER_MODE": "magic"})
        raise AssertionError("unknown mode must fail")
    except HybridRoutingError as exc:
        assert str(exc) == "unsupported_provider_mode:magic"
    try:
        route_stage("mystery", mode=HYBRID_GROQ_GEMINI)
        raise AssertionError("unknown stage must fail")
    except HybridRoutingError as exc:
        assert str(exc) == "unknown_stage:mystery"


def test_call_reduction_is_stage_count_based_not_503_claim():
    counts = {"screening": 8, "calibration": 3, "decision_plan": 3, "article_writer": 3}
    baseline = estimate_provider_calls(counts, mode=GEMINI_ONLY)
    hybrid = estimate_provider_calls(counts, mode=HYBRID_GROQ_GEMINI)
    reduction = gemini_call_reduction(counts)
    assert baseline == {"gemini": 17, "groq": 0, "local": 0}
    assert hybrid == {"gemini": 3, "groq": 14, "local": 0}
    assert reduction["gemini_calls_avoided"] == 14
    assert reduction["gemini_call_reduction_pct"] == 82.35


def test_backup_contract_is_pinned_to_current_gemini_only_snapshot():
    assert GEMINI_ONLY_BACKUP_BRANCH == "backup/gemini-only-run360-20260912"
    assert GEMINI_ONLY_BACKUP_SHA == "bdcd0a548084b348efb821b45b32d4a3faa0dc12"
    assert_backup_contract()
