from datetime import datetime, timezone
import base64
import json

import pytest

from hybrid_writer_deferred import build_pending_writer_record
from hybrid_writer_state_store import (
    PendingWriterStateError,
    delete_pending_writer_state,
    load_pending_writer_state,
    pending_writer_state_path,
    save_pending_writer_state,
)


class Response:
    def __init__(self,status_code,payload=None):
        self.status_code=status_code
        self._payload=payload or {}
    def json(self): return self._payload


class FakeHTTP:
    def __init__(self):
        self.files={}
        self.put_statuses=[]
        self.calls=[]
    def get(self,url,headers=None,params=None,timeout=None):
        self.calls.append(('get',url,params))
        item=self.files.get(url)
        return Response(200,item) if item else Response(404)
    def put(self,url,headers=None,json=None,timeout=None):
        self.calls.append(('put',url,json))
        if self.put_statuses:
            status=self.put_statuses.pop(0)
            if status not in {200,201}:
                return Response(status)
        raw=base64.b64decode(json['content']).decode('utf-8')
        self.files[url]={'sha':'sha-new','content':base64.b64encode(raw.encode()).decode()}
        return Response(201,{'content':{'sha':'sha-new'}})
    def delete(self,url,headers=None,json=None,timeout=None):
        self.calls.append(('delete',url,json))
        self.files.pop(url,None)
        return Response(200)


def _fixture():
    return {
        'candidate_id':'B0049','plan_provider':'groq','plan_source':'saved_validated_report',
        'writer_models':['gemini-3.7-flash','gemini-3.8-flash'],'writer_prompt':'prompt',
        'business_writes':0,'persist_results':False,
    }


def _report():
    return {'attempts':[
        {'model':'gemini-3.7-flash','status':'error','http_status':503},
        {'model':'gemini-3.8-flash','status':'error','http_status':503},
    ]}


def _env(monkeypatch):
    monkeypatch.setenv('GITHUB_REPOSITORY','trendhub-ab/ai-intelligence-factory')
    monkeypatch.setenv('GH_PAT','test-token')
    monkeypatch.setenv('AIIF_RUNTIME_STATE_BRANCH','runtime-state')


def test_state_path_is_bounded_and_rejects_traversal():
    assert pending_writer_state_path('B0049')=='.runtime/hybrid_pending_writers/B0049.json'
    with pytest.raises(PendingWriterStateError,match='candidate_id_invalid'):
        pending_writer_state_path('../main')


def test_save_load_delete_round_trip_is_runtime_state_only(monkeypatch):
    _env(monkeypatch); http=FakeHTTP()
    rec=build_pending_writer_record(_fixture(),_report(),now=datetime.now(timezone.utc))
    info=save_pending_writer_state(rec,http=http)
    assert info['branch']=='runtime-state' and info['candidate_id']=='B0049'
    assert '/contents/.runtime/hybrid_pending_writers/B0049.json' in info['path'].join(['','']) or info['path'].endswith('B0049.json')
    loaded=load_pending_writer_state('B0049',http=http)
    assert loaded['candidate_id']=='B0049' and loaded['business_writes']==0
    assert delete_pending_writer_state('B0049',http=http) is True
    assert load_pending_writer_state('B0049',http=http) is None


def test_store_never_accepts_main_branch(monkeypatch):
    monkeypatch.setenv('GITHUB_REPOSITORY','trendhub-ab/ai-intelligence-factory')
    monkeypatch.setenv('GH_PAT','test-token')
    monkeypatch.setenv('AIIF_RUNTIME_STATE_BRANCH','main')
    rec=build_pending_writer_record(_fixture(),_report(),now=datetime.now(timezone.utc))
    with pytest.raises(RuntimeError):
        save_pending_writer_state(rec,http=FakeHTTP())


def test_cas_conflict_retries_but_other_failure_does_not(monkeypatch):
    _env(monkeypatch); rec=build_pending_writer_record(_fixture(),_report(),now=datetime.now(timezone.utc))
    http=FakeHTTP(); http.put_statuses=[409,201]
    save_pending_writer_state(rec,http=http)
    assert len([c for c in http.calls if c[0]=='put'])==2
    http2=FakeHTTP(); http2.put_statuses=[403]
    with pytest.raises(PendingWriterStateError,match='write_http_403'):
        save_pending_writer_state(rec,http=http2)
    assert len([c for c in http2.calls if c[0]=='put'])==1
