from __future__ import annotations

from pathlib import Path

import run202_chatops_control as chatops


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "v2-shadow-deep-dive.yml"
CHATOPS_WORKFLOW = ROOT / ".github" / "workflows" / "chatops-one-shot.yml"


def _event(body: str):
    return {
        "issue": {"number": 71},
        "comment": {"user": {"login": "trendhub-ab"}, "body": body},
    }


def test_exact_v2_shadow_deep_dive_command_is_authorized():
    assert chatops.authorize_event(_event("/aiif run v2_shadow_deep_dive")) == {
        "authorized": True,
        "mode": "v2_shadow_deep_dive",
        "target_sync_id": "",
        "reason": "authorized",
    }


def test_v2_shadow_deep_dive_command_rejects_malformed_variants():
    for body in (
        "/aiif run v2_shadow_deep_dive ",
        " /aiif run v2_shadow_deep_dive",
        "/aiif run v2_shadow_deep_dive\n",
        "/aiif run V2_shadow_deep_dive",
        "/aiif run v2-shadow-deep-dive",
        "/aiif run v2_shadow_deep_dive please",
    ):
        assert chatops.authorize_event(_event(body))["authorized"] is False


def test_v2_workflow_is_manual_read_only_and_exactly_confirmed():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "push:" not in text
    assert "RUN_V2_SHADOW_DEEP_DIVE" in text
    assert "inputs.confirm == 'RUN_V2_SHADOW_DEEP_DIVE'" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "ubuntu-24.04" in text
    assert "python-version: '3.11.16'" in text
    assert "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6" in text
    assert "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6" in text
    assert "actions/upload-artifact@v7" in text
    assert "retention-days: 14" in text


def test_v2_workflow_receives_only_model_secret_and_writes_diagnostic_artifact():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}" in text
    for forbidden in (
        "NOTION_API_KEY",
        "NOTION_DATABASE_ID",
        "GH_PAT:",
        "TELEGRAM_BOT_TOKEN",
        "APIFY_TOKEN",
        "note.com",
        "production_pipeline.py",
        "pipeline.py",
    ):
        assert forbidden not in text
    assert "v2_shadow_observation.py" in text
    assert "--mode provider_backed_one_shot" in text
    assert "article_audit/v2_shadow_deep_dive.json" in text


def test_chatops_bridge_dispatches_exact_reviewed_v2_workflow_payload():
    text = CHATOPS_WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.comment.body == '/aiif run v2_shadow_deep_dive'" in text
    assert "v2_shadow_deep_dive)" in text
    assert "target='v2-shadow-deep-dive.yml'" in text
    assert "payload='{\"ref\":\"main\",\"inputs\":{\"confirm\":\"RUN_V2_SHADOW_DEEP_DIVE\"}}'" in text
    assert "GH_TOKEN: ${{ secrets.GH_PAT }}" in text
    assert "GH_TOKEN: ${{ github.token }}" not in text
