from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "note-cloud-runner-user-repair.yml"


def _workflow_text() -> str:
    assert WORKFLOW.exists(), "temporary note runner user repair workflow must exist"
    return WORKFLOW.read_text(encoding="utf-8")


def test_repair_workflow_is_bounded_and_fail_closed():
    text = _workflow_text()

    assert "github.event.issue.number == 71" in text
    assert "/aiif repair note-cloud-runner-user" in text
    assert "trendhub_biz_gmail_com" in text
    assert "1570601541" in text
    assert "getent passwd" in text
    assert "getent group" in text
    assert "groupadd" in text
    assert "useradd" in text
    assert "--no-create-home" in text
    assert "chown" not in text


def test_repair_workflow_proves_persistence_and_restores_metadata():
    text = _workflow_text()

    assert "AIIF_REPAIR_OWNERSHIP_UNCHANGED=yes" in text
    assert "AIIF_REPAIR_RUNNER_ONLINE=yes" in text
    assert "AIIF_REPAIR_REBOOT_RUNNER_ONLINE=yes" in text
    assert "AIIF_REPAIR_FINAL_VM_STOPPED=yes" in text
    assert "Original startup script restored exactly by SHA-256." in text
