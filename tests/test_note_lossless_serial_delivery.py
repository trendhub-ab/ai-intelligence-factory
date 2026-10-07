from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READY_SYNC = ROOT / ".github" / "workflows" / "note-ready-sync.yml"
CREATE_DRAFT = ROOT / ".github" / "workflows" / "note-create-draft.yml"
DAILY = ROOT / ".github" / "workflows" / "daily-one-shot.yml"


class NoteLosslessSerialDeliveryTests(unittest.TestCase):
    def test_daily_contract_is_not_reimplemented_in_note_delivery_repair(self) -> None:
        daily = DAILY.read_text(encoding="utf-8")

        self.assertIn('for target_source_url in "${target_source_urls[@]}"; do', daily)
        self.assertIn('gh workflow run note-ready-sync.yml --ref main', daily)
        self.assertNotIn('target_source_urls_b64:', daily)

    def test_ready_sync_keeps_single_writer_lock_but_scopes_it_to_each_exact_target(self) -> None:
        ready = READY_SYNC.read_text(encoding="utf-8")

        self.assertIn('TARGET_SYNC_ID: ${{ inputs.target_sync_id || steps.sync.outputs.resolved_sync_id }}', ready)
        self.assertIn('-f sync_id="$SELECTED_SYNC_ID"', ready)
        self.assertIn(
            'group: note-ready-article-sync-${{ inputs.target_sync_id || inputs.target_source_url || github.run_id }}',
            ready,
        )
        self.assertIn('cancel-in-progress: false', ready)
        self.assertNotIn('group: note-ready-article-sync\n', ready)

    def test_create_draft_does_not_use_fixed_workflow_concurrency_that_can_replace_pending_runs(self) -> None:
        draft = CREATE_DRAFT.read_text(encoding="utf-8")

        self.assertNotIn('group: note-draft-create', draft)
        self.assertNotIn('cancel-in-progress:', draft)

    def test_vm_start_waits_for_exactly_one_online_note_runner_before_browser_delivery(self) -> None:
        draft = CREATE_DRAFT.read_text(encoding="utf-8")

        self.assertIn('Wait for exactly one registered note runner to become online', draft)
        self.assertIn('actions/runners?per_page=100', draft)
        self.assertIn('status == "online"', draft)
        self.assertIn('aiif-note-cloud', draft)
        self.assertIn('count" -eq 1', draft)

    def test_vm_stop_is_deferred_while_another_note_draft_run_is_active(self) -> None:
        draft = CREATE_DRAFT.read_text(encoding="utf-8")

        self.assertIn('Defer VM stop while another note draft run is active', draft)
        self.assertIn('gh run list --workflow note-create-draft.yml', draft)
        self.assertIn('queued', draft)
        self.assertIn('in_progress', draft)
        self.assertIn('GITHUB_RUN_ID', draft)
        self.assertIn('Another note draft run is active; keeping the persistent VM online.', draft)

    def test_stop_cleanup_runs_after_any_started_vm_path_not_only_successful_start_job(self) -> None:
        draft = CREATE_DRAFT.read_text(encoding="utf-8")

        self.assertIn("needs.start-cloud-vm.result != 'skipped'", draft)
        self.assertNotIn("needs.start-cloud-vm.result == 'success'", draft)


if __name__ == "__main__":
    unittest.main(verbosity=2)
