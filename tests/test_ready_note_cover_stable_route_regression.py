from unittest.mock import Mock, patch

import pytest

import ready_note_cover_apply as target


def test_find_exact_existing_draft_uses_persisted_stable_identity_not_history():
    article = {
        "draft_id": "nabc123",
        "title": "対象記事タイトル",
        "manuscript": "## 本文\n承認済み本文" * 20,
    }
    stable_route = "https://note.com/notes/nabc123/edit"
    page = Mock()
    page.url = stable_route

    with patch.object(target.audit_base, "_draft_edit_url", return_value=stable_route) as build_route, \
         patch.object(target.note_base, "_looks_logged_out", return_value=False), \
         patch.object(target.audit_base, "_is_note_edit_url", return_value=True), \
         patch.object(target.audit_base, "_title_value", return_value=article["title"]), \
         patch.object(target, "_audit_current_private_draft", return_value={"ok": True}), \
         patch.object(target.audit_base, "_recent_private_edit_urls", create=True) as legacy_history:
        legacy_history.side_effect = AssertionError("cover apply must not use Chrome history discovery")
        result = target._find_exact_existing_draft(page, Mock(), article)

    assert result == stable_route
    build_route.assert_called_once_with(article["draft_id"])
    page.goto.assert_called_once_with(stable_route, wait_until="domcontentloaded", timeout=60000)
    legacy_history.assert_not_called()


def test_find_exact_existing_draft_accepts_editor_host_redirect_for_same_persisted_identity():
    article = {
        "draft_id": "nabc123",
        "title": "対象記事タイトル",
        "manuscript": "## 本文\n承認済み本文" * 20,
    }
    stable_route = "https://note.com/notes/nabc123/edit"
    redirected_route = "https://editor.note.com/notes/nabc123/edit"
    page = Mock()
    page.url = redirected_route

    with patch.object(target.audit_base, "_draft_edit_url", return_value=stable_route), \
         patch.object(target.note_base, "_looks_logged_out", return_value=False), \
         patch.object(target.audit_base, "_title_value", return_value=article["title"]), \
         patch.object(target, "_audit_current_private_draft", return_value={"ok": True}):
        result = target._find_exact_existing_draft(page, Mock(), article)

    assert result == redirected_route


def test_find_exact_existing_draft_rejects_redirect_to_different_draft_identity():
    article = {
        "draft_id": "nabc123",
        "title": "対象記事タイトル",
        "manuscript": "## 本文\n承認済み本文" * 20,
    }
    stable_route = "https://note.com/notes/nabc123/edit"
    wrong_route = "https://editor.note.com/notes/other456/edit"
    page = Mock()
    page.url = wrong_route

    with patch.object(target.audit_base, "_draft_edit_url", return_value=stable_route), \
         patch.object(target.note_base, "_looks_logged_out", return_value=False):
        with pytest.raises(target.ReadyNoteCoverError, match="persisted edit route"):
            target._find_exact_existing_draft(page, Mock(), article)
