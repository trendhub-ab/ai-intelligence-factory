from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTE_DRAFT = ROOT / ".github" / "workflows" / "note-create-draft.yml"
CONTROL = ROOT / ".github" / "workflows" / "note-draft-control.yml"


class NoteDraftOrphanRecoveryTests(unittest.TestCase):
    def test_current_lossless_queue_contract_is_preserved(self) -> None:
        text = NOTE_DRAFT.read_text(encoding="utf-8")
        self.assertIn("group: note-draft-create", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("queue: max", text)

    def test_recovery_control_is_owner_only_and_fail_closed_for_one_stale_run(self) -> None:
        text = CONTROL.read_text(encoding="utf-8")
        self.assertIn("issue_comment:", text)
        self.assertIn("github.event.issue.number == 71", text)
        self.assertIn("github.event.comment.user.login == 'trendhub-ab'", text)
        self.assertIn("github.actor == 'trendhub-ab'", text)
        self.assertIn("startsWith(github.event.comment.body, '/aiif note cancel_stale_pending ')", text)
        self.assertIn("[0-9]{8,20}", text)
        self.assertIn("GH_TOKEN: ${{ secrets.GH_PAT }}", text)
        self.assertIn(".github/workflows/note-create-draft.yml", text)
        self.assertIn("status", text)
        self.assertIn("pending", text)
        self.assertIn("jobs", text)
        self.assertIn("30", text)
        self.assertIn("/actions/runs/$run_id/cancel", text)
        self.assertNotIn("actions/workflows/note-create-draft.yml/dispatches", text)
        self.assertNotIn("daily-one-shot.yml", text)
        self.assertNotIn("production_pipeline.py", text)
        self.assertNotIn("GEMINI_API_KEY", text)
        self.assertNotIn("GOOGLE_API_KEY", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
