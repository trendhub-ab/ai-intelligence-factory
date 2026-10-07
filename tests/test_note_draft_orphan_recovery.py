from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTE_DRAFT = ROOT / ".github" / "workflows" / "note-create-draft.yml"
CONTROL = ROOT / ".github" / "workflows" / "note-draft-control.yml"


class NoteDraftOrphanRecoveryTests(unittest.TestCase):
    def test_note_draft_uses_new_queue_generation_without_dropping_waiters(self) -> None:
        text = NOTE_DRAFT.read_text(encoding="utf-8")
        self.assertIn("group: note-draft-create-v2", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("queue: max", text)
        self.assertNotIn("group: note-draft-create\n", text)

    def test_exact_control_is_owner_only_and_cleans_only_legacy_pending_runs(self) -> None:
        text = CONTROL.read_text(encoding="utf-8")
        self.assertIn("issue_comment:", text)
        self.assertIn("github.event.issue.number == 71", text)
        self.assertIn("github.event.comment.user.login == 'trendhub-ab'", text)
        self.assertIn("github.actor == 'trendhub-ab'", text)
        self.assertIn("startsWith(github.event.comment.body, '/aiif note draft ')", text)
        self.assertIn("[0-9a-fA-F]{32}", text)
        self.assertIn("GH_TOKEN: ${{ secrets.GH_PAT }}", text)
        self.assertIn("actions/workflows/note-create-draft.yml/runs?status=pending", text)
        self.assertIn("head_sha", text)
        self.assertIn("GITHUB_SHA", text)
        self.assertIn("/actions/runs/$run_id/cancel", text)
        self.assertIn("actions/workflows/note-create-draft.yml/dispatches", text)
        self.assertIn("CREATE_NOTE_DRAFT", text)
        self.assertIn("sync_id", text)
        self.assertNotIn("daily-one-shot.yml", text)
        self.assertNotIn("production_pipeline.py", text)
        self.assertNotIn("GEMINI_API_KEY", text)
        self.assertNotIn("GOOGLE_API_KEY", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
