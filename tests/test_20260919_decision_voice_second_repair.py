from __future__ import annotations

import types

import run208_reader_value_repair as run208


def _pipeline():
    pipeline = types.SimpleNamespace()
    pipeline.GATE_SEVERITY_HARD = "HARD"
    pipeline.EVIDENCE_SUFFICIENT = "SUFFICIENT"
    pipeline.MAX_QUALITY_RETRIES = 1
    pipeline.should_attempt_dynamic_retry = lambda rows, evidence, origin="new": (True, "repairable")
    pipeline.build_decision_prompt = lambda *args, **kwargs: "BASE PROMPT"
    pipeline.build_dynamic_retry_instruction = lambda rows: (
        "BASE RETRY\nAPPEAL_DECISION_VOICE_LOSS: restore existing editorial judgment only.",
        ["voice"],
    )
    return pipeline


def _safe_evidence():
    return {"state": "SUFFICIENT", "decision_scope_safe": True}


def _decision_voice_rows():
    return [{
        "reason_code": "APPEAL_DECISION_VOICE_LOSS",
        "message": "decision_voice_missing",
        "severity": "REVIEW",
    }]


def test_persistent_decision_voice_gets_one_second_bounded_repair_after_base_retry():
    pipeline = _pipeline()
    run208.install(pipeline)

    first = pipeline.should_attempt_dynamic_retry(
        _decision_voice_rows(), _safe_evidence(), "article_revalidation"
    )
    second = pipeline.should_attempt_dynamic_retry(
        _decision_voice_rows(), _safe_evidence(), "article_revalidation"
    )
    third = pipeline.should_attempt_dynamic_retry(
        _decision_voice_rows(), _safe_evidence(), "article_revalidation"
    )

    assert first == (True, "repairable")
    assert second == (True, "run418_decision_voice_second_repair")
    assert third == (False, "run360_reader_repair_already_spent")
    assert pipeline.MAX_QUALITY_RETRIES == 2


def test_decision_voice_second_repair_is_not_a_mixed_or_hard_escape_hatch():
    mixed = [
        *_decision_voice_rows(),
        {
            "reason_code": "READER_NON_ENGINEER_ACCESS",
            "message": "reader_value_review:non_engineer_access_failure",
            "severity": "REVIEW",
        },
    ]
    hard = [{
        "reason_code": "APPEAL_DECISION_VOICE_LOSS",
        "message": "decision_voice_missing",
        "severity": "HARD",
    }]

    for rows in (mixed, hard):
        pipeline = _pipeline()
        run208.install(pipeline)
        assert pipeline.should_attempt_dynamic_retry(rows, _safe_evidence(), "article_revalidation") == (
            True,
            "repairable",
        )
        assert pipeline.should_attempt_dynamic_retry(rows, _safe_evidence(), "article_revalidation") == (
            False,
            "run360_base_quality_retry_already_spent",
        )


def test_decision_voice_retry_instruction_preserves_existing_meaning_and_forbids_invention():
    pipeline = _pipeline()
    run208.install(pipeline)

    instruction, sections = pipeline.build_dynamic_retry_instruction(_decision_voice_rows())

    assert sections == ["voice"]
    assert "Decision Voice Repair" in instruction
    assert "Fact / Evidence / Decision / Score / Action" in instruction
    assert "新しい施策、数値、経験、感情、因果、保証" in instruction
    assert "前稿にないPoCやテストを勝手に提案しない" in instruction
