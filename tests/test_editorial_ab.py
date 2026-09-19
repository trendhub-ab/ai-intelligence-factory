"""Counterfactual controls for label-blind offline article comparison."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def evaluator():
    path = ROOT / 'tools/editorial_ab.py'
    assert path.exists(), 'Offline comparison path is not implemented'
    spec = importlib.util.spec_from_file_location('editorial_ab', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case():
    return {
        'id': 'control', 'evidence': {'url': 'https://example.com/fixture',
          'text': '公開資料では上限は10件です。試験環境のみで検証しました。',
          'facts': ['上限は10件です', '試験環境のみで検証'],
          'required_evidence': ['試験環境のみで検証']},
        'conditions': {'audience': '非専門家', 'decision': '限定検証'},
        'old': '公開資料では上限は10件です。試験環境のみで検証しました。',
        'new': '公開資料では上限は10件です。試験環境のみで検証しました。',
    }


def test_identical_articles_tie_and_labels_cannot_affect_metrics():
    m = evaluator()
    c = case()
    r = m.compare(c)
    assert r['winner'] == 'tie'
    assert len(r['old']['metrics']) == 11
    c['new'] += '\n\n上限は999件です。私が使ってみたところ完全に安全です。'
    r = m.compare(c)
    assert r['winner'] == 'old'
    c['old'], c['new'] = c['new'], c['old']
    swapped = m.compare(c)
    assert swapped['winner'] == 'new'
    assert swapped['new'] == r['old']
    assert swapped['old'] == r['new']


def test_lost_qualifier_and_fact_cannot_win_on_style():
    m = evaluator()
    c = case()
    c['new'] = 'スマホで困ったことはありませんか？なぜでしょう。私なら比較検証します。'
    r = m.compare(c)
    assert r['new']['metrics']['Fact retention'] == 0
    assert r['new']['metrics']['Evidence retention'] == 0
    assert not r['new']['eligible']
    assert r['winner'] == 'old'


def test_empty_evidence_is_rejected_instead_of_scored_perfect():
    m = evaluator()
    c = case()
    c['evidence']['facts'] = []
    with pytest.raises(ValueError):
        m.compare(c)


def test_fixture_corpus_reports_new_win_old_win_and_tie():
    m = evaluator()
    cases = json.loads((ROOT / 'tests/fixtures/editorial_ab/cases.json').read_text())['cases']
    results = [m.compare(c) for c in cases]
    assert {'old', 'new', 'tie'} <= {r['winner'] for r in results}
    for c, result in zip(cases, results):
        swapped = deepcopy(c)
        swapped['old'], swapped['new'] = c['new'], c['old']
        inverted = m.compare(swapped)
        assert result['old'] == inverted['new']
        assert result['new'] == inverted['old']


def test_prompt_pair_uses_frozen_baseline_and_rejects_changed_evidence():
    m = evaluator()
    c = json.loads((ROOT / 'tests/fixtures/editorial_ab/cases.json').read_text())['cases'][0]
    pair = m.build_prompt_pair(c)
    assert pair['old']['system_instruction'] is None
    assert 'AIIF Editor Persona' in pair['new']['system_instruction']
    for version in pair.values():
        assert c['evidence']['text'] in version['prompt']
    assert 'AIIF_EDITORIAL_STORY_BRIEF_V1' not in pair['old']['prompt']
    assert pair['new']['prompt'].count('AIIF_EDITORIAL_STORY_BRIEF_V1') == 1
    c['evidence']['text'] += '追加条件。'
    with pytest.raises(ValueError, match='baseline'):
        m.build_prompt_pair(c)
