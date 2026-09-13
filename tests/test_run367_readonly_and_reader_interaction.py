"""Canonical installed runtime, with network physically blocked by the fixture."""
import copy
import pytest
from run367_readonly_inventory_audit import offline_runtime, classify, extract_markdown_manuscript
import run208_reader_value_repair as reader
import run284_reader_recovery_precision as precision


@pytest.fixture
def runtime():
    with offline_runtime() as pipeline:
        yield pipeline


def row(message):
    return {"message": "reader_value_review:" + message, "severity": "REVIEW"}


def test_markdown_extraction_keeps_nested_code_fences():
    source = (
        "```markdown\n"
        "# title\n\n"
        "before\n\n"
        "```python\nprint('nested')\n```\n\n"
        "after\n"
        "```"
    )
    manuscript = extract_markdown_manuscript(source)
    assert manuscript is not None
    assert "print('nested')" in manuscript
    assert manuscript.endswith("after")


def test_three_candidates_each_get_one_repair_without_order_lock(runtime):
    evidence = {"state": runtime.EVIDENCE_SUFFICIENT, "decision_scope_safe": True}
    for label in ["dense_report_cluster", "non_engineer_access_failure", "final_surface_summary_jargon_cluster"]:
        # Exercise the actual first-pass Writer boundary, not a hand-reset counter.
        runtime.build_decision_prompt("offline candidate", "https://example.test/source", 0, "saved source")
        rows = [row(label)]
        original = copy.deepcopy(rows)
        allowed, _ = runtime.should_attempt_dynamic_retry(rows, evidence, "new")
        assert allowed
        assert runtime.should_attempt_dynamic_retry(rows, evidence, "new")[0] is False
        instruction, _ = runtime.build_dynamic_retry_instruction(rows)
        assert reader.READER_REPAIR_CONTRACT in instruction
        assert "記事全体の再構成や新事実の追加はしない" not in instruction
        assert precision.RETRY_PRESERVATION_CONTRACT not in precision.retry_feedback_with_preservation(instruction, "saved draft")
        assert rows == original


def test_mixed_fact_retry_keeps_local_preservation(runtime):
    rows = [row("dense_report_cluster"), {"message": "FACT_NUMERICAL_MISMATCH", "severity": runtime.GATE_SEVERITY_HARD}]
    instruction, _ = runtime.build_dynamic_retry_instruction(rows)
    assert reader.READER_REPAIR_CONTRACT not in instruction
    assert "記事全体の再構成や新事実の追加はしない" in instruction
    assert precision.RETRY_PRESERVATION_CONTRACT in precision.retry_feedback_with_preservation(instruction, "saved draft")


def test_reader_failures_still_block_and_no_source_evidence_is_invented(runtime):
    from run248_first_real_publish_quality_calibration import extra_reader_value_issues
    signals = dict.fromkeys(["accessibility", "jargon_translation", "non_engineer_core_clarity", "information_budget"], "REVIEW")
    assert extra_reader_value_issues(signals)
    assert classify(extra_reader_value_issues(signals), True, True) == "gate_failed"
    assert classify([], True, True) == "surface_clean_but_unproven"
    assert classify([], True, False) == "evidence_insufficient"
    assert classify([], False, True) == "unsupported"


def test_network_attempt_is_blocked(runtime):
    import requests
    with pytest.raises(RuntimeError, match="forbids network"):
        requests.get("https://example.test")
