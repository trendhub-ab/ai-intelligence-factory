from pathlib import Path


def test_member_ux_guard_change_triggers_main_integration_ci():
    workflow = Path(".github/workflows/integration-reconciliation-ci.yml").read_text(encoding="utf-8")
    assert "      - member_ux_guard.py" in workflow
