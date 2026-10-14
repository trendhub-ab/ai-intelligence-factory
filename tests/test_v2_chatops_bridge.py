from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "chatops-one-shot.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_v2_shadow_observation_route_is_exact_and_constant() -> None:
    text = _workflow_text()
    assert "github.event.comment.body == '/aiif run v2_shadow_observation'" in text
    assert "v2_shadow_observation" in text
    assert "target='v2-shadow-observation.yml'" in text
    assert "payload='{\"ref\":\"main\",\"inputs\":{\"confirm\":\"RUN_V2_SHADOW_OBSERVATION\"}}'" in text


def test_v2_bridge_preserves_owner_control_issue_and_single_attempt_gates() -> None:
    text = _workflow_text()
    assert "github.run_attempt == 1" in text
    assert "github.event.issue.number == 71" in text
    assert "github.event.issue.pull_request == null" in text
    assert "github.event.comment.user.login == 'trendhub-ab'" in text
    assert "github.actor == 'trendhub-ab'" in text


def test_v2_bridge_uses_chainable_pat_without_forwarding_sensitive_credentials() -> None:
    text = _workflow_text()
    assert "GH_TOKEN: ${{ secrets.GH_PAT }}" in text
    assert "GH_TOKEN: ${{ github.token }}" not in text
    for forbidden in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "NOTION_API_KEY",
        "NOTION_TOKEN",
        "NOTE_COOKIE",
    ):
        assert forbidden not in text


def test_v2_bridge_dispatches_workflow_instead_of_running_execution_code_directly() -> None:
    text = _workflow_text()
    assert "python v2_shadow_observation.py" not in text
    assert "python production_pipeline.py" not in text
    assert '"/repos/${GITHUB_REPOSITORY}/actions/workflows/${target}/dispatches"' in text
