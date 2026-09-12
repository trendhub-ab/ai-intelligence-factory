import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hybrid_one_shot import (
    PRIMARY_GEMINI_WRITER_MODEL,
    SECONDARY_GEMINI_WRITER_MODEL,
    _management_surface,
    build_writer_fixture,
    run_bounded_gemini_writer_calls,
    run_one_gemini_writer_call,
)
from hybrid_groq_plan import load_hybrid_plan_report

INPUT='tests/fixtures/groq/article_parity_B0049_input.json'
PLAN='tests/fixtures/groq/two_pass_v3_plan_safe_report.json'


class Fake503(RuntimeError):
    code=503


class Fake400(RuntimeError):
    code=400


def test_fixture_keeps_fact_locked_groq_plan_and_bounded_gemini_writer(tmp_path):
    out=tmp_path/'fixture.json'
    fx=build_writer_fixture(INPUT,PLAN,str(out))
    report=fx['decision_package']['plan_report']
    assert fx['plan_provider']=='groq'
    assert fx['plan_source']=='saved_validated_report'
    assert report['mode']=='hybrid_groq_judgment_fact_locked'
    assert report['pass']=='decision_judgment_codes'
    assert report['fact_envelope_sha256']
    assert report['composed_plan']['source_summary']
    assert report['composed_plan']['what']=='Path to Astra: critical capabilities and frontier safeguards'
    assert fx['writer_provider']=='gemini'
    assert fx['writer_model']==PRIMARY_GEMINI_WRITER_MODEL
    assert fx['writer_models']==[PRIMARY_GEMINI_WRITER_MODEL,SECONDARY_GEMINI_WRITER_MODEL]
    assert fx['provider_calls_expected']=={'groq_live':0,'gemini_live_max':2}
    assert '503/404' in fx['fallback_contract']
    assert fx['business_writes']==0 and fx['persist_results'] is False
    assert '最終日本語Writer' in fx['writer_prompt']
    assert '事実の上限はSOURCE CONTEXT' in fx['writer_prompt']
    assert '一般利用条件が未確認' in fx['writer_prompt']


def test_management_surface_is_deterministic_and_score_stays_80():
    plan=load_hybrid_plan_report(PLAN)
    text=_management_surface(plan)
    assert '・Decision: WATCH' in text
    assert '合計 80/100' in text
    assert 'Article Value: 85' in text
    assert '一般利用条件は確認できていない' in text
    assert 'Technical Impact 22/25' in text
    assert 'Reliability 13/15' in text


def test_writer_prompt_uses_source_context_as_fact_ceiling_not_plan_as_new_evidence(tmp_path):
    source=json.loads(Path(INPUT).read_text(encoding='utf-8'))
    fx=build_writer_fixture(INPUT,PLAN,str(tmp_path/'fixture.json'))
    prompt=fx['writer_prompt']
    assert source['source_context'] in prompt
    assert 'PLANは編集方針と判断であり、新しい事実ソースではない' in prompt
    assert 'Daybreak Blue' in prompt
    assert '評価条件から「安全装置を外した」' in prompt
    assert '公開時は高度なサイバー能力へのアクセス制限' in prompt


def test_rejected_plan_never_builds_writer_fixture(tmp_path):
    report=json.loads(Path(PLAN).read_text(encoding='utf-8'))
    report['status']='PLAN_REJECTED'
    report['semantic_plan_validated']=False
    bad=tmp_path/'bad-plan.json'
    bad.write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
    with pytest.raises(Exception,match='hybrid_plan_report_rejected'):
        build_writer_fixture(INPUT,str(bad),str(tmp_path/'writer.json'))


def test_one_writer_transport_attempt_has_no_pool_fallback(tmp_path):
    build_writer_fixture(INPUT,PLAN,str(tmp_path/'fixture.json'))
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


def test_bounded_writer_falls_back_once_from_503_to_38(tmp_path):
    build_writer_fixture(INPUT,PLAN,str(tmp_path/'fixture.json'))
    calls=[]
    class FakePipeline:
        def _generate_via_chat(self,model,*args,**kwargs):
            calls.append(model)
            if model==PRIMARY_GEMINI_WRITER_MODEL:
                raise Fake503('busy')
            return SimpleNamespace(text='===TITLE===\nテスト。\n===ARTICLE===\n' + ('本文です。'*260))
    report=run_bounded_gemini_writer_calls(FakePipeline(),str(tmp_path/'fixture.json'),str(tmp_path/'report.json'))
    assert calls==[PRIMARY_GEMINI_WRITER_MODEL,SECONDARY_GEMINI_WRITER_MODEL]
    assert report['provider_calls']==2
    assert report['model']==SECONDARY_GEMINI_WRITER_MODEL
    assert report['attempts'][0]['http_status']==503


def test_bounded_writer_does_not_fallback_on_nonavailability_error(tmp_path):
    build_writer_fixture(INPUT,PLAN,str(tmp_path/'fixture.json'))
    calls=[]
    class FakePipeline:
        def _generate_via_chat(self,model,*args,**kwargs):
            calls.append(model)
            raise Fake400('bad request')
    with pytest.raises(RuntimeError,match='hybrid_gemini_writer_unavailable'):
        run_bounded_gemini_writer_calls(FakePipeline(),str(tmp_path/'fixture.json'),str(tmp_path/'report.json'))
    assert calls==[PRIMARY_GEMINI_WRITER_MODEL]
    report=json.loads((tmp_path/'report.json').read_text(encoding='utf-8'))
    assert report['provider_calls']==1
    assert report['attempts'][0]['http_status']==400


def test_module_contains_no_business_persistence_surface():
    src=Path('hybrid_one_shot.py').read_text(encoding='utf-8')
    forbidden=('notion_client','create_page(','update_page(','note.com','requests.post(')
    for token in forbidden:
        assert token not in src
