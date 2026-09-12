from datetime import datetime, timedelta, timezone

import pytest

from hybrid_writer_deferred import (
    PENDING_WRITER,
    WRITER_READY,
    WRITER_EXPIRED,
    PendingWriterError,
    build_pending_writer_record,
    validate_pending_writer_record,
)

NOW=datetime(2026,9,12,4,0,tzinfo=timezone.utc)


def _fixture():
    return {
        'candidate_id':'B0049',
        'plan_provider':'groq',
        'plan_source':'saved_validated_report',
        'writer_models':['gemini-3.7-flash','gemini-3.8-flash'],
        'writer_prompt':'bounded prompt',
        'business_writes':0,
        'persist_results':False,
    }


def _availability_report(statuses=(503,503)):
    return {
        'provider':'gemini',
        'provider_calls':len(statuses),
        'attempts':[{'model':f'm{i}','status':'error','http_status':s} for i,s in enumerate(statuses,1)],
        'business_writes':0,
        'persist_results':False,
    }


def test_503_pair_becomes_pending_without_business_write():
    rec=build_pending_writer_record(_fixture(),_availability_report(),now=NOW)
    assert rec['status']==PENDING_WRITER
    assert rec['retry_cycles']==1
    assert rec['business_writes']==0 and rec['persist_results'] is False
    assert validate_pending_writer_record(rec,now=NOW,allow_not_ready=True)==PENDING_WRITER
    assert validate_pending_writer_record(rec,now=NOW+timedelta(hours=4))==WRITER_READY


def test_404_is_deferrable_but_400_and_quality_success_are_not():
    rec=build_pending_writer_record(_fixture(),_availability_report((404,)),now=NOW)
    assert rec['retry_cycles']==1
    with pytest.raises(PendingWriterError,match='nonavailability'):
        build_pending_writer_record(_fixture(),_availability_report((400,)),now=NOW)
    success=_availability_report((503,))
    success['attempts']=[{'model':'gemini-3.7-flash','status':'success'}]
    success['text']='article'
    with pytest.raises(PendingWriterError,match='nonavailability|success'):
        build_pending_writer_record(_fixture(),success,now=NOW)


def test_cooldown_prevents_repeat_runs_from_burning_quota():
    rec=build_pending_writer_record(_fixture(),_availability_report(),now=NOW)
    with pytest.raises(PendingWriterError,match='cooldown_active'):
        validate_pending_writer_record(rec,now=NOW+timedelta(hours=1))


def test_retry_cycles_are_bounded_across_runs():
    first=build_pending_writer_record(_fixture(),_availability_report(),now=NOW)
    second=build_pending_writer_record(_fixture(),_availability_report(),previous=first,now=NOW+timedelta(hours=4))
    third=build_pending_writer_record(_fixture(),_availability_report(),previous=second,now=NOW+timedelta(hours=8))
    assert third['retry_cycles']==3
    with pytest.raises(PendingWriterError,match='retry_budget_exhausted'):
        build_pending_writer_record(_fixture(),_availability_report(),previous=third,now=NOW+timedelta(hours=12))


def test_payload_change_and_expiry_fail_closed():
    rec=build_pending_writer_record(_fixture(),_availability_report(),now=NOW)
    changed=_fixture(); changed['writer_prompt']='different prompt'
    with pytest.raises(PendingWriterError,match='payload_changed'):
        build_pending_writer_record(changed,_availability_report(),previous=rec,now=NOW+timedelta(hours=4))
    assert validate_pending_writer_record(rec,now=NOW+timedelta(hours=49),allow_not_ready=True)==WRITER_EXPIRED
