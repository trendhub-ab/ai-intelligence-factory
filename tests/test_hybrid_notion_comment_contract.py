import json
from pathlib import Path

import pytest

from hybrid_notion_comment_contract import (
    CONTENT_COMMENT_CONTRACT,
    CONTENT_PAYLOAD_CONFIG_MAP,
    TECHNOLOGY_COMMENT_CONTRACT,
    TECHNOLOGY_CORE_CONSTANT_MAP,
    PRODUCT_REVIEW_DIRECT_FIELDS,
    PRESERVE_EXISTING,
    SHADOW_ONLY,
    PRODUCTION_FROZEN,
    LEGACY_PRODUCT_REVIEW_FROZEN,
    FACT_LOCKED_PLAN_DETERMINISTIC,
    CommentContractError,
    property_contract,
    build_content_comment_shadow,
    validate_product_review_comment_style,
    audit_product_review_shadow_fact_boundary,
    compare_comment_style,
    evaluate_shadow_promotion,
)

PLAN = 'tests/fixtures/groq/two_pass_v3_plan_safe_report.json'
INPUT = 'tests/fixtures/groq/article_parity_B0049_input.json'


def _source_context():
    return json.loads(Path(INPUT).read_text(encoding='utf-8'))['source_context']


def test_all_inventory_rows_preserve_existing_and_forbid_direct_freeform_groq():
    for database, rows in (("content", CONTENT_COMMENT_CONTRACT), ("technology", TECHNOLOGY_COMMENT_CONTRACT)):
        assert rows
        for name in rows:
            contract = property_contract(database, name)
            assert contract['existing_value_policy'] == PRESERVE_EXISTING
            assert contract['direct_groq_freeform_allowed'] is False
            assert contract['direct_writer_article_source_allowed'] is False
            assert contract['migration'] in {SHADOW_ONLY, PRODUCTION_FROZEN}


def test_unknown_database_and_property_fail_closed():
    with pytest.raises(CommentContractError, match='comment_database_unknown'):
        property_contract('other', '判断理由')
    with pytest.raises(CommentContractError, match='comment_property_unknown'):
        property_contract('content', '未知コメント')


def test_production_content_payload_comment_keys_are_governed():
    source = Path('notion_payloads.py').read_text(encoding='utf-8')
    for config_key, property_name in CONTENT_PAYLOAD_CONFIG_MAP.items():
        assert property_name in CONTENT_COMMENT_CONTRACT
        assert f'_cfg(config, "{config_key}")' in source


def test_technology_core_comment_constants_are_governed():
    source = Path('decision_intelligence_run255_core.py').read_text(encoding='utf-8')
    for constant, property_name in TECHNOLOGY_CORE_CONSTANT_MAP.items():
        assert property_name in TECHNOLOGY_COMMENT_CONTRACT
        assert f"{constant} = '{property_name}'" in source


def test_product_review_direct_comments_are_frozen_shadow_only():
    for _, (notion_property, _) in PRODUCT_REVIEW_DIRECT_FIELDS.items():
        contract = property_contract('technology', notion_property)
        assert contract['authority'] == LEGACY_PRODUCT_REVIEW_FROZEN
        assert contract['migration'] == SHADOW_ONLY
        assert contract['existing_value_policy'] == PRESERVE_EXISTING


def test_content_shadow_is_small_deterministic_surface_and_never_persistent():
    shadow = build_content_comment_shadow(PLAN)
    assert shadow['mode'] == SHADOW_ONLY
    assert shadow['persist_allowed'] is False
    assert shadow['existing_value_policy'] == PRESERVE_EXISTING
    assert shadow['source'] == FACT_LOCKED_PLAN_DETERMINISTIC
    assert set(shadow['values']) == {'スコア内訳', 'なぜ重要？', '判断理由', '次にやること'}
    assert shadow['values']['スコア内訳'] == (
        'Business Impact 20/25 / Technical Impact 22/25 / Urgency 15/20 / '
        'Market Impact 10/15 / Reliability 13/15'
    )
    assert '一般利用条件は確認できていない。' in shadow['values']['判断理由']
    assert shadow['values']['次にやること'] == '利用条件を一次情報で確認する。'


def test_content_shadow_rejects_legacy_plan_report(tmp_path):
    report = json.loads(Path(PLAN).read_text(encoding='utf-8'))
    report['mode'] = 'legacy_freeform_plan'
    bad = tmp_path / 'legacy.json'
    bad.write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
    with pytest.raises(CommentContractError, match='fact_locked_plan_required'):
        build_content_comment_shadow(str(bad))


