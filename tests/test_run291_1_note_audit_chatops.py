from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "chatops-note.yml"
AUDIT_WORKFLOW = ROOT / ".github" / "workflows" / "note-private-draft-audit.yml"
GENREC_SYNC_ID = "3bd479ffdca9817f926aeaffbb779c4b"


class Run2911NoteAuditChatOpsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WORKFLOW.read_text(encoding="utf-8")
        cls.audit_source = AUDIT_WORKFLOW.read_text(encoding="utf-8")

    def test_existing_sync_and_draft_exact_commands_are_preserved(self) -> None:
        self.assertIn("github.event.comment.body == '/aiif note sync'", self.source)
        self.assertIn("github.event.comment.body == '/aiif note draft'", self.source)
        self.assertIn("'/aiif note sync') action='sync'", self.source)
        self.assertIn("'/aiif note draft') action='draft'", self.source)
        self.assertIn("workflow='note-ready-sync.yml'", self.source)
        self.assertIn("workflow='note-create-draft.yml'", self.source)
        self.assertIn('"confirm":"CREATE_NOTE_DRAFT"', self.source)

    def test_fixed_genrec_audit_chatops_route_is_retired(self) -> None:
        self.assertNotIn("github.event.comment.body == '/aiif note audit'", self.source)
        self.assertNotIn("'/aiif note audit') action='audit'", self.source)
        self.assertNotIn("            audit)\n", self.source)
        self.assertNotIn("workflow='note-private-draft-audit.yml'", self.source)
        self.assertNotIn(GENREC_SYNC_ID, self.source)

    def test_manual_exact_sync_audit_workflow_remains_available(self) -> None:
        self.assertTrue(AUDIT_WORKFLOW.is_file())
        self.assertIn("workflow_dispatch:", self.audit_source)
        self.assertIn("sync_id:", self.audit_source)
        self.assertIn("description: 'Exact Content Intelligence sync ID already in 投稿準備中'", self.audit_source)
        self.assertIn("required: true", self.audit_source)
        self.assertIn("AUDIT_NOTE_DRAFT", self.audit_source)
        self.assertNotIn("issue_comment:", self.audit_source)
        self.assertNotIn("schedule:", self.audit_source)

    def test_bridge_keeps_owner_issue_and_single_run_fail_closed_guards(self) -> None:
        for required in (
            "github.run_attempt == 1",
            "github.event.issue.number == 71",
            "github.event.issue.pull_request == null",
            "github.event.comment.user.login == 'trendhub-ab'",
            "github.actor == 'trendhub-ab'",
            "*) echo '::error::Refusing unknown Note ChatOps command'; exit 1 ;;",
            "*)\n              echo '::error::Refusing unknown action'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)

    def test_bridge_has_no_model_production_publication_or_direct_vm_surface(self) -> None:
        for forbidden in (
            "GEMINI_API_KEY",
            "gemini-",
            "pipeline.py",
            "run194_note_persistent_cloud.py",
            "gcloud compute instances start",
            "gcloud compute instances stop",
            "playwright",
            "公開する",
            "publish_note",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.source)

    def test_bridge_does_not_accept_prefix_or_extra_text_variants(self) -> None:
        self.assertNotIn("startsWith(github.event.comment.body", self.source)
        self.assertNotIn("contains(github.event.comment.body", self.source)


if __name__ == "__main__":
    unittest.main()
