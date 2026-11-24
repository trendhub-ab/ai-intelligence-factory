"""Prove the single new Next OnePath private-note workflow retains old V1 retirement.

Static, zero-provider and no-VM. No live operations, credentials or model calls.
"""
from __future__ import annotations

from pathlib import Path
import unittest

import v1_retirement_contract_guard as guard

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/onepath-next-reviewed-note-draft.yml"


class OnePathReviewedNoteBridgeTests(unittest.TestCase):
    def test_v1_retired_and_four_exact_exceptions_only(self):
        result = guard.audit_v1_retirement(ROOT)
        self.assertEqual(result["retirement"], "PASS")
        self.assertEqual(result["operational_workflows_disabled"], 81)
        self.assertEqual(result["owner_onepath_signed_private_note_exception"], 1)
        self.assertEqual(result["owner_p15_vm_readonly_audit_exception"], 1)

    def test_owner_only_manual_gateway_with_runner_lock_and_cleanup(self):
        text = WORKFLOW.read_text("utf-8")
        for required in (
            "workflow_dispatch:", "github.run_attempt == 1",
            "github.actor == 'trendhub-ab'", "github.ref == 'refs/heads/main'",
            "RUN_ONEPATH_REVIEWED_PRIVATE_NOTE_DRAFT",
            "group: note-draft-create-v2", "cancel-in-progress: false",
            "TERMINATED", "runs-on: [self-hosted, linux, x64, aiif-note-cloud]",
            "ONEPATH_VM_NOT_TERMINATED_NO_OWNERSHIP",
            "stop-note-vm:", "always()", "gcloud compute instances stop",
            "shred -u", "rmdir", "persist-credentials: false",
        ):
            self.assertIn(required, text)
        for forbidden in (
            "schedule:", "push:", "issue_comment:", "workflow_call:",
            "actions/upload-artifact", "actions/download-artifact",
            "publish_note", "note-publication", "AIIF_NEXT_GEMINI_API_KEY",
            "repository_dispatch:", "if: ${{ true }}",
        ):
            self.assertNotIn(forbidden, text)

    def test_exact_private_packet_content_and_separate_signing_key(self):
        text = WORKFLOW.read_text("utf-8")
        self.assertIn("validate_sealed_blob", text)
        self.assertIn("ONEPATH_ENCRYPTED_PACKET_METADATA_VERIFIED", text)
        self.assertIn("secrets.GH_PAT", text)
        self.assertIn("vars.AIIF_ONEPATH_OWNER_POLICY_PUBLIC_KEY_B64", text)
        self.assertIn("secrets.AIIF_ONEPATH_RECIPIENT_PRIVATE_KEY_B64", text)
        self.assertNotIn("secrets.AIIF_NEXT_OWNER_REVIEW_KEY_B64", text)
        self.assertNotIn("AIIF_NEXT_OWNER_REVIEW_KEY_ID", text)
        self.assertIn("secrets.NOTION_API_KEY", text)
        self.assertIn("onepath_packet_exchange.py --mode fetch", text)
        self.assertIn("--mode deliver", text)
        self.assertIn('test "$(git -C next-p1 rev-parse HEAD)" = "$NEXT_MAIN_SHA"', text)
        self.assertNotIn("body: ${{", text)
        self.assertNotIn("manuscript: ${{", text)

    def test_vm_uses_isolated_python_for_install_decrypt_and_delivery(self):
        workflow = WORKFLOW.read_text("utf-8")
        job = workflow.split("  deliver-private-note:", 1)[1].split("  stop-note-vm:", 1)[0]
        for required in (
            "uses: actions/setup-python@v6", "python-version: '3.11'",
            'python -m venv "$venv_dir"',
            '"$venv_dir/bin/python" -m pip install -r legacy/requirements.txt',
            '"$venv_dir/bin/python" -B next-p1/scripts/onepath_packet_exchange.py --mode fetch',
            'xvfb-run -a "$venv_dir/bin/python" -B next-p1/scripts/onepath_reviewed_delivery.py',
            'venv_dir="$RUNNER_TEMP/onepath-venv-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"',
            'if: ${{ always() }}', 'rm -rf -- "$venv_dir"',
        ):
            self.assertIn(required, job)
        self.assertLess(job.index("actions/setup-python@v6"), job.index("python -m venv"))
        self.assertLess(job.index("python -m venv"), job.index("onepath_packet_exchange.py --mode fetch"))
        for forbidden in ("--break-system-packages", "sudo ", "python3 -m pip install"):
            self.assertNotIn(forbidden, job)

    def test_no_v1_reactivation(self):
        src = WORKFLOW.read_text("utf-8")
        self.assertEqual(src.count("workflow_dispatch:"), 1)
        for piece in ('"$venv_dir/bin/python" -m pip install -r legacy/requirements.txt',
                      'NOTE_CHROME_HEADLESS: "false"',
                      "AIIF_ONEPATH_OWNER_GO"):
            self.assertIn(piece, src)
        for forbidden in ("notion_writes", "Gemini API key"):
            self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
