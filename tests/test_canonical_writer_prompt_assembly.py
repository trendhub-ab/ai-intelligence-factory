from types import SimpleNamespace

import canonical_article_contract as cac
import reader_value_review_bridge as bridge
import run208_reader_value_repair as repair
import run226_reader_delight_planning as run226
import run228_reader_rhythm_planning as run228


def _pipeline():
    return SimpleNamespace(
        build_decision_prompt=lambda *a, **k: "SOURCE BOUNDARY\nEvidence-to-Decision",
        build_dynamic_retry_instruction=lambda rows: ("BASE RETRY", ["ARTICLE"]),
        validate_human_appeal_gate=lambda parsed, peers=None: ("ACCEPTABLE", []),
        should_attempt_dynamic_retry=lambda rows, evidence, origin="new": (False, "base_denied"),
        GATE_SEVERITY_HARD="HARD",
        GATE_SEVERITY_REVIEW="REVIEW",
        EVIDENCE_SUFFICIENT="SUFFICIENT",
        MAX_QUALITY_RETRIES=1,
    )


def test_production_editorial_stack_has_one_canonical_contract():
    p = _pipeline()
    for layer in (run226, run228, bridge, repair):
        layer.install(p)
    prompt = p.build_decision_prompt()
    assert prompt.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER) == 1
    assert prompt.count(cac.CANONICAL_FINAL_READER_CHECK_MARKER) == 1
    assert "SOURCE BOUNDARY" in prompt
    assert "Evidence-to-Decision" in prompt


def test_run228_is_safe_when_installed_without_run226():
    p = _pipeline()
    run228.install(p)
    prompt = p.build_decision_prompt()
    assert prompt.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER) == 1
    assert prompt.count(cac.CANONICAL_FINAL_READER_CHECK_MARKER) == 1


def test_run208_is_safe_when_installed_without_run226():
    p = _pipeline()
    repair.install(p)
    prompt = p.build_decision_prompt()
    assert prompt.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER) == 1


def test_long_legacy_reader_contract_is_not_repeated_in_fresh_prompt():
    p = _pipeline()
    for layer in (run226, run228, bridge, repair):
        layer.install(p)
    prompt = p.build_decision_prompt()
    assert prompt.count("記事を全部説明するな") == 1
    assert prompt.count("Reader Repair｜Factを固定した読者導線修正") == 0
    assert "原則2〜3個" not in prompt
    assert "最大3項目" not in prompt
