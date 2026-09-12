import json
import pytest

from ai_provider import GenerationRequest, GroqProvider, ProviderError
from groq_validation import schema_validator
from hybrid_groq_plan import MODE, build_hybrid_plan_fixture, validate_hybrid_plan_text

INPUT='tests/fixtures/groq/article_parity_B0049_input.json'


def _valid_plan():
    return {
        'source_summary':'一次情報で確認された評価結果。',
        'what':'特定条件で能力評価が行われた。',
        'why_important':'能力の上限を判断する材料になる。',
        'decision':'WATCH',
        'decision_reason':['利用条件は一次情報で確認する必要がある。'],
        'business_impact':12,
        'technical_impact':18,
        'urgency':8,
        'market_impact':10,
        'reliability':12,
        'action':'一次情報で利用条件を確認する。',
        'article_value':82,
        'article_angle':'大きな数字ほど条件と一緒に読む。',
        'reader_bridge':'テストの満点と日常での万能さは別だと考える。',
        'title_seed':'100%の数字はどこまで信じていい？',
        'access_status':'NOT_CONFIRMED',
    }


def test_hybrid_plan_fixture_explicitly_uses_json_object_local_strict(tmp_path):
    fixture=build_hybrid_plan_fixture(INPUT,str(tmp_path/'fixture.json'))
    assert fixture['structured_output_mode']==MODE
    assert fixture['schema']
    assert 'JSONオブジェクト1個だけ' in fixture['prompt']
    assert fixture['business_writes']==0 and fixture['persist_results'] is False
    provider=GroqProvider(lambda _:None,validate_schema=schema_validator(fixture['schema']),token_budget=7000,model=fixture['model'])
    payload,_=provider.prepare(GenerationRequest(
        fixture['prompt'],fixture['max_output_tokens'],fixture['schema'],fixture['reasoning_effort'],fixture['structured_output_mode']
    ))
    assert payload['response_format']=={'type':'json_object'}
    assert payload['reasoning_format']=='hidden'
    assert 'json_schema' not in payload['response_format']


def test_shared_strict_schema_mode_remains_default():
    schema={'type':'object','properties':{'x':{'type':'string'}},'required':['x'],'additionalProperties':False}
    provider=GroqProvider(lambda _:None,validate_schema=schema_validator(schema),token_budget=7000)
    payload,_=provider.prepare(GenerationRequest('Return JSON',100,schema,'low'))
    assert payload['response_format']['type']=='json_schema'
    assert payload['response_format']['json_schema']['strict'] is True


def test_valid_json_object_passes_full_local_schema_and_semantic_guards():
    plan=validate_hybrid_plan_text(json.dumps(_valid_plan(),ensure_ascii=False))
    assert plan['decision']=='WATCH'
    assert plan['access_status']=='NOT_CONFIRMED'


def test_missing_key_wrong_enum_and_non_json_fail_closed():
    missing=_valid_plan(); missing.pop('title_seed')
    with pytest.raises(Exception):
        validate_hybrid_plan_text(json.dumps(missing,ensure_ascii=False))
    wrong=_valid_plan(); wrong['decision']='GO_NOW'
    with pytest.raises(Exception):
        validate_hybrid_plan_text(json.dumps(wrong,ensure_ascii=False))
    with pytest.raises(ValueError,match='hybrid_plan_json_invalid'):
        validate_hybrid_plan_text('not json')


def test_json_object_mode_requires_schema():
    provider=GroqProvider(lambda _:None,token_budget=7000)
    with pytest.raises(ProviderError,match='structured_output_schema_required'):
        provider.prepare(GenerationRequest('Return JSON',100,None,'low',MODE))



def test_unconfirmed_evaluation_conditions_cannot_become_provision_claim():
    plan=_valid_plan()
    plan['what']='特定のアクセス条件下で提供され、複数の安全策がある。'
    with pytest.raises(Exception,match='unconfirmed_access_scope_claim'):
        validate_hybrid_plan_text(json.dumps(plan,ensure_ascii=False))
    plan['what']='特定のアクセス条件下で評価された。'
    assert validate_hybrid_plan_text(json.dumps(plan,ensure_ascii=False))['decision']=='WATCH'


def test_hybrid_completion_budget_preserves_rate_safety(tmp_path):
    fixture=build_hybrid_plan_fixture(INPUT,str(tmp_path/'fixture.json'))
    assert fixture['max_output_tokens']==3000
    provider=GroqProvider(lambda _:None,validate_schema=schema_validator(fixture['schema']),token_budget=7000,model=fixture['model'])
    _,estimate=provider.prepare(GenerationRequest(fixture['prompt'],fixture['max_output_tokens'],fixture['schema'],fixture['reasoning_effort'],fixture['structured_output_mode']))
    assert estimate<=7000


def test_rejected_plan_is_saved_without_becoming_quality_success(tmp_path, monkeypatch):
    from dataclasses import dataclass
    import hybrid_groq_plan_live as live
    fixture=build_hybrid_plan_fixture(INPUT,str(tmp_path/'fixture.json'))
    plan=_valid_plan()
    plan['what']='限定条件下で提供されている。'
    @dataclass
    class Result:
        text: str
        prompt_tokens: int = 100
        completion_tokens: int = 200
    class FakeProvider:
        def __init__(self,*a,**kw): pass
        def prepare(self,request):
            return {'response_format':{'type':'json_object'},'reasoning_format':'hidden'},500
        def generate(self,request): return Result(json.dumps(plan,ensure_ascii=False))
    monkeypatch.setattr(live,'GroqProvider',FakeProvider)
    monkeypatch.setattr(live,'reconcile_remote',lambda *a:None)
    for name in ('GROQ_API_KEY','GROQ_LEDGER_GITHUB_TOKEN','AIIF_GROQ_EXPERIMENT'):
        monkeypatch.setenv(name,'offline-placeholder')
    output=tmp_path/'report.json'
    with pytest.raises(Exception,match='unconfirmed_access_scope_claim'):
        live.run_live(str(tmp_path/'fixture.json'),str(output))
    report=json.loads(output.read_text())
    assert report['status']=='PLAN_REJECTED'
    assert report['semantic_plan_validated'] is False
    assert report['quality_validated'] is False
    assert json.loads(report['result']['text'])==plan
    assert report['business_writes']==0

    from groq_two_pass_article import load_plan_report
    with pytest.raises(Exception,match='plan_report_rejected'):
        load_plan_report(str(output))
