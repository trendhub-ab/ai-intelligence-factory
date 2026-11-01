from pathlib import Path
import unittest


WORKFLOW = Path(".github/workflows/chatops-note.yml")


class ChatOpsNoteExactSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_bare_note_sync_route_is_preserved(self):
        self.assertIn("github.event.comment.body == '/aiif note sync'", self.text)
        self.assertIn("'/aiif note sync') action='sync' ;;", self.text)
        self.assertIn("payload='{\"ref\":\"main\"}'", self.text)

    def test_exact_note_sync_route_accepts_only_a_pinned_sync_id(self):
        self.assertIn("startsWith(github.event.comment.body, '/aiif note sync ')", self.text)
        self.assertIn("'/aiif note sync '*)", self.text)
        self.assertIn("action='sync_exact'", self.text)
        self.assertIn("sync_id=\"${COMMAND#'/aiif note sync '}\"", self.text)
        self.assertIn("^[0-9a-fA-F]{32}$", self.text)

    def test_exact_note_sync_dispatches_ready_sync_with_exact_target(self):
        self.assertIn("sync_exact)", self.text)
        self.assertIn("workflow='note-ready-sync.yml'", self.text)
        self.assertIn('"create_private_draft":"true"', self.text)
        self.assertIn('"target_sync_id":"%s"', self.text)
        self.assertIn("\"$SYNC_ID\"", self.text)


    def test_manual_terra_override_is_hard_bound_to_exact_target_and_one_shot_token(self):
        import inspect
        import note_delivery_ledger as ledger
        import note_delivery_runtime as runtime
        workflow = Path(".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
        sh = Path("note_delivery_ledger_preflight.sh").read_text(encoding="utf-8")
        cmd = "/aiif note terra recreate 40a479ffdca981efb47bc5fe5fee1da9"
        self.assertIn(f"github.event.comment.body == '{cmd}'", self.text)
        self.assertIn(f"'{cmd}') action='terra_manual_recreate'", self.text)
        self.assertIn('terra_manual_recreate)', self.text)
        self.assertIn('"ASSUME_ABSENT_TERRA_ONCE"', self.text)
        self.assertIn('terra_manual_recreate:', workflow)
        self.assertIn("default: ''", workflow)
        self.assertIn("NOTE_TERRA_MANUAL_RECREATE_TOKEN", workflow)
        self.assertIn("NOTE_TERRA_MANUAL_RECREATE_TOKEN", sh)
        self.assertIn("owner_assumed_absent_once", sh)
        self.assertIn("CREATE_INTENT_RECORDED", inspect.getsource(
            ledger.SQLiteDeliveryLedger.authorize_terra_owner_assumed_absent_once
        ))
        self.assertIn("terra_manual_confirmation", inspect.getsource(
            runtime.create_or_resume_delivery
        ))
        self.assertIn("terra_manual_confirmation=manual_token", inspect.getsource(
            runtime.install
        ))


if __name__ == "__main__":
    unittest.main()
