import json
import pytest

from ai_provider import GenerationRequest, GroqProvider, ProviderError
from groq_validation import schema_validator
from hybrid_fact_envelope import build_fact_envelope, validate_fact_envelope, FactEnvelopeError
from hybrid_groq_plan import (
    MODE, JUDGMENT_FIELDS, build_hybrid_plan_fixture, validate_hybrid_judgment_text,
    validate_hybrid_plan_text, compose_fact_locked_plan,
)

INPUT='tests/fixtures/groq/article_parity_B0049_input.json'


def _valid_judgment():
    return {
        'decision':'WATCH',
        'reason_codes':['HIGH_TECHNICAL_SIGNIFICANCE','ACCESS_UNCONFIRMED','SAFEGUARD_EFFECTIVENESS_UNCONFIRMED'],
        'business_impact':18, 'technical_impact':20, 'urgency':12, 'market_impact':10,
        'reliability':13, 'article_value':80, 'access_status':'NOT_CONFIRMED',
        'action_code':'CONFIRM_ACCESS', 'reader_priority':'SAFETY',
    }


def _legacy_plan():
    return {
        'source_summary':'一次情報で確認された評価結果。', 'what':'特定条件で能力評価が行われた。',
        'why_important':'確認済みEvidenceを実務判断へ結びつける価値がある。', 'decision':'WATCH',
        'decision_reason':['一般利用条件は確認できていない。'],
        'business_impact':12, 'technical_impact':18, 'urgency':8, 'market_impact':10, 'reliability':12,
        'action':'利用条件を一次情報で確認する。', 'article_value':82,
        'article_angle':'確認済みFactと未確認事項を分けて読む。',
        'reader_bridge':'専門語を普通の言葉に置き換えて説明する。',
        'title_seed':'確認済みEvidenceから読む次の判断材料', 'access_status':'NOT_CONFIRMED',
    }


def test_fact_envelope_preserves_verified_ledger_verbatim_and_hashes_it():
    envelope=build_fact_envelope(INPUT)
    source=json.load(open(INPUT,encoding='utf-8'))
    assert envelope['fact_ledger']==source['source_context']
    assert envelope['primary_url']==source['url']
    assert len(envelope['fact_ledger_sha256'])==64
    assert validate_fact_envelope(envelope)==envelope


def test_fact_envelope_tamper_fails_closed():
    envelope=build_fact_envelope(INPUT)
    envelope['fact_ledger'] += '改変'
    with pytest.raises(FactEnvelopeError,match='fact_ledger_hash_mismatch'):
        validate_fact_envelope(envelope)


def test_fixture_is_categorical_and_contains_no_freeform_fact_fields(tmp_path):
    fixture=build_hybrid_plan_fixture(INPUT,str(tmp_path/'fixture.json'))
    assert fixture['structured_output_mode']==MODE
    assert fixture['pass']=='decision_judgment_codes'
    assert set(fixture['schema']['required'])==set(JUDGMENT_FIELDS)
    for forbidden in ('source_summary','what','why_important','decision_reason','action','article_angle','reader_bridge','title_seed'):
        assert forbidden not in fixture['schema']['properties']
    assert 'あなたは文章を書きません' in fixture['prompt']
    assert 'Decision Score較正' in fixture['prompt']
    assert '一般利用可否が不明でも一次Evidenceの信頼性は下げない' in fixture['prompt']
    assert fixture['business_writes']==0 and fixture['persist_results'] is False
    provider=GroqProvider(lambda _:None,validate_schema=schema_validator(fixture['schema']),token_budget=7000,model=fixture['model'])
    payload,_=provider.prepare(GenerationRequest(fixture['prompt'],fixture['max_output_tokens'],fixture['schema'],fixture['reasoning_effort'],fixture['structured_output_mode']))
    assert payload['response_format']=={'type':'json_object'}
    assert payload['reasoning_format']=='hidden'


def test_composed_plan_uses_only_envelope_and_deterministic_mappings_for_prose():
    envelope=build_fact_envelope(INPUT)
    plan=compose_fact_locked_plan(envelope,_valid_judgment())
    assert plan['source_summary']==envelope['fact_ledger']
    assert plan['what']==envelope['name']
    assert plan['decision']=='WATCH'
    assert plan['decision_reason']==[
        '技術的な影響が大きく、継続監視の価値がある。',
        '一般利用条件は確認できていない。',
        '安全策の有効性は、このEvidenceだけでは確認できない。',
    ]
    assert plan['action']=='利用条件を一次情報で確認する。'
    assert '実装された安全策' not in json.dumps(plan,ensure_ascii=False)


def test_freeform_fact_prose_is_schema_rejected():
    judgment=_valid_judgment(); judgment['why_important']='Astraは臨界点を超えた。'
    with pytest.raises(Exception):
        validate_hybrid_judgment_text(json.dumps(judgment,ensure_ascii=False))


