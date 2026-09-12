import copy
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from hybrid_one_shot import build_writer_fixture
from hybrid_writer_deferred import build_pending_writer_record
from hybrid_writer_package import WriterPackageError, restore_pending_package
from hybrid_writer_runtime import resume_saved_writer, run_or_defer_writer, HybridWriterRuntimeError

INPUT = 'tests/fixtures/groq/article_parity_B0049_input.json'
PLAN = 'tests/fixtures/groq/two_pass_v3_plan_safe_report.json'


def pending(tmp_path):
    fixture = build_writer_fixture(INPUT, PLAN, str(tmp_path / 'initial.json'))
    report = {'attempts': [{'model': 'gemini-3.7-flash', 'status': 'error', 'http_status': 503}]}
    return build_pending_writer_record(fixture, report,
        now=datetime.now(timezone.utc) - timedelta(hours=5))


def test_resume_uses_only_durable_record_in_empty_directory(tmp_path):
    record = pending(tmp_path)
    (tmp_path / 'initial.json').unlink()
    calls = []
    def runner(pipeline, fixture_path, report_path):
        calls.append(json.loads(open(fixture_path).read()))
        return {'provider_calls': 1, 'text': 'writer response'}
    result = resume_saved_writer(SimpleNamespace(), 'B0049', str(tmp_path / 'fresh'),
        load_state=lambda cid: record, save_state=lambda rec: None,
        delete_state=lambda cid: None, writer_runner=runner)
    assert result['status'] == 'SUCCESS'
    assert result['quality_validated'] is False
    assert len(calls) == 1
    assert calls[0] == record['writer_snapshot']['fixture']
    restored = json.loads(open(result['restored_paths']['plan_report']).read())
    # Preserve current Fact-Locked provenance. Recovery must restore the exact validated
    # composed Plan, never reinterpret the raw categorical Groq output as prose evidence.
    assert restored['mode'] == 'hybrid_groq_judgment_fact_locked'
    assert restored['status'] == 'PLAN_VALIDATED'
    assert restored['semantic_plan_validated'] is True
    assert restored['fact_envelope_sha256']
    assert restored['composed_plan']['decision'] == 'WATCH'
    assert restored['composed_plan']['access_status'] == 'NOT_CONFIRMED'


@pytest.mark.parametrize('field', ['writer_prompt', 'writer_max_output_tokens', 'decision_package'])
def test_mutated_saved_material_rejected(tmp_path, field):
    record = pending(tmp_path)
    record['writer_snapshot']['fixture'][field] = 'changed'
    with pytest.raises(WriterPackageError, match='hash_mismatch'):
        restore_pending_package(record, str(tmp_path / 'restore'))
    assert not (tmp_path / 'restore').exists()


def test_same_prompt_with_changed_evidence_blocked_before_call(tmp_path):
    record = pending(tmp_path)
    fixture = copy.deepcopy(record['writer_snapshot']['fixture'])
    fixture['decision_package']['input']['source_context'] = 'different evidence'
    path = tmp_path / 'changed.json'
    path.write_text(json.dumps(fixture))
    calls = []
    with pytest.raises(HybridWriterRuntimeError, match='payload_changed'):
        run_or_defer_writer(SimpleNamespace(), str(path), str(tmp_path / 'report.json'),
            str(tmp_path / 'pending.json'), load_state=lambda cid: record,
            writer_runner=lambda *args: calls.append(True))
    assert calls == []


def test_restore_refuses_to_overwrite_existing_material(tmp_path):
    record = pending(tmp_path)
    directory = tmp_path / 'restore'
    restore_pending_package(record, str(directory))
    with pytest.raises(WriterPackageError, match='target_exists'):
        restore_pending_package(record, str(directory))
