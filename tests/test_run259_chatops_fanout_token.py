from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHATOPS = ROOT / ".github" / "workflows" / "chatops-one-shot.yml"
NOTE_SYNC = ROOT / ".github" / "workflows" / "note-ready-sync.yml"
SUBSCRIBER_SYNC = ROOT / ".github" / "workflows" / "subscriber-decision-brief.yml"


class Run259ChatOpsFanoutTokenTests(unittest.TestCase):
    def test_chatops_dispatch_requires_pat_not_repository_token(self):
        text = CHATOPS.read_text(encoding="utf-8")
        self.assertIn("GH_TOKEN: ${{ secrets.GH_PAT }}", text)
        self.assertNotIn("GH_TOKEN: ${{ github.token }}", text)
        self.assertIn('if [ -z "${GH_TOKEN:-}" ]; then', text)
        self.assertIn("GH_PAT is required for ChatOps ONE-SHOT dispatch", text)

    def test_note_sync_still_subscribes_to_one_shot_completion(self):
        text = NOTE_SYNC.read_text(encoding="utf-8")
        self.assertIn("workflow_run:", text)
        self.assertIn("Daily Intelligence & Content Pipeline [ONE-SHOT]", text)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", text)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", text)

    def test_subscriber_sync_still_subscribes_to_one_shot_completion(self):
        text = SUBSCRIBER_SYNC.read_text(encoding="utf-8")
        self.assertIn("workflow_run:", text)
        self.assertIn("Daily Intelligence & Content Pipeline [ONE-SHOT]", text)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", text)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", text)

    def test_fix_does_not_resume_scheduled_daily_or_public_note_release(self):
        text = CHATOPS.read_text(encoding="utf-8")
        self.assertNotIn("schedule:", text)
        self.assertNotIn("note-create-draft.yml", text)
        self.assertNotIn("playwright", text.lower())
        self.assertIn("Daily schedule changed: `false`", text)
        self.assertIn("public note release performed: `false`", text)


if __name__ == "__main__":
    unittest.main()
