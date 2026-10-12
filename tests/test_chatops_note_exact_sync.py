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


if __name__ == "__main__":
    unittest.main()
