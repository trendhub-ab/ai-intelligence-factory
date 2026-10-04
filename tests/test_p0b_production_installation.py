from pathlib import Path
import inspect

import note_delivery_runtime as runtime
import run194_note_persistent_cloud as run194


ROOT = Path(__file__).resolve().parents[1]


def test_run194_installs_p0b_runtime_after_all_existing_gates():
    source = inspect.getsource(run194.main)
    ordered = [
        "cloud.install()",
        "current_contract.install()",
        "run222.install_note(cloud.base)",
        "eyecatch_persistence.install_creation_persistence_guard(cloud.base)",
        "note_lifecycle.install_draft_identity(cloud.base)",
        "delivery_runtime.install(cloud.base)",
        "current_contract.run_base_main_with_safe_noop()",
    ]
    positions = [source.index(token) for token in ordered]
    assert positions == sorted(positions)


def test_runtime_installer_owns_write_enabled_run_and_safe_projection():
    source = inspect.getsource(runtime.install)
    assert "base.run = _run" in source
    assert "create_or_resume_delivery" in source
    assert "reconcile_exact_delivery" in source
    projection = inspect.getsource(runtime.safe_delivery_result)
    for forbidden in ("sync_id", "draft_id", "queue_page_id", "operation_key", "revision_key", "ledger.path"):
        assert forbidden not in projection


def test_note_workflow_configures_private_ledger_without_uploading_it():
    source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
    assert "NOTE_DELIVERY_LEDGER_PATH" in source
    assert "NOTE_TARGET_IDENTITY" in source
    assert "tests/test_note_delivery_ledger.py" in source
    assert "tests/test_note_delivery_runtime.py" in source
    assert "tests/test_note_delivery_human_edit_guard.py" in source
    assert "tests/test_run295_note_eyecatch_persistence.py" in source
    assert "tests/test_p0b_eyecatch_callback_forwarding.py" in source
    assert "upload-artifact" not in source
    summary_writes = [
        line.strip()
        for line in source.splitlines()
        if "fh.write(" in line
    ]
    assert summary_writes
    assert all("NOTE_DELIVERY_LEDGER_PATH" not in line for line in summary_writes)
    assert all("delivery-ledger" not in line.lower() for line in summary_writes)


def test_note_workflow_does_not_mask_cross_job_selected_sync_id():
    source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
    export_start = source.index("      - name: Export VM decision")
    export_end = source.index("      - name: Summarize preflight result")
    export_block = source[export_start:export_end]
    assert "selected_sync_id={selected}" in export_block
    assert "::add-mask::" not in export_block
    assert "NOTE_TARGET_SYNC_ID: ${{ needs.preflight.outputs.selected_sync_id }}" in source


def test_note_workflow_records_prepare_only_mode_in_safe_preflight_summary():
    source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
    summary_start = source.index("      - name: Summarize preflight result")
    summary_end = source.index("  start-cloud-vm:")
    summary_block = source[summary_start:summary_end]
    assert "PREPARE_ONLY: ${{ inputs.prepare_only }}" in summary_block
    assert "prepare-only mode" in summary_block
    assert "selected_sync_id" not in summary_block


def test_note_workflow_gates_on_private_ledger_before_heavy_delivery_job():
    source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
    ledger_job = source.index("  ledger-preflight:")
    create_job = source.index("  create-draft:")
    assert ledger_job < create_job

    ledger_block = source[ledger_job:create_job]
    assert "runs-on: [self-hosted, linux, x64, aiif-note-cloud]" in ledger_block
    assert "bash note_delivery_ledger_preflight.sh" in ledger_block
    assert "NOTE_TARGET_SYNC_ID: ${{ needs.preflight.outputs.selected_sync_id }}" in ledger_block
    assert "NOTE_DELIVERY_LEDGER_PATH: '~/.aiif-note/delivery-ledger-v1.sqlite3'" in ledger_block
    assert "should_run_delivery" in ledger_block
    assert "pip install" not in ledger_block
    assert "playwright" not in ledger_block
    assert "xvfb" not in ledger_block.lower()

    create_block = source[create_job:source.index("  stop-cloud-vm:")]
    assert "needs: [preflight, start-cloud-vm, ledger-preflight]" in create_block
    assert "needs.ledger-preflight.outputs.should_run_delivery == 'true'" in create_block


def test_ledger_preflight_is_non_python_ops_surface():
    assert (ROOT / "note_delivery_ledger_preflight.sh").is_file()
    assert not (ROOT / "note_delivery_ledger_preflight.py").exists()


def test_offline_verification_tracks_ledger_preflight_script():
    source = (ROOT / ".github/workflows/p0b-offline-verification.yml").read_text(encoding="utf-8")
    assert "'note_delivery_ledger_preflight.sh'" in source


def test_runtime_public_result_has_no_private_delivery_identity():
    result = runtime.safe_delivery_result(status="queue_confirmed", telegram_notified=False)
    assert result == {
        "success": True,
        "status": "queue_confirmed",
        "zero_gemini_calls": True,
        "telegram_notified": False,
        "public_release": False,
    }
