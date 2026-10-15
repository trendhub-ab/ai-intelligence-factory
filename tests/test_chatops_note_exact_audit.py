from pathlib import Path
import unittest


WORKFLOW = Path('.github/workflows/chatops-note-audit.yml')


class ChatOpsNoteExactAuditContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding='utf-8')

    def test_generic_exact_read_only_audit_command_is_authorized_and_fail_closed(self):
        self.assertIn("startsWith(github.event.comment.body, '/aiif note audit ')", self.text)
        self.assertIn("github.event.comment.body != '/aiif note audit openai2015'", self.text)
        self.assertIn("'/aiif note audit '*)", self.text)
        self.assertIn("sync_id=\"${COMMAND#'/aiif note audit '}\"", self.text)
        self.assertIn("grep -Eq '^[0-9a-fA-F]{32}$'", self.text)
        self.assertIn("github.event.issue.number == 71", self.text)
        self.assertIn("github.event.comment.user.login == 'trendhub-ab'", self.text)
        self.assertIn("github.actor == 'trendhub-ab'", self.text)

    def test_exact_audit_dispatches_only_existing_read_only_workflow(self):
        self.assertIn("note-private-draft-audit.yml/dispatches", self.text)
        self.assertIn("AUDIT_NOTE_DRAFT", self.text)
        self.assertIn("sync_id\":\"%s\"", self.text)
        self.assertIn("exact private-draft read-only audit authorized for sync_id", self.text)
        self.assertIn("draft mutation authorized: `false`", self.text)
        self.assertIn("public note release authorized: `false`", self.text)
        self.assertNotIn("note-ready-sync.yml", self.text)
        self.assertNotIn("CREATE_NOTE_DRAFT", self.text)

    def test_same_issue_comment_is_claimed_once_before_dispatch(self):
        self.assertIn("issues: write", self.text)
        self.assertIn("github.event.comment.id", self.text)
        self.assertIn('id: claim', self.text)
        self.assertIn('/issues/comments/${COMMENT_ID}/reactions', self.text)
        self.assertIn('github-actions[bot]', self.text)
        self.assertIn('content=eyes', self.text)
        self.assertIn("steps.claim.outputs.dispatch == 'true'", self.text)
        self.assertLess(self.text.index('id: claim'), self.text.index('note-private-draft-audit.yml/dispatches'))


if __name__ == '__main__':
    unittest.main()
