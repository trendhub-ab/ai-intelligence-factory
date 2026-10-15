from pathlib import Path
import unittest


WORKFLOW = Path('.github/workflows/chatops-note.yml')


class ChatOpsNoteExactAuditContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding='utf-8')

    def test_generic_exact_read_only_audit_command_is_authorized_and_parsed(self):
        self.assertIn("startsWith(github.event.comment.body, '/aiif note audit ')", self.text)
        self.assertIn("'/aiif note audit '*)", self.text)
        self.assertIn("action='audit_exact'", self.text)
        self.assertIn("sync_id=\"${COMMAND#'/aiif note audit '}\"", self.text)
        self.assertIn("[ \"${action}\" = 'audit_exact' ]", self.text)
        self.assertIn("grep -Eq '^[0-9a-fA-F]{32}$'", self.text)

    def test_exact_audit_dispatches_read_only_workflow_not_ready_sync(self):
        self.assertIn("audit_exact)", self.text)
        self.assertIn("workflow='note-private-draft-audit.yml'", self.text)
        self.assertIn("AUDIT_NOTE_DRAFT", self.text)
        self.assertIn("sync_id\":\"%s\"", self.text)
        self.assertIn("exact private-draft read-only audit authorized for sync_id", self.text)
        self.assertIn("'/aiif note audit openai2015') action='openai2015_audit'", self.text)


if __name__ == '__main__':
    unittest.main()
