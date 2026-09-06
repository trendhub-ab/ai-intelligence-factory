from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHATOPS = ROOT / ".github" / "workflows" / "chatops-one-shot.yml"
ONE_SHOT = ROOT / ".github" / "workflows" / "daily-one-shot.yml"
NOTE_SYNC = ROOT / ".github" / "workflows" / "note-ready-sync.yml"
SUBSCRIBER_SYNC = ROOT / ".github" / "workflows" / "subscriber-decision-brief.yml"


class Run259ChatOpsFanoutTokenTests(unittest.TestCase):
    def test_chatops_dispatch_requires_pat_not_repository_token(self):
        text = CHATOPS.read_text(encoding="utf-8")
        self.assertIn("GH_TOKEN: ${{ secrets.GH_PAT }}", text)
        self.assertNotIn("GH_TOKEN: ${{ github.token }}", text)
        self.assertIn('if [ -z "${GH_TOKEN:-}" ]; then', text)
        self.assertIn("GH_PAT is required for ChatOps ONE-SHOT dispatch", text)

    def test_one_shot_downstream_dispatch_requires_pat_and_success(self):
        text = ONE_SHOT.read_text(encoding="utf-8")
        self.assertIn("GH_TOKEN: ${{ secrets.GH_PAT }}", text)
        self.assertIn("GH_PAT is required for authoritative ONE-SHOT downstream fan-out", text)
        self.assertIn("if: ${{ success() }}", text)
        self.assertIn("note-ready-sync.yml", text)
        self.assertIn("subscriber-decision-brief.yml", text)
        self.assertIn("cross-db-contract-guard.yml", text)

    def test_note_sync_is_dispatchable_without_passive_one_shot_subscription(self):
        text = NOTE_SYNC.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("Daily Intelligence & Content Pipeline [ONE-SHOT]", text)

    def test_subscriber_sync_keeps_inventory_trigger_without_passive_one_shot_subscription(self):
        text = SUBSCRIBER_SYNC.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("workflow_run:", text)
        self.assertIn("Subscriber Inventory Bootstrap", text)
        self.assertNotIn("Daily Intelligence & Content Pipeline [ONE-SHOT]", text)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", text)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", text)
        self.assertIn("contains(github.event.workflow_run.display_title, '[apply]')", text)

    def test_fix_does_not_resume_scheduled_daily_or_public_note_release(self):
        chatops = CHATOPS.read_text(encoding="utf-8")
        one_shot = ONE_SHOT.read_text(encoding="utf-8")
        self.assertNotIn("schedule:", chatops)
        self.assertNotIn("note-create-draft.yml", chatops)
        self.assertNotIn("playwright", chatops.lower())
        self.assertNotIn("note.com", one_shot)
        self.assertIn("Daily schedule changed: `false`", chatops)
        self.assertIn("public note release performed: `false`", chatops)


if __name__ == "__main__":
    unittest.main()
