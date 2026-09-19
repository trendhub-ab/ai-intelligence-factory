from types import SimpleNamespace

import canonical_article_contract as cac
import run208_reader_value_repair as r208


def _row(message):
    return {"message": "reader_value_review:" + message, "severity": "REVIEW"}


def test_density_failure_gets_deletion_not_more_explanation_instruction():
    text = r208._run359_targeted_repair([_row("non_engineer_access_failure")])
    assert "専門語密度を下げる" in text
    assert "不要な名称を捨てる" in text
    assert "専門語を別の専門語で説明しない" in text
    assert "個数にかかわらず" in text


def test_final_summary_jargon_targets_source_sentences_not_gate_relaxation():
    text = r208._run359_targeted_repair([_row("final_surface_summary_jargon_cluster")])
    assert "30秒要約の素材を平易化する" in text
    assert "本文から自動抽出" in text
    assert "Factを削るのではなく" in text
    assert "閾値" not in text


def test_unrelated_reader_reason_does_not_invent_targeted_directive():
    assert r208._run359_targeted_repair([_row("title_flattening")]) == ""


def test_install_appends_targeted_contract_without_new_call_site():
    def retry(rows, evidence, origin="new"):
        return False, "reader_value_review_no_retry"

    def prompt(*args, **kwargs):
        return "BASE"

    def retry_instruction(rows):
        return "RETRY", ["reader"]

    pipeline = SimpleNamespace(
        should_attempt_dynamic_retry=retry,
        build_decision_prompt=prompt,
        build_dynamic_retry_instruction=retry_instruction,
        GATE_SEVERITY_HARD="HARD",
        EVIDENCE_SUFFICIENT="SUFFICIENT",
    )
    r208.install(pipeline)
    instruction, sections = pipeline.build_dynamic_retry_instruction([
        _row("multi_axis_reader_weakness"),
        _row("final_surface_summary_jargon_cluster"),
    ])
    assert "Reader Repair" in instruction
    assert "RUN359 Reader Repair Execution Contract" in instruction
    assert "専門語密度を下げる" in instruction
    assert "30秒要約の素材を平易化する" in instruction
    assert sections == ["reader"]
    assert pipeline.RUN359_READER_REPAIR_EXECUTION is True


def test_reader_retry_budget_and_evidence_safety_remain_authoritative():
    calls = {"count": 0}

    def retry(rows, evidence, origin="new"):
        calls["count"] += 1
        return False, "reader_value_review_no_retry"

    pipeline = SimpleNamespace(
        should_attempt_dynamic_retry=retry,
        build_decision_prompt=lambda: "BASE",
        build_dynamic_retry_instruction=lambda rows: ("RETRY", []),
        GATE_SEVERITY_HARD="HARD",
        EVIDENCE_SUFFICIENT="SUFFICIENT",
    )
    r208.install(pipeline)
    rows = [_row("non_engineer_access_failure")]
    assert pipeline.should_attempt_dynamic_retry(rows, {"state": "INSUFFICIENT", "decision_scope_safe": False}, "new") == (False, "reader_value_review_no_retry")
    assert pipeline.should_attempt_dynamic_retry(rows, {"state": "SUFFICIENT", "decision_scope_safe": True}, "new") == (True, "run341_production_reader_repair")
    # Safe reader-only residual is owned directly by Reader Repair; the generic retry owner
    # is consulted only for the unsafe case.
    assert calls["count"] == 1


def test_reader_repair_uses_canonical_contract_once():
    pipeline = SimpleNamespace(
        should_attempt_dynamic_retry=lambda rows, evidence, origin="new": (
            False, "reader_value_review_no_retry"
        ),
        build_decision_prompt=lambda *a, **k: "BASE",
        build_dynamic_retry_instruction=lambda rows: ("BASE RETRY", ["reader"]),
        GATE_SEVERITY_HARD="HARD",
        EVIDENCE_SUFFICIENT="SUFFICIENT",
    )
    r208.install(pipeline)
    instruction, _ = pipeline.build_dynamic_retry_instruction(
        [_row("non_engineer_access_failure")]
    )
    assert r208.READER_REPAIR_CONTRACT == cac.canonical_reader_repair_contract()
    assert instruction.count("Reader Repair｜Factを固定した読者導線修正") == 1
    assert "段落・見出しを再編" in instruction
    assert "新しい数値、製品名、API名、比較対象" in instruction


def test_mixed_publication_and_reader_failure_never_gets_reader_only_contract():
    pipeline = SimpleNamespace(
        should_attempt_dynamic_retry=lambda rows, evidence, origin="new": (
            True, "base_quality_retry"
        ),
        build_decision_prompt=lambda *a, **k: "BASE",
        build_dynamic_retry_instruction=lambda rows: ("BASE RETRY", ["ARTICLE"]),
        GATE_SEVERITY_HARD="HARD",
        EVIDENCE_SUFFICIENT="SUFFICIENT",
    )
    r208.install(pipeline)
    rows = [
        _row("non_engineer_access_failure"),
        {"message": "score_narrative_mismatch", "severity": "REVIEW"},
    ]
    instruction, _ = pipeline.build_dynamic_retry_instruction(rows)
    assert "Reader Repair｜Factを固定した読者導線修正" not in instruction


def test_reader_repair_remains_reachable_after_base_fact_retry_is_spent():
    calls = {"count": 0}

    def retry(rows, evidence, origin="new"):
        calls["count"] += 1
        return True, "repairable"

    pipeline = SimpleNamespace(
        should_attempt_dynamic_retry=retry,
        build_decision_prompt=lambda *a, **k: "BASE",
        build_dynamic_retry_instruction=lambda rows: ("RETRY", []),
        GATE_SEVERITY_HARD="HARD",
        EVIDENCE_SUFFICIENT="SUFFICIENT",
    )
    r208.install(pipeline)
    safe = {"state": "SUFFICIENT", "decision_scope_safe": True}

    fact_rows = [{"message": "unsupported market-standard claim: 業界標準", "severity": "HARD"}]
    assert pipeline.should_attempt_dynamic_retry(fact_rows, safe, "article_revalidation") == (True, "repairable")

    reader_rows = [
        _row("non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity)"),
        _row("multi_axis_reader_weakness (accessibility/reader_enjoyment/narrative_pull)"),
    ]
    assert pipeline.should_attempt_dynamic_retry(reader_rows, safe, "article_revalidation") == (
        True, "run341_production_reader_repair"
    )
    assert calls["count"] == 1

    assert pipeline.should_attempt_dynamic_retry(reader_rows, safe, "article_revalidation") == (
        False, "run360_reader_repair_already_spent"
    )
