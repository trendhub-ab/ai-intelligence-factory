import json
from pathlib import Path

import pytest

from hybrid_fact_boundary import FactBoundaryError, assert_fact_boundary, audit_fact_boundary

INPUT = 'tests/fixtures/groq/article_parity_B0049_input.json'
RED_TEAM = 'tests/fixtures/groq/historical_writer_fact_boundary_cases.json'


def _source():
    return json.loads(Path(INPUT).read_text(encoding='utf-8'))['source_context']


def test_source_supported_concrete_facts_pass():
    article = (
        'AstraはExploitBenchで100%を記録した。'
        '2026年6〜8月に公開された高深刻度V8脆弱性20件を評価し、2件のzero-day脆弱性を発見した。'
        '結果はDaybreak Blue access条件を反映する。'
    )
    report = audit_fact_boundary(_source(), article)
    assert report['passed'] is True
    assert report['violations'] == []


def test_unsupported_number_and_identifier_fail_closed():
    article = 'AstraはExploitBenchで99%を記録し、新しいCyberBenchXでも評価された。'
    report = audit_fact_boundary(_source(), article)
    assert report['passed'] is False
    kinds = {row['type'] for row in report['violations']}
    assert 'unsupported_numeric_fact' in kinds
    assert 'unsupported_technical_identifier' in kinds
    with pytest.raises(FactBoundaryError, match='fact_boundary_failed'):
        assert_fact_boundary(_source(), article)


def test_unsupported_url_is_rejected():
    report = audit_fact_boundary(_source(), '詳細はhttps://example.com/secretを参照。')
    assert any(row['type'] == 'unsupported_url' for row in report['violations'])


@pytest.mark.parametrize('phrase,kind', [
    ('一般に通常の対話画面で触れられる設定だ。', 'availability_inflation'),
    ('データ混入の可能性が極めて低い評価だ。', 'contamination_certainty_inflation'),
    ('まだ誰も発見していなかった未知の不具合を見つけた。', 'zero_day_inflation'),
    ('Astraは開発中の新しい基盤モデルだ。', 'development_state_inflation'),
])
def test_known_writer_fact_inflation_modes_are_rejected(phrase, kind):
    report = audit_fact_boundary(_source(), phrase)
    assert report['passed'] is False
    assert any(row['type'] == kind for row in report['violations'])


@pytest.mark.parametrize('phrase,kind', [
    ('拒否訓練は不適切な指示を断る訓練だ。', 'refusal_training_function_inference'),
    ('system safety classifierは安全性を判定する仕組みだ。', 'classifier_function_inference'),
    ('監視によってログ収集を行う。', 'monitoring_function_inference'),
    ('misalignment detectionはAIの意図を読む仕組みだ。', 'misalignment_function_inference'),
])
def test_safety_name_to_function_inference_is_rejected(phrase, kind):
    report = audit_fact_boundary(_source(), phrase)
    assert report['passed'] is False
    assert any(row['type'] == kind for row in report['violations'])


def test_general_editorial_language_without_new_concrete_fact_passes():
    article = '数字の大きさだけで判断せず、どの条件で得られた結果なのかを分けて読む必要がある。'
    assert audit_fact_boundary(_source(), article)['passed'] is True


def test_nfkc_normalization_does_not_create_false_numeric_delta():
    source = '評価は100%で、対象は20件だった。'
    article = '評価は１００％で、対象は２０件だった。'
    assert audit_fact_boundary(source, article)['passed'] is True


def test_historical_writer_red_team_corpus_has_zero_false_negative_and_zero_false_positive():
    fixture = json.loads(Path(RED_TEAM).read_text(encoding='utf-8'))
    source = _source()
    tp = tn = fp = fn = 0
    failures = []
    for case in fixture['cases']:
        report = audit_fact_boundary(source, case['text'])
        actual_pass = bool(report['passed'])
        expected_pass = bool(case['expected_pass'])
        if expected_pass and actual_pass:
            tn += 1
        elif expected_pass and not actual_pass:
            fp += 1
            failures.append((case['id'], 'false_positive', report['violations']))
        elif not expected_pass and not actual_pass:
            tp += 1
        else:
            fn += 1
            failures.append((case['id'], 'false_negative', report['violations']))
        actual_types = {row['type'] for row in report['violations']}
        for expected_type in case.get('expected_types') or []:
            if expected_type not in actual_types:
                failures.append((case['id'], 'missing_expected_type', expected_type, sorted(actual_types)))

    recall = tp / (tp + fn) if (tp + fn) else 1.0
    specificity = tn / (tn + fp) if (tn + fp) else 1.0
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    metrics = {
        'cases': len(fixture['cases']),
        'true_positive': tp,
        'true_negative': tn,
        'false_positive': fp,
        'false_negative': fn,
        'recall': recall,
        'specificity': specificity,
        'precision': precision,
    }
    assert failures == [], {'metrics': metrics, 'failures': failures}
    assert metrics == {
        'cases': 16,
        'true_positive': 8,
        'true_negative': 8,
        'false_positive': 0,
        'false_negative': 0,
        'recall': 1.0,
        'specificity': 1.0,
        'precision': 1.0,
    }