def test_unconfirmed_access_requires_safe_action_but_reason_is_derived_deterministically():
    judgment=_valid_judgment(); judgment['action_code']='COMPARE'
    with pytest.raises(Exception,match='unconfirmed_access_action_escalation'):
        validate_hybrid_judgment_text(json.dumps(judgment,ensure_ascii=False))
    judgment=_valid_judgment(); judgment['reason_codes']=['HIGH_TECHNICAL_SIGNIFICANCE','BUSINESS_RELEVANCE','EVIDENCE_STRONG']
    validated=validate_hybrid_judgment_text(json.dumps(judgment,ensure_ascii=False))
    plan=compose_fact_locked_plan(build_fact_envelope(INPUT),validated)
    assert plan['decision_reason']==[
        '技術的な影響が大きく、継続監視の価値がある。',
        '事業判断への影響を見極める価値がある。',
        '一般利用条件は確認できていない。',
    ]


def test_captured_calibrated_judgment_revalidates_without_repair():
    captured={
        'decision':'WATCH',
        'reason_codes':['HIGH_TECHNICAL_SIGNIFICANCE','BUSINESS_RELEVANCE','EVIDENCE_STRONG'],
        'business_impact':20,'technical_impact':22,'urgency':15,'market_impact':12,'reliability':13,
        'article_value':80,'access_status':'NOT_CONFIRMED','action_code':'CONFIRM_ACCESS','reader_priority':'TECHNICAL',
    }
    judgment=validate_hybrid_judgment_text(json.dumps(captured,ensure_ascii=False))
    plan=compose_fact_locked_plan(build_fact_envelope(INPUT),judgment)
    assert sum(plan[k] for k in ('business_impact','technical_impact','urgency','market_impact','reliability'))==82
    assert plan['decision']=='WATCH'
    assert plan['access_status']=='NOT_CONFIRMED'
    assert plan['decision_reason'][-1]=='一般利用条件は確認できていない。'


def test_confirmed_access_cannot_keep_unconfirmed_reason():
    judgment=_valid_judgment(); judgment['access_status']='CONFIRMED_AVAILABLE'; judgment['action_code']='COMPARE'
    with pytest.raises(Exception,match='confirmed_access_reason_conflict'):
        validate_hybrid_judgment_text(json.dumps(judgment,ensure_ascii=False))


def test_legacy_composed_plan_remains_readable_during_migration():
    assert validate_hybrid_plan_text(json.dumps(_legacy_plan(),ensure_ascii=False))['decision']=='WATCH'


def test_json_object_mode_requires_schema():
    provider=GroqProvider(lambda _:None,token_budget=7000)
    with pytest.raises(ProviderError,match='structured_output_schema_required'):
        provider.prepare(GenerationRequest('Return JSON',100,None,'low',MODE))


def test_hybrid_completion_budget_preserves_rate_safety(tmp_path):
    fixture=build_hybrid_plan_fixture(INPUT,str(tmp_path/'fixture.json'))
    assert fixture['max_output_tokens']==1200
    provider=GroqProvider(lambda _:None,validate_schema=schema_validator(fixture['schema']),token_budget=7000,model=fixture['model'])
    _,estimate=provider.prepare(GenerationRequest(fixture['prompt'],fixture['max_output_tokens'],fixture['schema'],fixture['reasoning_effort'],fixture['structured_output_mode']))
    assert estimate<=7000


def test_rejected_judgment_is_saved_and_never_composed(tmp_path, monkeypatch):
    from dataclasses import dataclass
    import hybrid_groq_plan_live as live
    fixture=build_hybrid_plan_fixture(INPUT,str(tmp_path/'fixture.json'))
    judgment=_valid_judgment(); judgment['action_code']='COMPARE'
    @dataclass
    class Result:
        text: str
        prompt_tokens: int = 100
        completion_tokens: int = 200
    class FakeProvider:
        def __init__(self,*a,**kw): pass
        def prepare(self,request): return {'response_format':{'type':'json_object'},'reasoning_format':'hidden'},500
        def generate(self,request): return Result(json.dumps(judgment,ensure_ascii=False))
    monkeypatch.setattr(live,'GroqProvider',FakeProvider)
    monkeypatch.setattr(live,'reconcile_remote',lambda *a:None)
    for name in ('GROQ_API_KEY','GROQ_LEDGER_GITHUB_TOKEN','AIIF_GROQ_EXPERIMENT'):
        monkeypatch.setenv(name,'offline-placeholder')
    output=tmp_path/'report.json'
    with pytest.raises(Exception,match='unconfirmed_access_action_escalation'):
        live.run_live(str(tmp_path/'fixture.json'),str(output))
    report=json.loads(output.read_text())
    assert report['status']=='PLAN_REJECTED'
    assert report['semantic_plan_validated'] is False
    assert 'composed_plan' not in report
    assert report['business_writes']==0
