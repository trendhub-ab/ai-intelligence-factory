from __future__ import annotations

from pathlib import Path

import workflow_reference_guard as reference_guard


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "v2-shadow-observation.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_is_manual_only_and_requires_exact_confirmation():
    text = _text()

    assert reference_guard._top_level_on_triggers(text) == {"workflow_dispatch"}
    assert "RUN_V2_SHADOW_OBSERVATION" in text
    assert "inputs.confirm == 'RUN_V2_SHADOW_OBSERVATION'" in text


def test_workflow_has_read_only_permissions_and_no_secrets_or_provider_credentials():
    text = _text()

    assert "permissions:\n  contents: read\n" in text
    assert "contents: write" not in text
    assert "${{ secrets." not in text
    for forbidden in (
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "NOTION_API_KEY",
        "NOTION_DATA_SOURCE_ID",
        "GH_PAT",
    ):
        assert forbidden not in text


def test_workflow_cannot_call_production_or_automatic_paths():
    text = _text().lower()

    for forbidden in (
        "schedule:",
        "push:",
        "workflow_run:",
        "gh workflow run",
        "production_pipeline.py",
        "pipeline.py",
        "daily-one-shot.yml",
        "daily.yml",
        "fresh-zero-model-preflight.yml",
        "note-ready-sync.yml",
    ):
        assert forbidden not in text


def test_workflow_uses_pinned_runtime_locked_dependencies_and_focused_tests_before_live_run():
    text = _text()

    assert "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803" in text
    assert "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1" in text
    assert "python-version: '3.11.16'" in text
    assert "requirements.txt" in text
    assert "requirements-ci-constraints.txt" in text
    assert "pytest==8.4.2" in text
    focused = text.index("tests/test_v2_shadow_observation_workflow.py")
    live = text.index("python v2_shadow_observation.py")
    assert focused < live


def test_workflow_uploads_only_the_expected_short_lived_json_artifact():
    text = _text()

    assert "python v2_shadow_observation.py" in text
    assert "--output article_audit/v2_shadow_observation.json" in text
    assert "actions/upload-artifact@v7" in text
    assert "path: article_audit/v2_shadow_observation.json" in text
    assert "if-no-files-found: error" in text
    assert "retention-days: 14" in text
