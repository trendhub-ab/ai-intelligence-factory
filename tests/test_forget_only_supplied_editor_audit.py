"""Provider-free verification for a privately staged note editor URL."""
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from operations import forget_only_supplied_editor_audit as u


def _private_stage(url: str):
    return [{"type": "paragraph", "paragraph": {"rich_text": [
        {"plain_text": "候補note編集URL: " + url}
    ]}}]


def test_only_user_provided_exact_candidate_hash_is_accepted():
    url = "https://editor.note.com/notes/n40cb200b1c27/edit/"
    with patch.object(u.stage, "children", return_value=_private_stage(url)):
        assert u.candidate() == "n40cb200b1c27"


@pytest.mark.parametrize("url", [
    "https://note.com/notes/n40cb200b1c27/edit/",
    "http://editor.note.com/notes/n40cb200b1c27/edit/",
    "https://editor.note.com/notes/n40cb200b1c27/edit/?publish=true",
    "https://editor.note.com/notes/n2bf954920ec4/edit/",
    "https://editor.note.com/notes/n40cb200b1c27/new",
    "https://editor.note.com/notes/n40cb200b1c27/edit/#x",
])
def test_wrong_host_path_id_or_query_fails_closed(url):
    with patch.object(u.stage, "children", return_value=_private_stage(url)):
        with pytest.raises(u.audit.Refused):
            u.candidate()


def test_duplicate_candidate_fails_closed():
    stage = _private_stage("https://editor.note.com/notes/n40cb200b1c27/edit/")
    with patch.object(u.stage, "children", return_value=stage + stage):
        with pytest.raises(u.audit.Refused, match="not_unique"):
            u.candidate()


def test_preflight_makes_no_browser_or_db_mutations():
    with patch.object(u.audit, "exact_queue", return_value={"draft_id":"nold"}), \
         patch.object(u, "candidate", return_value="nnew"), \
         patch.object(u.audit,"browser_probe") as probe:
        result = u.check(browser=False)
    assert result["status"] == "candidate_preflight_pass"
    assert result["note_mutation"] is False
    assert result["notion_mutation"] is False
    probe.assert_not_called()


def test_editor_title_and_route_must_both_match():
    with patch.object(u.audit,"exact_queue",return_value={"draft_id":"nold"}), \
         patch.object(u,"candidate",return_value="nnew"), \
         patch.object(u.audit.chrome,"install"), \
         patch.object(u.audit,"browser_probe",return_value={
             "account_proven":True,
             "same_existing_edit_route":True,
             "draft_editor_has_old_title":False,
             "draft_editor_has_new_title":False,
             "official_list_old_title_matches":1,
             "official_list_new_title_matches":0,
         }):
        with pytest.raises(u.audit.Refused, match="supplied_candidate_identity_unproven"):
            u.check(browser=True)


def test_readonly_workflow_is_exact_owner_only():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    script=(root/"operations/forget_only_supplied_editor_audit.py").read_text()
    flow=(root/".github/workflows/forget-only-supplied-editor-audit.yml").read_text()
    assert "github.event.issue.number == 71" in flow
    assert "github.event.comment.user.login == 'trendhub-ab'" in flow
    assert "github.actor == 'trendhub-ab'" in flow
    assert "/aiif audit forget-only supplied-editor-identity" in flow
    assert "NOTION_API_KEY" in flow
    assert "sudo apt-get" not in flow
    assert "fonts-noto-cjk" not in flow
    assert "note_mutation" in script and "notion_mutation" in script
    assert "GEMINI_API_KEY" not in script
    assert "new_draft_created" not in script
    assert "note.com/notes/new" not in script
    assert "notion_update" not in script
