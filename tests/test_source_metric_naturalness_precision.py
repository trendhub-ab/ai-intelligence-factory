from __future__ import annotations

import pytest

import editorial_naturalness as en
from evidence_authority import classify_evidence
import run223_technical_claim_precision as run223


@pytest.mark.parametrize("raw_source_type", ["secondary_news", "news", "explainer", "analysis"])
def test_explicit_secondary_material_cannot_be_promoted_by_primary_role(raw_source_type):
    out = classify_evidence(
        url="https://analysis.example/vendor-change",
        role="PRIMARY_SOURCE",
        raw_source_type=raw_source_type,
        label="Independent news analysis",
        pipeline_source="HackerNews",
    )
    assert out["source_type"] in {"SECONDARY_NEWS", "SUPPLEMENTAL"}
    assert out["authority_class"] == "SECONDARY"
    assert out["decision_eligible"] is False


def test_auc_value_cannot_be_relabeled_as_accuracy_or_precision():
    source = "The evaluation reports ROC AUC of 0.91 on the held-out benchmark."

    for wrong_metric in ("accuracy", "precision"):
        failures = run223.technical_claim_failures(
            {"note_draft": f"The model achieved {wrong_metric} of 0.91 on the held-out benchmark."},
            source,
        )
        assert any("metric_semantics_changed:" in failure for failure in failures), failures

    preserved = run223.technical_claim_failures(
        {"note_draft": "The model achieved ROC AUC of 0.91 on the held-out benchmark."},
        source,
    )
    assert not any("metric_semantics_changed:" in failure for failure in preserved), preserved


def test_strong_hype_is_advisory_retry_feedback_not_a_new_gate():
    article = (
        "## 評価\n"
        "これは革命的で圧倒的な進化です。公式資料で確認できる仕様と測定条件を比較します。"
    )
    before = en.ai_style_composite_signals(article, [])
    signals = en.naturalness_v2_signals(article)

    assert signals["repair_recommended"] is True
    assert signals["strong_hype_sections"] == [1]

    contract = en.build_naturalness_retry_contract(article)
    assert "naturalness-v2" in contract
    assert "節 1" in contract
    assert "革命的" in contract
    assert "圧倒的" in contract
    assert "煽り" in contract

    after = en.ai_style_composite_signals(article, [])
    assert (after["score"], after["high"]) == (before["score"], before["high"])