@pytest.mark.parametrize('field,text', [
    ('main_risk', '権限設計とレビュー境界が弱いと、誤変更の影響が広がる。'),
    ('best_for', 'レビュー体制がある小規模チームの実装高速化に向いている。'),
    ('avoid_for', '監査フローが未整備な本番直結運用には向かない。'),
    ('short_rationale', '効果は大きいが、統制設計を先に確認する必要がある。'),
])
def test_public_synthetic_product_review_style_baseline_passes(field, text):
    report = validate_product_review_comment_style(field, text)
    assert report['passed'] is True
    assert report['persist_allowed'] is False
    assert report['sentences'] <= 2


@pytest.mark.parametrize('text,expected', [
    ('# 主リスク\n危険です。', {'multiline', 'markdown_or_list'}),
    ('- 危険です。', {'markdown_or_list'}),
    ('私はAIとして判断します。', {'provider_self_reference'}),
    ('一文。二文。三文。', {'too_many_sentences'}),
])
def test_product_review_style_rejects_presentation_drift(text, expected):
    report = validate_product_review_comment_style('main_risk', text)
    assert report['passed'] is False
    assert expected.issubset(set(report['violations']))


def test_product_review_style_enforces_current_protocol_lengths():
    for field, (_, limit) in PRODUCT_REVIEW_DIRECT_FIELDS.items():
        assert validate_product_review_comment_style(field, 'あ' * limit)['passed'] is True
        report = validate_product_review_comment_style(field, 'あ' * (limit + 1))
        assert 'too_long' in report['violations']


def test_product_review_shadow_fact_boundary_blocks_new_concrete_fact():
    assessment = {
        'main_risk': 'Astraの主なリスクは追加確認が必要だ。',
        'best_for': '確認済み条件を理解できるチーム向け。',
        'avoid_for': '一般利用条件を確認せずに本番採用する用途には向かない。',
        'short_rationale': 'ExploitBenchでは99%を記録したため有望だ。',
    }
    report = audit_product_review_shadow_fact_boundary(_source_context(), assessment)
    assert report['passed'] is False
    assert any(x['type'] == 'unsupported_numeric_fact' for x in report['fact_boundary']['violations'])
    assert report['persist_allowed'] is False


def test_product_review_shadow_allows_source_supported_concrete_facts():
    assessment = {
        'main_risk': '一般利用条件は一次資料だけでは確認できない。',
        'best_for': '評価条件を分けて検討できるチーム向け。',
        'avoid_for': '利用条件を確認せず即時導入する用途には向かない。',
        'short_rationale': 'ExploitBenchで100%を記録した一方、結果はDaybreak Blue access条件を反映する。',
    }
    report = audit_product_review_shadow_fact_boundary(_source_context(), assessment)
    assert report['passed'] is True
    assert report['persist_allowed'] is False


def test_style_comparison_never_claims_semantic_equivalence_or_persistence():
    report = compare_comment_style('短い既存文。', '少し長い候補文。')
    assert report['semantic_equivalence_claimed'] is False
    assert report['persist_allowed'] is False
    assert report['existing_chars'] > 0 and report['candidate_chars'] > 0


def test_shadow_machine_pass_can_never_auto_promote_comments():
    result = evaluate_shadow_promotion(
        {'判断理由': '既存判断です。'},
        {'判断理由': '候補判断です。'},
        machine_checks_passed=True,
    )
    assert result['machine_checks_passed'] is True
    assert result['human_semantic_review_required'] is True
    assert result['automatic_promotion_allowed'] is False
    assert result['production_write_allowed'] is False
    assert result['existing_value_policy'] == PRESERVE_EXISTING


def test_shadow_promotion_requires_existing_reference_value():
    with pytest.raises(CommentContractError, match='shadow_existing_value_missing'):
        evaluate_shadow_promotion({}, {'判断理由': '候補判断です。'}, machine_checks_passed=True)


def test_contract_module_has_no_provider_or_business_persistence_surface():
    source = Path('hybrid_notion_comment_contract.py').read_text(encoding='utf-8').lower()
    for token in ('google', 'gemini_api_key', 'groq_api_key', 'notion_client', 'create_page(', 'update_page(', 'requests.post('):
        assert token not in source
