from __future__ import annotations

import os

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GH_PAT", "test-token")
os.environ.setdefault("GEMINI_QUOTA_PROJECT_ID", "test-project")

import pipeline


def _failures(article: str, source: str):
    return pipeline._find_unsupported_numeric_claims(article, source, {})


def test_27_generic_count_is_grounded_by_same_number_and_summary_entity():
    article = "通常の制約を無視する指示を含む要約を27件特定しました。"
    source = "An unreleased research model inserted unrelated instructions. We identified 27 affected summaries."
    failures = _failures(article, source)
    assert not any("27件" in item for item in failures), failures


def test_generic_count_does_not_match_same_number_for_different_entity():
    article = "通常の制約を無視する指示を含む要約を27件特定しました。"
    source = "We identified 27 affected API keys in public repositories."
    failures = _failures(article, source)
    assert any("27件" in item for item in failures), failures


def test_generic_count_requires_meaningful_entity_near_claim():
    article = "合計27件が確認されました。"
    source = "We identified 27 affected summaries."
    failures = _failures(article, source)
    assert any("27件" in item for item in failures), failures


def test_package_count_can_cross_japanese_english_counter_boundary():
    article = "不審なパッケージを2,000件確認しました。"
    source = "Researchers observed 2,000 suspicious packages."
    failures = _failures(article, source)
    assert not any("2,000件" in item for item in failures), failures


def test_unrelated_same_number_never_legalizes_count_claim():
    article = "不審なパッケージを2,000件確認しました。"
    source = "The report mentions 2,000 users and 14 suspicious packages."
    failures = _failures(article, source)
    assert any("2,000件" in item for item in failures), failures
