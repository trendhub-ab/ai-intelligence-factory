from __future__ import annotations

from pathlib import Path


WORKFLOW = Path('.github/workflows/p0b-strong-zero-reconciliation-live.yml')


def _source() -> str:
    assert WORKFLOW.is_file(), 'live strong-zero reconciliation workflow must exist'
    return WORKFLOW.read_text(encoding='utf-8')


def test_live_reconciliation_is_marker_only_and_hosted_gcs():
    source = _source()
    assert 'push:' in source
    assert 'ops/p0b-hosted-b01-recovery-20261006' in source
    assert "- 'ops/p0b-strong-zero-reconcile.trigger'" in source
    assert 'workflow_dispatch:' not in source
    assert 'runs-on: ubuntu-24.04' in source
    assert 'id-token: write' in source
    assert 'NOTE_DELIVERY_LEDGER_BACKEND: gcs' in source
    assert 'NOTE_DELIVERY_LEDGER_PREFIX: delivery/v1' in source
    assert 'self-hosted' not in source
    assert 'systemd' not in source


def test_live_reconciliation_installs_pillow_before_snapshot_rebuild():
    source = _source()
    install = source.index('name: Install bounded recovery dependencies')
    reconcile = source.index('name: Reconcile strong zero with immutable snapshot')
    assert install < reconcile
    dependency_block = source[install:reconcile].lower()
    assert 'pillow' in dependency_block


def test_live_reconciliation_has_read_only_snapshot_and_ledger_gate_before_cas():
    source = _source()
    census = source.index('name: Run fresh strong-zero census')
    gate = source.index('name: Rebuild immutable snapshot and recheck ambiguous ledger read-only')
    reconcile = source.index('name: Reconcile strong zero with immutable snapshot')
    assert census < gate < reconcile

    gate_block = source[gate:reconcile]
    required = (
        'delivery_runtime.prepare_delivery(',
        'get_active_by_logical_key(',
        'DeliveryState.CREATION_UNKNOWN',
        'prepared.snapshot != record.snapshot',
        "str(record.draft_id or '').strip()",
        'P0B_PRE_CAS_GATE=immutable_snapshot_match_creation_unknown',
    )
    for token in required:
        assert token in gate_block

    forbidden = (
        'record_blocked(',
        'record_draft_created(',
        'record_verified(',
        'record_queue_confirmed(',
        'reconcile_strong_zero(',
        'patch_and_readback_draft_binding(',
    )
    for token in forbidden:
        assert token not in gate_block


def test_live_reconciliation_runs_fresh_census_before_one_cas_reconciliation():
    source = _source()
    census = source.index('name: Run fresh strong-zero census')
    reconcile = source.index('name: Reconcile strong zero with immutable snapshot')
    verify = source.index('name: Verify durable manual-reconciliation state')
    assert census < reconcile < verify

    assert 'python run_p0b_hosted_private_draft_census.py' in source
    assert 'current_contract.install()' in source
    assert 'presentation.install_note(current_contract.base)' in source
    assert 'delivery_runtime.prepare_delivery(' in source
    assert 'current_snapshot=prepared.snapshot' in source
    assert 'reconcile_strong_zero(' in source
    assert 'DeliveryState.MANUAL_RECONCILIATION_REQUIRED' in source


def test_live_reconciliation_cannot_create_edit_publish_or_patch_queue():
    source = _source()
    required = (
        'NOTE_STORAGE_STATE_B64',
        'zero_model_calls',
        'note_mutation_count',
        'creation_authorized',
        'public_release',
    )
    for token in required:
        assert token in source

    forbidden = (
        '_create_browser_draft(',
        'record_draft_created(',
        'record_verified(',
        'record_queue_confirmed(',
        'patch_and_readback_draft_binding(',
        'requests.post(',
        'workflow_dispatch:',
        'gemini',
        'openai',
    )
    lower = source.lower()
    for token in forbidden:
        assert token.lower() not in lower
