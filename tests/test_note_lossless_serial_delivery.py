from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READY_SYNC = ROOT / ".github" / "workflows" / "note-ready-sync.yml"
CREATE_DRAFT = ROOT / ".github" / "workflows" / "note-create-draft.yml"


class NoteLosslessSerialDeliveryTests(unittest.TestCase):
    def test_ready_sync_waits_for_exact_private_draft_instead_of_fire_and_forget_dispatch(self) -> None:
        ready = READY_SYNC.read_text(encoding="utf-8")

        self.assertIn("draft_eligible: ${{ steps.fanout.outputs.eligible }}", ready)
        self.assertIn("selected_sync_id: ${{ steps.fanout.outputs.selected_sync_id }}", ready)
        self.assertIn("create-private-draft:", ready)
        self.assertIn("needs: sync-note-ready", ready)
        self.assertIn("uses: ./.github/workflows/note-create-draft.yml", ready)
        self.assertIn("secrets: inherit", ready)
        self.assertNotIn("gh workflow run note-create-draft.yml", ready)

    def test_called_draft_is_pinned_to_the_exact_ready_sync_id(self) -> None:
        ready = READY_SYNC.read_text(encoding="utf-8")

        self.assertIn("confirm: CREATE_NOTE_DRAFT", ready)
        self.assertIn("sync_id: ${{ needs.sync-note-ready.outputs.selected_sync_id }}", ready)
        self.assertIn("prepare_only: false", ready)
        self.assertIn("inputs.create_private_draft == true", ready)
        self.assertIn("needs.sync-note-ready.outputs.draft_eligible == 'true'", ready)

    def test_create_draft_supports_reusable_call_without_losing_manual_dispatch(self) -> None:
        draft = CREATE_DRAFT.read_text(encoding="utf-8")

        self.assertIn("workflow_call:", draft)
        self.assertIn("workflow_dispatch:", draft)
        self.assertGreaterEqual(draft.count("confirm:"), 2)
        self.assertGreaterEqual(draft.count("sync_id:"), 2)
        self.assertGreaterEqual(draft.count("prepare_only:"), 2)

    def test_global_single_writer_concurrency_remains_fail_safe(self) -> None:
        draft = CREATE_DRAFT.read_text(encoding="utf-8")

        self.assertIn("group: note-draft-create", draft)
        self.assertIn("cancel-in-progress: false", draft)


if __name__ == "__main__":
    unittest.main(verbosity=2)
