from pathlib import Path
import unittest


class Run247ChatOpsNoteBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = Path('.github/workflows/chatops-note.yml').read_text(encoding='utf-8')

    def test_fail_closed_control_surface(self):
        text = self.workflow
        self.assertIn("github.run_attempt == 1", text)
        self.assertIn("github.event.issue.number == 71", text)
        self.assertIn("github.event.issue.pull_request == null", text)
        self.assertIn("github.event.comment.user.login == 'trendhub-ab'", text)
        self.assertIn("github.actor == 'trendhub-ab'", text)
        self.assertIn("github.event.comment.body == '/aiif note sync'", text)
        self.assertIn("github.event.comment.body == '/aiif note draft'", text)

    def test_dispatches_only_existing_private_note_workflows(self):
        text = self.workflow
        self.assertIn("workflow='note-ready-sync.yml'", text)
        self.assertIn("workflow='note-create-draft.yml'", text)
        self.assertIn('CREATE_NOTE_DRAFT', text)
        self.assertIn('"prepare_only":"false"', text)
        self.assertNotIn('publish-note', text.lower())
        self.assertNotIn('production_pipeline.py', text)

    def test_bridge_is_zero_model_and_no_public_release(self):
        text = self.workflow
        self.assertIn('Gemini calls performed by bridge: `0`', text)
        self.assertIn('Production started: `false`', text)
        self.assertIn('public note release performed: `false`', text)


if __name__ == '__main__':
    unittest.main()
