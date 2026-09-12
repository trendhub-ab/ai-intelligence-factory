import json
from datetime import datetime, timezone
from types import SimpleNamespace

from hybrid_writer_deferred import build_pending_writer_record
from hybrid_writer_runtime import run_or_defer_writer


def _fixture(tmp_path):
    path=tmp_path/'fixture.json'
    value={
        'candidate_id':'B0049','plan_provider':'groq','plan_source':'saved_validated_report',
        'writer_models':['gemini-3.7-flash','gemini-3.8-flash'],'writer_prompt':'prompt',
        'business_writes':0,'persist_results':False,
    }
    path.write_text(json.dumps(value),encoding='utf-8')
    return str(path),value


def _failure_report(path):
    value={
        'provider':'gemini','provider_calls':2,'business_writes':0,'persist_results':False,
        'attempts':[
            {'model':'gemini-3.7-flash','status':'error','http_status':503},
            {'model':'gemini-3.8-flash','status':'error','http_status':503},
        ],
    }
    path.write_text(json.dumps(value),encoding='utf-8')
    return value


def test_pair_503_is_saved_as_deferred_without_business_write(tmp_path):
    fixture_path,_=_fixture(tmp_path); report_path=tmp_path/'report.json'; pending_path=tmp_path/'pending.json'
    saved=[]
    def runner(pipeline,fixture,report):
        _failure_report(report_path)
        raise RuntimeError('hybrid_gemini_writer_unavailable')
    result=run_or_defer_writer(
        SimpleNamespace(),fixture_path,str(report_path),str(pending_path),
        load_state=lambda cid:None, save_state=lambda rec:saved.append(rec),
        delete_state=lambda cid:False, writer_runner=runner,
    )
    assert result['status']=='DEFERRED' and result['provider_calls']==2
    assert len(saved)==1 and saved[0]['business_writes']==0
    assert json.loads(pending_path.read_text())['status']=='PENDING_WRITER'


def test_active_cooldown_skips_provider_call_entirely(tmp_path):
    fixture_path,fixture=_fixture(tmp_path); report_path=tmp_path/'report.json'; pending_path=tmp_path/'pending.json'
    provider_report={
        'attempts':[
            {'model':'gemini-3.7-flash','status':'error','http_status':503},
            {'model':'gemini-3.8-flash','status':'error','http_status':503},
        ]
    }
    pending=build_pending_writer_record(fixture,provider_report,now=datetime.now(timezone.utc))
    calls=[]
    result=run_or_defer_writer(
        SimpleNamespace(),fixture_path,str(report_path),str(pending_path),
        load_state=lambda cid:pending, save_state=lambda rec:None, delete_state=lambda cid:False,
        writer_runner=lambda *a,**k:calls.append(True),
    )
    assert result['status']=='DEFERRED' and result['provider_calls']==0
    assert calls==[]


def test_success_clears_pending_state(tmp_path):
    fixture_path,_=_fixture(tmp_path); report_path=tmp_path/'report.json'; pending_path=tmp_path/'pending.json'
    deleted=[]
    def runner(pipeline,fixture,report):
        value={'provider_calls':1,'model':'gemini-3.7-flash','text':'ok','business_writes':0}
        report_path.write_text(json.dumps(value),encoding='utf-8')
        return value
    result=run_or_defer_writer(
        SimpleNamespace(),fixture_path,str(report_path),str(pending_path),
        load_state=lambda cid:None, save_state=lambda rec:None,
        delete_state=lambda cid:deleted.append(cid), writer_runner=runner,
    )
    assert result['status']=='SUCCESS' and result['provider_calls']==1
    assert deleted==['B0049']


def test_nonavailability_runtime_error_is_not_deferred(tmp_path):
    fixture_path,_=_fixture(tmp_path); report_path=tmp_path/'report.json'; pending_path=tmp_path/'pending.json'
    saved=[]
    try:
        run_or_defer_writer(
            SimpleNamespace(),fixture_path,str(report_path),str(pending_path),
            load_state=lambda cid:None, save_state=lambda rec:saved.append(rec), delete_state=lambda cid:False,
            writer_runner=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('writer_quality_failure')),
        )
    except RuntimeError as exc:
        assert str(exc)=='writer_quality_failure'
    else:
        raise AssertionError('expected failure')
    assert saved==[]
