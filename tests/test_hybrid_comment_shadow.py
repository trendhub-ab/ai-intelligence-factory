import json
from pathlib import Path

import pytest

from hybrid_comment_shadow import (
    COMMENT_SHADOW_FIELDS,
    CommentShadowError,
    build_comment_shadow_fixture,
    validate_comment_shadow_output,
)

INPUT='tests/fixtures/groq/article_parity_B0049_input.json'
PLAN='tests/fixtures/groq/two_pass_v3_plan_safe_report.json'


def _valid_output():
    return {
        'what':'AstraはPreparedness Framework上のCritical cybersecurity capability thresholdに到達した最初のモデルと説明されている。',
        'why_important':'ExploitBenchで100%を記録するなど能力向上が確認された一方、結果はDaybreak Blue access条件を反映するため、評価条件を分けて判断する必要がある。',
        'decision_reason':'技術的な影響は大きいが、一般利用条件は確認できていない。能力と利用条件を分け、追加の一次情報を確認して判断する。',
        'next_action':'一般利用条件と追加の一次情報を確認し、評価条件と実運用条件を分けて比較する。',
    }


def test_fixture_is_shadow_only_and_bound_to_fact_hash(tmp_path):
    fx=build_comment_shadow_fixture(INPUT,PLAN,str(tmp_path/'shadow.json'))
    report=json.loads(Path(PLAN).read_text(encoding='utf-8'))
    assert fx['mode']=='SHADOW_ONLY'
    assert fx['candidate_id']=='B0049'
    assert fx['provider_target']=='groq'
    assert fx['model_target']=='openai/gpt-oss-120b'
    assert fx['fact_envelope_sha256']==report['fact_envelope_sha256']
    assert set(fx['schema']['required'])==set(COMMENT_SHADOW_FIELDS)
    assert fx['persist_allowed'] is False
    assert fx['business_writes']==0
    assert fx['automatic_promotion_allowed'] is False
    assert 'SOURCE CONTEXT — sole factual surface' in fx['prompt']
    assert '既存コメントを書き換える権限もありません' in fx['prompt']


def test_valid_source_bound_candidate_passes():
    result=validate_comment_shadow_output(INPUT,PLAN,json.dumps(_valid_output(),ensure_ascii=False))
    assert result['passed'] is True
    assert result['persist_allowed'] is False
    assert result['automatic_promotion_allowed'] is False
    assert result['human_semantic_review_required'] is True
    assert set(result['values'])=={'これは何？','なぜ重要？','判断理由','次にやること'}


def test_unsupported_numeric_fact_is_blocked():
    value=_valid_output(); value['why_important']='ExploitBenchでは99%を記録したため重要だ。'
    result=validate_comment_shadow_output(INPUT,PLAN,json.dumps(value,ensure_ascii=False))
    assert result['passed'] is False
    assert any(row['type']=='unsupported_numeric_fact' for row in result['fact_boundary']['violations'])


def test_semantic_access_inflation_is_blocked():
    value=_valid_output(); value['decision_reason']='Astraは一般公開されているため、すぐ導入できる。'
    result=validate_comment_shadow_output(INPUT,PLAN,json.dumps(value,ensure_ascii=False))
    assert result['passed'] is False
    assert any(row['type']=='availability_inflation' for row in result['fact_boundary']['violations'])


def test_markdown_html_and_overlong_structure_are_blocked():
    value=_valid_output()
    value['decision_reason']='- 一つ目。\n- 二つ目。<br>三つ目。'
    result=validate_comment_shadow_output(INPUT,PLAN,json.dumps(value,ensure_ascii=False))
    assert result['passed'] is False
    violations=set(result['style_violations']['decision_reason'])
    assert {'multiline','markdown_or_list','html'}.issubset(violations)


def test_wrong_shape_and_legacy_plan_fail_closed(tmp_path):
    value=_valid_output(); value['extra']='x'
    with pytest.raises(CommentShadowError,match='shape_invalid'):
        validate_comment_shadow_output(INPUT,PLAN,json.dumps(value,ensure_ascii=False))
    report=json.loads(Path(PLAN).read_text(encoding='utf-8'))
    report['mode']='legacy_freeform_plan'
    path=tmp_path/'legacy.json'; path.write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
    with pytest.raises(CommentShadowError,match='fact_locked_plan_required'):
        build_comment_shadow_fixture(INPUT,str(path))


def test_module_has_no_provider_transport_or_business_persistence_surface():
    source=Path('hybrid_comment_shadow.py').read_text(encoding='utf-8').lower()
    for token in ('groq_api_key','gemini_api_key','notion_client','requests.post(','create_page(','update_page('):
        assert token not in source
