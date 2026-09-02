from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Run190CloudWorkflowTests(unittest.TestCase):
    def test_actual_draft_runs_on_persistent_self_hosted_vm(self) -> None:
        source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
        self.assertIn("runs-on: [self-hosted, linux, x64, aiif-note-cloud]", source)
        self.assertIn("xvfb-run -a python run194_note_persistent_cloud.py", source)
        self.assertNotIn("xvfb-run -a python run190_note_persistent_cloud.py", source)
        self.assertIn("NOTE_CHROME_CHANNEL: 'chrome'", source)
        self.assertNotIn("python -m playwright install --with-deps chromium", source)

    def test_cloud_vm_uses_oidc_and_is_stopped_after_job(self) -> None:
        source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
        self.assertIn("id-token: write", source)
        self.assertIn("google-github-actions/auth@v3", source)
        self.assertIn("google-github-actions/setup-gcloud@v3", source)
        self.assertIn("gcloud compute instances start", source)
        self.assertIn("gcloud compute instances stop", source)
        self.assertIn("if: ${{ always() && inputs.prepare_only == false }}", source)

    def test_prepare_only_does_not_start_cloud_vm(self) -> None:
        source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
        self.assertIn("prepare-only:", source)
        self.assertIn("if: ${{ inputs.prepare_only == true }}", source)
        self.assertIn("NOTE_PREPARE_ONLY: 'true'", source)
        self.assertIn("python run194_note_current_contract.py", source)

    def test_bootstrap_has_cost_failsafe_and_persistent_profile(self) -> None:
        controller = (ROOT / "infra/gcp/run190_setup_controller.sh").read_text(encoding="utf-8")
        runner = (ROOT / "infra/gcp/run190_bootstrap_runner.sh").read_text(encoding="utf-8")
        self.assertIn("shutdown -h +35", controller)
        self.assertIn("google-chrome-stable", runner)
        self.assertIn("chrome-profile", runner)
        self.assertIn("--labels", runner)
        self.assertIn("svc.sh start", runner)


if __name__ == "__main__":
    unittest.main()
