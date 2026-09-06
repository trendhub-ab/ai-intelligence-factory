from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "note-ready-sync.yml"
ONE_SHOT = ROOT / ".github" / "workflows" / "daily-one-shot.yml"
DAILY = ROOT / ".github" / "workflows" / "daily.yml"


class Run194NoteReadyWorkflowTests(unittest.TestCase):
    def test_ready_sync_follows_manual_one_shot_via_explicit_dispatch_while_daily_is_paused(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        one_shot = ONE_SHOT.read_text(encoding="utf-8")
        daily = DAILY.read_text(encoding="utf-8")

        self.assertIn("name: Daily Intelligence & Content Pipeline [PAUSED]", daily)
        self.assertIn("if: ${{ false }}", daily)

        self.assertIn("workflow_dispatch:", source)
        self.assertNotIn("Daily Intelligence & Content Pipeline [ONE-SHOT]", source)
        self.assertIn("GH_TOKEN: ${{ secrets.GH_PAT }}", one_shot)
        self.assertIn("note-ready-sync.yml", one_shot)
        self.assertIn("if: ${{ success() }}", one_shot)

    def test_sync_remains_zero_model_and_has_no_note_publish_action(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("run: python note_ready_sync.py", source)
        self.assertNotIn("GEMINI_API_KEY", source)
        self.assertNotIn("note-create-draft", source)
        self.assertNotIn("公開", source)


if __name__ == "__main__":
    unittest.main()
