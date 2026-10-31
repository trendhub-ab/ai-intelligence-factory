"""Hard safety contract for the one-time P0-B creation-unknown audit.

Only authorized owner comment on canonical control issue can start a read-only
history inspection. The audit never authorizes ledger reset or note mutation.
"""
from pathlib import Path

PATH = Path(__file__).parents[1] / ".github/workflows/note-creation-unknown-readonly-audit.yml"


def test_exact_owner_and_immutable_target_scope():
    data = PATH.read_text(encoding="utf-8")
    for value in (
        "github.run_attempt == 1", "github.event.issue.number == 71",
        "github.event.issue.pull_request == null",
        "github.event.comment.user.login == 'trendhub-ab'",
        "github.actor == 'trendhub-ab'",
        "github.event.comment.body == '/aiif note audit creation_unknown 40a479ffdca981efb47bc5fe5fee1da9'",
        "NOTE_TARGET_SYNC_ID: '40a479ffdca981efb47bc5fe5fee1da9'",
        "NOTE_TARGET_IDENTITY: 'trendhub_biz'",
        "NOTE_RECOVERY_CONFIRM: AUDIT_CREATION_UNKNOWN",
    ):
        assert value in data


def test_read_only_and_browser_resource_guards():
    data = PATH.read_text(encoding="utf-8")
    for required in (
        "group: note-draft-create-v2",
        "cancel-in-progress: false",
        "NOTE_RECOVERY_PREPARE_ONLY: 'false'",
        "xvfb-run -a python note_delivery_creation_recovery.py",
        "NOTE_DELIVERY_LEDGER_PATH: '~/.aiif-note/delivery-ledger-v1.sqlite3'",
        "if: ${{ always() && needs.start-cloud-vm.result == 'success' }}",
        "match_count",
        "history_candidate_count",
    ):
        assert required in data
    for forbidden in (
        "CREATE_NOTE_DRAFT", "run194_note_persistent_cloud.py",
        "gh workflow run", "note-ready-sync.yml", "note-create-draft.yml",
        "git push", "upload-artifact", "notion.pages.update", "note.com/new",
        "record_draft_created", "record_queue_confirmed", "record_blocked",
        "gemini", "公開する", "投稿する",
    ):
        assert forbidden not in data


def test_recovery_script_exposes_safe_projection_not_identity():
    import inspect
    import note_delivery_creation_recovery as recovery

    source = inspect.getsource(recovery.safe_recovery_projection)
    assert "recovered_draft_id" not in source
    assert "sync_id" not in source
    assert "read_only" in source
    assert "draft_mutation" in source
    assert "public_release" in source
