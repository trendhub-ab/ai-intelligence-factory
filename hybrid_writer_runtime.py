"""Hybrid writer runtime orchestration with durable availability deferral.

This is the only layer that combines the bounded Gemini writer attempt with the
runtime-state PENDING_WRITER store. It never writes Notion/note. Availability outages
are deferred; quality and non-availability errors remain fail-closed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from hybrid_one_shot import run_bounded_gemini_writer_calls
from hybrid_writer_deferred import (
    PENDING_WRITER,
    WRITER_EXPIRED,
    WRITER_READY,
    PendingWriterError,
    build_pending_writer_record,
    validate_pending_writer_record,
)
from hybrid_writer_state_store import (
    delete_pending_writer_state,
    load_pending_writer_state,
    save_pending_writer_state,
)


class HybridWriterRuntimeError(RuntimeError):
    pass


def _read_json(path: str) -> dict:
    try:
        value=json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:
        raise HybridWriterRuntimeError('hybrid_writer_runtime_json_invalid') from None
    if not isinstance(value,dict):
        raise HybridWriterRuntimeError('hybrid_writer_runtime_json_invalid')
    return value


def run_or_defer_writer(
    pipeline,
    fixture_path: str,
    report_path: str,
    pending_output_path: str,
    *,
    load_state: Callable = load_pending_writer_state,
    save_state: Callable = save_pending_writer_state,
    delete_state: Callable = delete_pending_writer_state,
    writer_runner: Callable = run_bounded_gemini_writer_calls,
) -> dict:
    """Run the bounded writer unless an existing pending record is still cooling down.

    Returns one of:
      {status: 'SUCCESS', report: ...}
      {status: 'DEFERRED', pending: ..., provider_calls: 0..2}
    Non-availability failures are re-raised and never enter PENDING_WRITER.
    """
    fixture=_read_json(fixture_path)
    candidate_id=str(fixture.get('candidate_id') or '')
    if not candidate_id:
        raise HybridWriterRuntimeError('hybrid_writer_candidate_missing')

    previous=load_state(candidate_id)
    if previous is not None:
        state=validate_pending_writer_record(previous,allow_not_ready=True)
        if state==WRITER_EXPIRED:
            delete_state(candidate_id)
            previous=None
        elif state==PENDING_WRITER:
            Path(pending_output_path).write_text(json.dumps(previous,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            return {'status':'DEFERRED','reason':'cooldown_active','provider_calls':0,'pending':previous}
        elif state!=WRITER_READY:
            raise HybridWriterRuntimeError('hybrid_writer_pending_state_invalid')

    try:
        report=writer_runner(pipeline,fixture_path,report_path)
    except RuntimeError as exc:
        if str(exc)!='hybrid_gemini_writer_unavailable':
            raise
        provider_report=_read_json(report_path)
        try:
            pending=build_pending_writer_record(fixture,provider_report,previous=previous)
        except PendingWriterError:
            raise
        save_state(pending)
        Path(pending_output_path).write_text(json.dumps(pending,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return {
            'status':'DEFERRED',
            'reason':'gemini_writer_temporarily_unavailable',
            'provider_calls':int(provider_report.get('provider_calls') or 0),
            'pending':pending,
        }

    delete_state(candidate_id)
    return {'status':'SUCCESS','provider_calls':int(report.get('provider_calls') or 0),'report':report}
