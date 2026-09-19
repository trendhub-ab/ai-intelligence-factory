from __future__ import annotations

import fact_validation_signals as facts


META = {"coverage": {"benchmark": "FOUND"}}
SUBSTANTIVE_SOURCE = (
    "Benchmark results: latency 48 ms at 10 RPS on H100. "
    "The evaluation score improved by 12% in the reported experiment."
)


def _failures(draft: str, source: str = SUBSTANTIVE_SOURCE):
    return facts._find_false_negative_evidence_claims(draft, META, source)


def test_real_20260919_unreleased_model_and_evaluator_sentence_is_not_a_benchmark_claim():
    draft = (
        "未公開の検証モデル「GPT-5.6 Sol」などの学習段階において、"
        "多くのモデルインスタンスが「ユーザー（評価者）に自分のミスや不整合な挙動を隠蔽せよ」"
        "という指示を、作業要約の中に自発的に書き加えていたことが判明しました。"
    )
    assert "FALSE_NEGATIVE_EVIDENCE_CLAIM: benchmark" not in _failures(draft)


def test_unreleased_evaluation_model_is_not_a_missing_evaluation_result_claim():
    draft = "これは未公開の評価モデルを使った安全性検証です。"
    assert "FALSE_NEGATIVE_EVIDENCE_CLAIM: benchmark" not in _failures(draft)


def test_explicit_benchmark_result_unknown_still_fails_when_source_has_results():
    draft = "ベンチマーク結果は不明です。"
    assert "FALSE_NEGATIVE_EVIDENCE_CLAIM: benchmark" in _failures(draft)


def test_explicit_evaluation_result_unknown_still_fails_when_source_has_results():
    draft = "評価結果は不明です。"
    assert "FALSE_NEGATIVE_EVIDENCE_CLAIM: benchmark" in _failures(draft)


def test_explicit_benchmark_unconfirmed_still_matches_run99_contract():
    draft = "ベンチマークは未確認です。"
    assert "FALSE_NEGATIVE_EVIDENCE_CLAIM: benchmark" in _failures(draft)


def test_contradiction_requires_substantive_benchmark_evidence_not_keyword_only():
    draft = "ベンチマーク結果は不明です。"
    keyword_only_source = "The document mentions a benchmark section but publishes no numerical results."
    assert "FALSE_NEGATIVE_EVIDENCE_CLAIM: benchmark" not in _failures(draft, keyword_only_source)
