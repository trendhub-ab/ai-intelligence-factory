from __future__ import annotations

from types import SimpleNamespace

import run208_reader_value_repair as r208
import run249_final_publication_surface_gate as r249


def _reader_row(message: str) -> dict:
    return {"message": message, "severity": "REVIEW"}


def _pipeline_for_run208():
    def original_retry(reason_rows, evidence_result, candidate_origin="new"):
        return False, "reader_value_review_no_retry"

    def build_prompt(*args, **kwargs):
        return "BASE PROMPT"

    def build_retry_instruction(reason_rows):
        return "BASE RETRY", []

    return SimpleNamespace(
        should_attempt_dynamic_retry=original_retry,
        build_decision_prompt=build_prompt,
        build_dynamic_retry_instruction=build_retry_instruction,
        EVIDENCE_SUFFICIENT="SUFFICIENT",
        GATE_SEVERITY_HARD="HARD_BLOCK",
    )


def test_article_revalidation_reader_retry_matches_fresh_production():
    pipeline = _pipeline_for_run208()
    r208.install(pipeline)
    rows = [_reader_row("reader_value_review:multi_axis_reader_weakness (accessibility/jargon_translation)")]
    evidence = {"state": "SUFFICIENT", "decision_scope_safe": True}

    fresh = pipeline.should_attempt_dynamic_retry(rows, evidence, "new")
    validation = pipeline.should_attempt_dynamic_retry(rows, evidence, "article_revalidation")

    assert fresh == (True, "run341_production_reader_repair")
    assert validation == fresh
    assert pipeline.RUN354_VALIDATION_RETRY_PARITY is True


def test_article_revalidation_parity_does_not_relax_evidence_safety():
    pipeline = _pipeline_for_run208()
    r208.install(pipeline)
    rows = [_reader_row("reader_value_review:non_engineer_access_failure")]

    assert pipeline.should_attempt_dynamic_retry(
        rows, {"state": "INSUFFICIENT", "decision_scope_safe": True}, "article_revalidation"
    ) == (False, "reader_value_review_no_retry")
    assert pipeline.should_attempt_dynamic_retry(
        rows, {"state": "SUFFICIENT", "decision_scope_safe": False}, "article_revalidation"
    ) == (False, "reader_value_review_no_retry")


def test_article_revalidation_parity_does_not_open_unrelated_origins():
    pipeline = _pipeline_for_run208()
    r208.install(pipeline)
    rows = [_reader_row("reader_value_review:dense_report_cluster")]
    evidence = {"state": "SUFFICIENT", "decision_scope_safe": True}

    assert pipeline.should_attempt_dynamic_retry(
        rows, evidence, "existing_editorial_recovery"
    ) == (False, "reader_value_review_no_retry")


def test_final_surface_does_not_rescore_article_body_reader_axes():
    def should_not_be_called(article):
        raise AssertionError("Run249 must not re-run article-wide Reader axes")

    pipeline = SimpleNamespace(_reader_experience_signals=should_not_be_called)

    def build_manuscript(article, *args, **kwargs):
        return article

    def build_summary(parsed):
        return {
            "what": "平易な説明です。",
            "why": "読者への意味を説明します。",
            "decision": "まず小さく試します。",
        }

    issues, summary, projection = r249.final_surface_issues(
        pipeline,
        build_manuscript,
        build_summary,
        {
            "title_text": "普通のタイトル",
            "note_draft": "専門語が多い本文でも、Reader bodyの判定責任はRun248側にあります。",
        },
    )

    assert issues == []
    assert summary["decision"] == "まず小さく試します。"
    assert "専門語が多い本文" in projection


def test_final_surface_still_blocks_late_summary_jargon_cluster():
    pipeline = SimpleNamespace(_reader_experience_signals=lambda article: {})

    def build_manuscript(article, *args, **kwargs):
        return article

    def build_summary(parsed):
        return {
            "what": "ZXQ RST-CORE VLMPIPE VectorKernel TensorRouter Orchestratorを統合した技術更新です。",
            "why": "ABC DEF-GATE RetrievalKernel MemoryRouter TokenPlanner Schedulerを接続するため重要です。",
            "decision": "まず小さく試します。",
        }

    issues, _summary, _projection = r249.final_surface_issues(
        pipeline,
        build_manuscript,
        build_summary,
        {"title_text": "普通のタイトル", "note_draft": "読みやすい本文です。"},
    )

    assert any("final_surface_summary_jargon_cluster" in issue for issue in issues)


def test_final_surface_still_detects_unbalanced_title_quote():
    pipeline = SimpleNamespace(_reader_experience_signals=lambda article: {})

    issues, _summary, _projection = r249.final_surface_issues(
        pipeline,
        lambda article, *args, **kwargs: article,
        lambda parsed: {"what": "説明", "why": "意味", "decision": "判断"},
        {"title_text": "「閉じていないタイトル", "note_draft": "本文"},
    )

    assert any("final_surface_title_unbalanced_kagi" in issue for issue in issues)


def test_final_surface_still_detects_malformed_assembled_japanese():
    pipeline = SimpleNamespace(_reader_experience_signals=lambda article: {})

    issues, _summary, _projection = r249.final_surface_issues(
        pipeline,
        lambda article, *args, **kwargs: article + " 主主要な判断です。",
        lambda parsed: {"what": "説明", "why": "意味", "decision": "判断"},
        {"title_text": "普通のタイトル", "note_draft": "本文"},
    )

    assert any("malformed_japanese_surface:duplicated_primary_modifier" in issue for issue in issues)
