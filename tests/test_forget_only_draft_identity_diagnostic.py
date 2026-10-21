"""Provider-free guard for one-off held draft identity audit: read-only, no title leaks."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from operations import forget_only_draft_identity_diagnostic as diag


def test_source_identity_digest_is_fixed_and_distinct():
    assert len(diag.SOURCE_ID) == 32
    assert len(diag.DRAFT_ID_SHA256) == 64
    assert diag.OLD_TITLE_SHA256 != diag.NEW_TITLE_SHA256


def test_queue_refuses_nonheld_draft_before_browser():
    row = {
        "id":"queue",
        "properties":{
            "同期ID":{"rich_text":[{"plain_text":diag.SOURCE_ID}]},
            "note下書きID":{"rich_text":[{"plain_text":"wrong-id"}]},
            "投稿状態":{"select":{"name":"投稿準備中"}},
            "品質状態":{"select":{"name":"Ready"}},
            "記事タイトル":{"title":[{"plain_text":"unrelated"}]},
            "note公開URL":{"url":None},
            "投稿日":{"date":None},
        },
    }
    with patch.object(diag.sync,"_query_db",return_value=[row]):
        with pytest.raises(diag.Refused,match="draft_identity_changed"):
            diag.exact_queue()


def test_official_list_matches_old_and_new_by_hash_only():
    old="LEGACY_PRIVATE_TITLE"
    new="REVISED_PRIVATE_TITLE"
    controls = []
    for title in (old,new,"UNRELATED"):
        btn=MagicMock()
        btn.evaluate.return_value=title+"を編集"
        controls.append(btn)
    class Buttons:
        def count(self): return len(controls)
        def nth(self,idx): return controls[idx]
    page=MagicMock()
    page.url="https://note.com/notes"
    page.get_by_role.return_value=Buttons()
    page.locator.return_value.count.return_value=0
    with patch.object(diag,"OLD_TITLE_SHA256",diag.digest(old)),\
         patch.object(diag,"NEW_TITLE_SHA256",diag.digest(new)):
        assert diag._list_labels(page) == (1,1)
    page.goto.assert_called_once()
    assert not any(b.click.called for b in controls)


def test_workflow_cannot_perform_posting_or_swap():
    root=Path(__file__).resolve().parents[1]
    script=(root/"operations/forget_only_draft_identity_diagnostic.py").read_text(encoding="utf-8")
    workflow=(root/".github/workflows/forget-only-held-draft-audit.yml").read_text(encoding="utf-8")
    assert "/aiif audit forget-only held-draft-identity" in workflow
    assert "github.event.comment.user.login == 'trendhub-ab'" in workflow
    assert "forget_only_draft_identity_diagnostic" in workflow
    assert "SWAP_EXISTING_PRIVATE_DRAFT_ONCE" not in workflow
    assert "forget_only_private_swap_once" not in workflow
    assert "--apply" not in workflow
    assert "xvfb-run -a python" in workflow
    assert "page.click(" not in script
    assert "note_draft_automation._save" not in script
    assert "GEMINI_API_KEY" not in script
    assert "note_mutation" in script and "notion_mutation" in script


def test_read_only_probe_returns_categoric_and_boolean_fields(monkeypatch):
    class FakeContext:
        def new_page(self):
            return MagicMock()
        def close(self): pass
    class FakeSync:
        def __enter__(self): return SimpleNamespace()
        def __exit__(self,*args): pass
    monkeypatch.setattr(diag.chrome,"_launch_persistent_context", lambda _: FakeContext())
    monkeypatch.setattr(diag.chrome,"_assert_expected_note_account", lambda _: None)
    monkeypatch.setattr(diag,"_list_labels", lambda _: (1,0))
    monkeypatch.setattr(diag.drafts,"_draft_id_from_edit_url", lambda _: "test")
    result=diag.browser_probe("test")
    assert result["account_proven"] is True
    assert result["official_list_old_title_matches"] == 1
    assert result["same_existing_edit_route"] is True
    assert result["note_mutation"] is False
    assert result["new_draft_created"] is False
