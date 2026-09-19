from __future__ import annotations

import types

import run208_reader_value_repair as run208


def _safe_evidence():
    return {"state": "SUFFICIENT", "decision_scope_safe": True}


def _pipeline_with_live_like_base_policy():
    p = types.SimpleNamespace()
    p.GATE_SEVERITY_HARD = "HARD"
    p.EVIDENCE_SUFFICIENT = "SUFFICIENT"
    p.MAX_QUALITY_RETRIES = 1
    p.REASON_CODE_APPEAL_DECISION_VOICE_LOSS = "APPEAL_DECISION_VOICE_LOSS"

    # This reproduces the real base policy: any non-empty repairable REVIEW bundle
    # returns allowed=True. Run360 must still hand the already-budgeted second slot
    # to the dedicated Reader owner after the Fact owner was spent.
    p.should_attempt_dynamic_retry = (
        lambda rows, evidence, origin="new":
        (True, "repairable") if rows else (False, "no_blocking_reason")
    )
    p.build_decision_prompt = lambda *args, **kwargs: "BASE PROMPT"
    p.build_dynamic_retry_instruction = lambda rows: ("BASE RETRY", ["ARTICLE"])
    return p


def _fact_rows():
    return [
        {
            "reason_code": "FACT_UNSUPPORTED_CLAIM",
            "message": "unsupported vague quantified claim: 数ヶ月",
            "severity": "HARD",
        }
    ]


def _real_reader_decision_bundle():
    return [
        {
            "reason_code": "APPEAL_DECISION_VOICE_LOSS",
            "message": "decision_voice_missing",
            "severity": "REVIEW",
        },
        {
            "reason_code": "READER_NON_ENGINEER_ACCESS",
            "message": "reader_value_review:non_engineer_access_failure (Accessibility/Opening/Plain-Language/Jargon Translation/Non-Engineer Core Clarity)",
            "severity": "REVIEW",
        },
        {
            "reason_code": "READER_MULTI_AXIS_WEAKNESS",
            "message": "reader_value_review:multi_axis_reader_weakness (accessibility/reader_enjoyment/narrative_pull/jargon_translation/non_engineer_core_clarity/reader_temperature_rhythm)",
            "severity": "REVIEW",
        },
    ]


def test_live_base_policy_hands_second_slot_to_reader_owner_after_fact_retry():
    p = _pipeline_with_live_like_base_policy()
    run208.install(p)

    assert p.should_attempt_dynamic_retry(
        _fact_rows(), _safe_evidence(), "article_revalidation"
    ) == (True, "repairable")

    assert p.should_attempt_dynamic_retry(
        _real_reader_decision_bundle(), _safe_evidence(), "article_revalidation"
    ) == (True, "run341_production_reader_repair")

    assert p.should_attempt_dynamic_retry(
        _real_reader_decision_bundle(), _safe_evidence(), "article_revalidation"
    ) == (False, "run360_reader_repair_already_spent")
    assert p.MAX_QUALITY_RETRIES == 2


def test_second_fact_retry_remains_blocked_after_base_owner_spent():
    p = _pipeline_with_live_like_base_policy()
    run208.install(p)

    assert p.should_attempt_dynamic_retry(
        _fact_rows(), _safe_evidence(), "article_revalidation"
    )[0] is True
    assert p.should_attempt_dynamic_retry(
        _fact_rows(), _safe_evidence(), "article_revalidation"
    ) == (False, "run360_base_quality_retry_already_spent")


def test_lone_decision_voice_review_cannot_steal_reader_owner():
    p = _pipeline_with_live_like_base_policy()
    run208.install(p)
    p.should_attempt_dynamic_retry(_fact_rows(), _safe_evidence(), "article_revalidation")

    rows = [{
        "reason_code": "APPEAL_DECISION_VOICE_LOSS",
        "message": "decision_voice_missing",
        "severity": "REVIEW",
    }]
    assert p.should_attempt_dynamic_retry(
        rows, _safe_evidence(), "article_revalidation"
    ) == (False, "run360_base_quality_retry_already_spent")


def test_unrelated_review_cannot_steal_reader_owner():
    p = _pipeline_with_live_like_base_policy()
    run208.install(p)
    p.should_attempt_dynamic_retry(_fact_rows(), _safe_evidence(), "article_revalidation")

    rows = [{
        "reason_code": "APPEAL_AI_STYLE_COMPOSITE",
        "message": "ai_style_composite_high",
        "severity": "REVIEW",
    }]
    assert p.should_attempt_dynamic_retry(
        rows, _safe_evidence(), "article_revalidation"
    ) == (False, "run360_base_quality_retry_already_spent")


def test_hard_companion_still_blocks_reader_owner():
    p = _pipeline_with_live_like_base_policy()
    run208.install(p)
    p.should_attempt_dynamic_retry(_fact_rows(), _safe_evidence(), "article_revalidation")

    rows = _real_reader_decision_bundle() + [{
        "reason_code": "FACT_UNSUPPORTED_CLAIM",
        "message": "unsupported guarantee",
        "severity": "HARD",
    }]
    assert p.should_attempt_dynamic_retry(
        rows, _safe_evidence(), "article_revalidation"
    ) == (False, "run360_base_quality_retry_already_spent")


def test_combined_reader_and_decision_voice_bundle_receives_reader_repair_contract():
    p = _pipeline_with_live_like_base_policy()
    run208.install(p)

    instruction, sections = p.build_dynamic_retry_instruction(
        _real_reader_decision_bundle()
    )
    assert "Reader Repair｜Factを固定した読者導線修正" in instruction
    assert "RUN359 Reader Repair Execution Contract" in instruction
    assert "Decision Voiceを復元する" in instruction
    assert "新しいFact、利用経験、感情、因果、保証、緊急度を作らず" in instruction
    assert sections == ["ARTICLE"]


def test_unsafe_evidence_never_hands_off_to_reader_owner():
    for evidence in (
        None,
        {"state": "INSUFFICIENT", "decision_scope_safe": True},
        {"state": "SUFFICIENT", "decision_scope_safe": False},
    ):
        p = _pipeline_with_live_like_base_policy()
        run208.install(p)
        p.should_attempt_dynamic_retry(_fact_rows(), _safe_evidence(), "article_revalidation")
        assert p.should_attempt_dynamic_retry(
            _real_reader_decision_bundle(), evidence, "article_revalidation"
        ) == (False, "run360_base_quality_retry_already_spent")
