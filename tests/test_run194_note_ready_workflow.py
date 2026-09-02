from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "note-ready-sync.yml"


class Run194NoteReadyWorkflowTests(unittest.TestCase):
    def test_ready_sync_follows_both_normal_daily_and_manual_one_shot(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("- Daily Intelligence & Content Pipeline\n", source)
        self.assertIn("- Daily Intelligence & Content Pipeline [ONE-SHOT]\n", source)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", source)

    def test_sync_remains_zero_model_and_has_no_note_publish_action(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("run: python note_ready_sync.py", source)
        self.assertNotIn("GEMINI_API_KEY", source)
        self.assertNotIn("note-create-draft", source)
        self.assertNotIn("公開", source)


if __name__ == "__main__":
    unittest.main()
