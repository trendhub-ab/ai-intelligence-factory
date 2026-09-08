from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "chatops-note.yml"
GENREC_SYNC_ID = "3bd479ffdca9817f926aeaffbb779c4b"


class Run2911NoteAuditChatOpsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_existing_sync_and_draft_exact_commands_are_preserved(self) -> None:
        self.assertIn("github.event.comment.body == '/aiif note sync'", self.source)
        self.assertIn("github.event.comment.body == '/aiif note draft'", self.source)
        self.assertIn("'/aiif note sync') action='sync'", self.source)
        self.assertIn("'/aiif note draft') action='draft'", self.source)
        self.assertIn("workflow='note-ready-sync.yml'", self.source)
        self.assertIn("workflow='note-create-draft.yml'", self.source)
        self.assertIn('"confirm":"CREATE_NOTE_DRAFT"', self.source)

    def test_audit_command_is_exact_and_dispatches_only_read_only_audit_workflow(self) -> None:
        self.assertIn("github.event.comment.body == '/aiif note audit'", self.source)
        self.assertIn("'/aiif note audit') action='audit'", self.source)
        audit_case = self.source.split("            audit)\n", 1)[1].split("            *)", 1)[0]
        self.assertIn("workflow='note-private-draft-audit.yml'", audit_case)
        self.assertIn('"confirm":"AUDIT_NOTE_DRAFT"', audit_case)
        self.assertIn(f'"sync_id":"{GENREC_SYNC_ID}"', audit_case)
        self.assertNotIn("note-create-draft.yml", audit_case)
        self.assertNotIn("CREATE_NOTE_DRAFT", audit_case)

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

    def test_audit_route_does_not_accept_prefix_or_extra_text_variants(self) -> None:
        # The GitHub-expression gate and shell case both contain only literal exact commands.
        self.assertNotIn("startsWith(github.event.comment.body", self.source)
        self.assertNotIn("contains(github.event.comment.body", self.source)
        self.assertNotIn("'/aiif note audit '*", self.source)
        self.assertNotIn("'/aiif note audit'*)", self.source)


if __name__ == "__main__":
    unittest.main()
