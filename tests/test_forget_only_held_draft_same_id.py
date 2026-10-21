"""Held Forget-Only replacement is exact, manual, private-only and fail closed."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from operations import forget_only_draft_identity_diagnostic as held


def test_held_destination_requires_same_source_and_manual_hold(monkeypatch):
    monkeypatch.setattr(held, "exact_queue", lambda: {"draft_id": "nprivate"})
    state = {"title": "AIに「忘れさせる」には、なぜ記憶が必要なのか？"}
    fake = SimpleNamespace(status_code=200, json=lambda: {})
    monkeypatch.setattr(held.sync, "_request", lambda *a, **k: fake)
    monkeypatch.setattr(held.sync, "_source_state", lambda _: state)
    dest = held._held_destination(held.SOURCE_ID)
    assert dest["posting_state"] == "保留"
    assert dest["note_draft_id"] == "nprivate"
    assert dest["title"] == state["title"]
    with pytest.raises(held.Refused, match="wrong_target"):
        held._held_destination("0" * 32)


def test_no_note_write_without_confirmed_same_draft_route(monkeypatch):
    writer = MagicMock()
    monkeypatch.setattr(held.chrome, "install", lambda: None)
    monkeypatch.setattr(held, "exact_queue", lambda: {"draft_id": "nprivate"})
    monkeypatch.setattr(held, "browser_probe", lambda _: {
        "account_proven": True,
        "same_existing_edit_route": False,
        "draft_editor_has_old_title": True,
        "draft_editor_has_new_title": False,
        "official_list_old_title_matches": 1,
        "official_list_new_title_matches": 0,
    })
    monkeypatch.setattr(held.drafts, "apply_current_article_to_existing_draft", writer)
    with pytest.raises(held.Refused, match="same_draft_route_not_proven"):
        held.replace_held_draft_once()
    writer.assert_not_called()


def test_no_note_write_on_missing_official_list_proof(monkeypatch):
    writer = MagicMock()
    monkeypatch.setattr(held.chrome, "install", lambda: None)
    monkeypatch.setattr(held, "exact_queue", lambda: {"draft_id": "nprivate"})
    monkeypatch.setattr(held, "browser_probe", lambda _: {
        "account_proven": True,
        "same_existing_edit_route": True,
        "draft_editor_has_old_title": True,
        "draft_editor_has_new_title": False,
        "official_list_old_title_matches": 0,
        "official_list_new_title_matches": 0,
    })
    monkeypatch.setattr(held.drafts, "apply_current_article_to_existing_draft", writer)
    with pytest.raises(held.Refused, match="official_list_has_no_matching"):
        held.replace_held_draft_once()
    writer.assert_not_called()


def test_workflow_is_exact_owner_only_and_releases_no_hold():
    root = Path(__file__).resolve().parents[1]
    flow = (root / ".github/workflows/forget-only-held-draft-same-id-replace.yml").read_text(encoding="utf8")
    implementation = (root / "operations/forget_only_draft_identity_diagnostic.py").read_text(encoding="utf8")
    assert "github.event.issue.number == 71" in flow
    assert "github.event.comment.user.login == 'trendhub-ab'" in flow
    assert "github.actor == 'trendhub-ab'" in flow
    assert "/aiif replace forget-only held-draft" in flow
    assert "--apply-held --confirm REPLACE_EXACT_HELD_DRAFT_ONCE" in flow
    assert "cancel-in-progress: false" in flow
    assert "issues: write" in flow
    assert "apply_current_article_to_existing_draft" in implementation
    assert "patch.object(drafts, \"destination_preflight\"" in implementation
    assert '"posting_state": "保留"' in implementation
    assert "note.com/notes/new" not in implementation
    assert "GEMINI_API_KEY" not in implementation
