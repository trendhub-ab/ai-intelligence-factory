from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Run190CloudWorkflowTests(unittest.TestCase):
    def test_actual_draft_runs_on_ephemeral_github_hosted_worker(self) -> None:
        source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
        self.assertIn("runs-on: ubuntu-latest", source)
        self.assertIn("python -m playwright install --with-deps chromium", source)
        self.assertIn("python run194_note_hosted.py", source)
        self.assertIn("NOTE_CHROME_HEADLESS: 'true'", source)
        self.assertNotIn("runs-on: [self-hosted", source)
        self.assertNotIn("xvfb-run", source)
        self.assertNotIn("run194_note_persistent_cloud.py", source)

    def test_hosted_delivery_uses_oidc_for_private_gcs_ledger_without_gce_control(self) -> None:
        source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
        self.assertIn("id-token: write", source)
        self.assertIn("google-github-actions/auth@v3", source)
        self.assertIn("NOTE_DELIVERY_LEDGER_BACKEND: 'gcs'", source)
        self.assertIn("GCP_PROJECT_ID: ${{ vars.GCP_PROJECT_ID }}", source)
        self.assertIn('bucket="${GCP_PROJECT_ID}-aiif-note-ledger-v1"', source)
        self.assertIn('echo "NOTE_DELIVERY_LEDGER_BUCKET=$bucket" >> "$GITHUB_ENV"', source)
        self.assertNotIn("vars.GCP_NOTE_LEDGER_BUCKET", source)
        self.assertNotIn("google-github-actions/setup-gcloud@v3", source)
        self.assertNotIn("gcloud compute instances start", source)
        self.assertNotIn("gcloud compute instances stop", source)
        self.assertNotIn("start-cloud-vm", source)
        self.assertNotIn("stop-cloud-vm", source)

    def test_prepare_only_and_empty_queue_do_not_enter_browser_delivery(self) -> None:
        source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
        preflight_start = source.index("  preflight:")
        create_start = source.index("  create-draft:")
        preflight = source[preflight_start:create_start]
        create = source[create_start:]

        self.assertIn("run199_note_vm_preflight.py", preflight)
        self.assertIn("should_continue: ${{ steps.decision.outputs.should_continue }}", preflight)
        self.assertIn("PREPARE_ONLY: ${{ inputs.prepare_only }}", preflight)
        self.assertIn("GITHUB_EVENT_PATH", preflight)
        self.assertNotIn("selected_sync_id: ${{ steps.decision.outputs.selected_sync_id }}", preflight)
        self.assertNotIn("needs.preflight.outputs.selected_sync_id", source)
        self.assertIn(
            "if: ${{ inputs.prepare_only == false && needs.preflight.outputs.should_continue == 'true' }}",
            create,
        )
        self.assertIn("Revalidate and pin exact candidate on hosted worker", create)
        self.assertIn("NOTE_PREPARE_ONLY: 'false'", create)

    def test_legacy_bootstrap_files_remain_reference_only(self) -> None:
        controller = (ROOT / "infra/gcp/run190_setup_controller.sh").read_text(encoding="utf-8")
        runner = (ROOT / "infra/gcp/run190_bootstrap_runner.sh").read_text(encoding="utf-8")
        self.assertIn("shutdown -h +35", controller)
        self.assertIn("google-chrome-stable", runner)
        production = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
        self.assertNotIn("infra/gcp/run190_setup_controller.sh", production)
        self.assertNotIn("infra/gcp/run190_bootstrap_runner.sh", production)


if __name__ == "__main__":
    unittest.main()