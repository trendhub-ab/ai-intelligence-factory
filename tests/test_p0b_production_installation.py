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


def test_note_workflow_keeps_selected_sync_id_runner_local_and_off_cross_job_surfaces():
    source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
    preflight_block = source[source.index("  preflight:"):source.index("  start-cloud-vm:")]
    assert "selected_sync_id:" not in preflight_block
    assert "selected_sync_id={selected}" not in preflight_block
    assert "needs.preflight.outputs.selected_sync_id" not in source
    assert "NOTE_TARGET_SYNC_ID: ${{" not in source
    assert "GITHUB_EVENT_PATH" in preflight_block

    create_block = source[source.index("  create-draft:"):source.index("  stop-cloud-vm:")]
    assert "note_worker_preflight.json" in create_block
    assert "GITHUB_EVENT_PATH" in create_block
    assert 'NOTE_TARGET_SYNC_ID="$selected"' in create_block
    assert "selected_sync_id" not in "\n".join(
        line for line in create_block.splitlines() if "GITHUB_OUTPUT" in line or "fh.write(" in line
    )


def test_note_workflow_records_prepare_only_mode_in_safe_preflight_summary():
    source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
    summary_start = source.index("      - name: Summarize preflight result")
    summary_end = source.index("  start-cloud-vm:")
    summary_block = source[summary_start:summary_end]
    assert "PREPARE_ONLY: ${{ inputs.prepare_only }}" in summary_block
    assert "prepare-only mode" in summary_block
    assert "selected_sync_id" not in summary_block


def test_note_workflow_gates_on_private_ledger_before_heavy_delivery_steps():
    source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
    assert "  ledger-preflight:" not in source
    create_block = source[source.index("  create-draft:"):source.index("  stop-cloud-vm:")]
    ordered = [
        "Revalidate and pin exact candidate on private worker",
        "Read durable ledger authority before heavy browser setup",
        "Install persistent Chrome automation dependencies",
        "Zero-Gemini note draft tests",
        "Create one private note draft or reconcile the worker-pinned article",
    ]
    positions = [create_block.index(token) for token in ordered]
    assert positions == sorted(positions)
    assert "bash note_delivery_ledger_preflight.sh" in create_block
    assert "NOTE_DELIVERY_LEDGER_PATH" in create_block
    assert "id: ledger" in create_block
    assert create_block.count("steps.ledger.outputs.should_run_delivery == 'true'") >= 3

    light_prefix = create_block[:create_block.index("Install persistent Chrome automation dependencies")]
    assert "playwright" not in light_prefix
    assert "xvfb" not in light_prefix.lower()


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
