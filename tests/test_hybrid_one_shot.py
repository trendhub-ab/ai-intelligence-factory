import json
from pathlib import Path
from types import SimpleNamespace

from hybrid_one_shot import (
    PRIMARY_GEMINI_WRITER_MODEL,
    _management_surface,
    build_writer_fixture,
    run_one_gemini_writer_call,
)
from groq_two_pass_article import load_plan_report

INPUT='tests/fixtures/groq/article_parity_B0049_input.json'
PLAN='tests/fixtures/groq/two_pass_v3_plan_safe_report.json'


def test_fixture_keeps_saved_groq_plan_and_one_gemini_call(tmp_path):
    out=tmp_path/'fixture.json'
    fx=build_writer_fixture(INPUT,PLAN,str(out))
    assert fx['plan_provider']=='groq'
    assert fx['plan_source']=='saved_validated_report'
    assert fx['writer_provider']=='gemini'
    assert fx['writer_model']==PRIMARY_GEMINI_WRITER_MODEL
    assert fx['provider_calls_expected']=={'groq_live':0,'gemini_live':1}
    assert fx['business_writes']==0 and fx['persist_results'] is False
    assert '最終日本語Writer' in fx['writer_prompt']


def test_management_surface_is_deterministic_and_score_stays_60():
    plan=load_plan_report(PLAN)
    text=_management_surface(plan)
    assert '・Decision: WATCH' in text
    assert '合計 62/100' in text
    assert 'Article Value: 80' in text
    assert '一般利用条件は確認できない' in text


def test_one_writer_transport_attempt_has_no_pool_fallback(tmp_path):
    fixture=build_writer_fixture(INPUT,PLAN,str(tmp_path/'fixture.json'))
    calls=[]
    class FakePipeline:
        def _generate_via_chat(self,*args,**kwargs):
            calls.append((args,kwargs))
            return SimpleNamespace(text='===TITLE===\nテスト。\n===ARTICLE===\n' + ('本文です。'*260))
    report=run_one_gemini_writer_call(FakePipeline(),str(tmp_path/'fixture.json'),str(tmp_path/'report.json'))
    assert len(calls)==1
    args,kwargs=calls[0]
    assert args[0]==PRIMARY_GEMINI_WRITER_MODEL
    assert kwargs['request_kind']=='hybrid_final_writer'
    assert kwargs['count_as_deep_dive'] is True
    assert report['provider_calls']==1 and report['business_writes']==0


def test_module_contains_no_business_persistence_surface():
    src=Path('hybrid_one_shot.py').read_text(encoding='utf-8')
    forbidden=('notion_client','create_page(','update_page(','note.com','requests.post(')
    for token in forbidden:
        assert token not in src
