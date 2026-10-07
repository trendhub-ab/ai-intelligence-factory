from __future__ import annotations

import unittest
import re
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

    def test_cloud_vm_uses_oidc_and_is_stopped_after_actual_start(self) -> None:
        source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
        self.assertIn("id-token: write", source)
        self.assertIn("google-github-actions/auth@v3", source)
        self.assertIn("google-github-actions/setup-gcloud@v3", source)
        self.assertIn("gcloud compute instances start", source)
        self.assertIn("gcloud compute instances stop", source)
        self.assertIn(
            "if: ${{ inputs.prepare_only == false && needs.preflight.outputs.should_start_vm == 'true' }}",
            source,
        )
        # Evaluate the cleanup decision across success/failure and no-start paths.
        # A VM can be running even if the subsequent runner-readiness step fails.
        cleanup = source.split("  stop-cloud-vm:", 1)[1]
        expression = re.search(r"if: \$\{\{ (.*?) \}\}", cleanup)[1]
        expression = (expression.replace("always()", "True")
                      .replace("inputs.prepare_only", "prepare_only")
                      .replace("needs.preflight.outputs.should_start_vm", "should_start")
                      .replace("needs.start-cloud-vm.result", "start_result")
                      .replace("false", "False").replace("&&", "and"))
        for prepare, candidate, start_result, expected in [
            (False, 'true', 'success', True),
            (False, 'true', 'failure', True),
            (False, 'true', 'cancelled', True),
            (False, 'true', 'skipped', False),
            (True, 'true', 'skipped', False),
            (False, 'false', 'skipped', False),
        ]:
            with self.subTest(prepare=prepare, candidate=candidate, start=start_result):
                actual = eval(expression, {"__builtins__": {}}, {
                    "prepare_only": prepare, "should_start": candidate,
                    "start_result": start_result,
                })
                self.assertEqual(expected, actual)
        self.assertNotIn("if: ${{ always() && inputs.prepare_only == false }}", source)

    def test_prepare_only_and_empty_queue_do_not_start_cloud_vm(self) -> None:
        source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
        preflight_start = source.index("  preflight:")
        vm_start = source.index("  start-cloud-vm:")
        preflight = source[preflight_start:vm_start]

        self.assertIn("run199_note_vm_preflight.py", preflight)
        self.assertIn("should_start_vm: ${{ steps.decision.outputs.should_start_vm }}", preflight)
        self.assertIn("PREPARE_ONLY: ${{ inputs.prepare_only }}", preflight)
        self.assertIn("GITHUB_EVENT_PATH", preflight)
        self.assertNotIn("selected_sync_id: ${{ steps.decision.outputs.selected_sync_id }}", preflight)
        self.assertNotIn("needs.preflight.outputs.selected_sync_id", source)
        self.assertIn(
            "if: ${{ inputs.prepare_only == false && needs.preflight.outputs.should_start_vm == 'true' }}",
            source,
        )
        self.assertIn("Revalidate and pin exact candidate on private worker", source)
        self.assertIn("NOTE_PREPARE_ONLY: 'false'", source)

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
