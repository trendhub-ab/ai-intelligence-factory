from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "note-ready-sync.yml"
DAILY = ROOT / ".github" / "workflows" / "daily.yml"


class Run194NoteReadyWorkflowTests(unittest.TestCase):
    def test_ready_sync_follows_manual_one_shot_while_normal_daily_is_paused(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        daily = DAILY.read_text(encoding="utf-8")
        self.assertIn("name: Daily Intelligence & Content Pipeline [PAUSED]", daily)
        workflow_run = source.split("workflow_run:", 1)[1].split("types:", 1)[0]
        self.assertIn("- Daily Intelligence & Content Pipeline [ONE-SHOT]\n", workflow_run)
        self.assertNotIn("- Daily Intelligence & Content Pipeline\n", workflow_run)
        self.assertNotIn("- Daily Intelligence & Content Pipeline [PAUSED]\n", workflow_run)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", source)

    def test_sync_remains_zero_model_and_has_no_note_publish_action(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("run: python note_ready_sync.py", source)
        self.assertNotIn("GEMINI_API_KEY", source)
        self.assertNotIn("note-create-draft", source)
        self.assertNotIn("公開", source)


if __name__ == "__main__":
    unittest.main()
