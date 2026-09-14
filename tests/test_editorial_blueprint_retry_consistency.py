"""Regression for quotas reintroduced after Blueprint by later prompt layers."""
from types import SimpleNamespace

import pytest

import reader_value_review_bridge as bridge
import run208_reader_value_repair as repair
import run226_reader_delight_planning as blueprint
import run228_reader_rhythm_planning as rhythm


QUOTAS = (
    '1つだけ本文前半', '原則3点以内', '新規専門概念を2個以上持ち込まない',
    '4項目以上なら3項目以内', '中核メカニズムを1つまで',
    '中核メカニズム1つ →', '冒頭約600文字', '冒頭3段落以内',
    '普通の日本語で1〜2文', '原則2〜3個', '2段落続いたら',
    '専門名・略語が3個以上',
)


def assembled_editorial_layers():
    # Actual production ordering matters: the old quotas were added AFTER Run226.
    p = SimpleNamespace(
        build_decision_prompt=lambda *a, **k: 'SOURCE BOUNDARY\n' + str(k.get('quality_feedback', '')),
        build_dynamic_retry_instruction=lambda rows: ('BASE RETRY', ['ARTICLE']),
        validate_human_appeal_gate=lambda parsed, peers=None: ('ACCEPTABLE', []),
        should_attempt_dynamic_retry=lambda rows, evidence, origin='new': (False, 'base_denied'),
        GATE_SEVERITY_HARD='HARD', EVIDENCE_SUFFICIENT='SUFFICIENT',
    )
    for layer in (blueprint, rhythm, bridge, repair):
        layer.install(p)
    return p


@pytest.mark.parametrize('message', [
    '', 'dense_report_cluster', 'multi_axis_reader_weakness',
    'non_engineer_access_failure', 'final_surface_non_engineer_access_failure',
    'final_surface_summary_jargon_cluster',
])
@pytest.mark.parametrize('mixed', [False, True])
def test_first_pass_and_retries_do_not_reintroduce_numeric_editorial_limits(message, mixed):
    p = assembled_editorial_layers()
    rows = [{'message': 'reader_value_review:' + message, 'severity': 'REVIEW'}] if message else []
    if mixed:
        rows.append({'reason_code': 'score_narrative_mismatch',
                     'message': 'score_narrative_mismatch', 'severity': 'REVIEW'})
    feedback, sections = p.build_dynamic_retry_instruction(rows)
    prompt = p.build_decision_prompt(quality_feedback=feedback, previous_article='Existing evidence')
    assert sections == ['ARTICLE']
    assert blueprint.EDITORIAL_BLUEPRINT_MARKER in prompt
    assert '必要な専門概念・制約・判断材料を個数合わせのために削らない' in prompt
    assert 'Evidence上重要な数値・条件・反証・制約は削らない' in prompt
    for quota in QUOTAS:
        assert quota not in feedback
        assert quota not in prompt
    if message and not mixed:
        assert 'Reader Repair｜Factを固定した読者導線修正' in feedback
        assert 'Decision/Score/Action' in feedback
        assert '通らなければReadyにしない' in feedback
    if mixed:
        assert 'Reader Repair｜Factを固定した読者導線修正' not in feedback
        assert 'Decision Score、Evidence、事実、数値、重要制約は作り替えず' in feedback


def test_reader_repair_stays_bounded_and_evidence_gated_after_prompt_changes():
    p = assembled_editorial_layers()
    rows = [{'message': 'reader_value_review:dense_report_cluster', 'severity': 'REVIEW'}]
    for evidence in ({'state': 'INSUFFICIENT', 'decision_scope_safe': True},
                     {'state': 'SUFFICIENT', 'decision_scope_safe': False}):
        assert p.should_attempt_dynamic_retry(rows, evidence, 'new')[0] is False
    safe = {'state': 'SUFFICIENT', 'decision_scope_safe': True}
    assert p.should_attempt_dynamic_retry(rows, safe, 'new')[0] is True
    assert p.should_attempt_dynamic_retry(rows, safe, 'new')[0] is False
    p.build_decision_prompt(quality_feedback='retry', previous_article='existing')
    assert p.should_attempt_dynamic_retry(rows, safe, 'new')[0] is False
