"""P1.5 live VM audit bridge: offline-only safety checks (no cloud or secrets)."""
from __future__ import annotations

from pathlib import Path
import unittest

from v1_retirement_contract_guard import (
    P15_LEDGER_AUDIT_BRIDGE, P15_LEDGER_AUDIT_JOBS,
    V04_NOTE_BRIDGE, _jobs,
)

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / ".github" / "workflows" / P15_LEDGER_AUDIT_BRIDGE
V04 = ROOT / ".github" / "workflows" / V04_NOTE_BRIDGE
PINNED_NEXT = "bbf7b49cc4eae1975d3dc838d560c12ccccc3a61"


class P15VmAuditBridgeTests(unittest.TestCase):
    def setUp(self):
        self.audit = AUDIT.read_text("utf-8")
        self.v04 = V04.read_text("utf-8")

    def test_only_five_scoped_jobs(self):
        names = [name for name, _ in _jobs(self.audit, AUDIT.name)]
        self.assertEqual(names, P15_LEDGER_AUDIT_JOBS)
        self.assertEqual(self.audit.count("workflow_dispatch:"), 1)
        self.assertNotIn("issue_comment:", self.audit)
        self.assertNotIn("schedule:", self.audit)
        self.assertNotIn("push:", self.audit)

    def test_owner_only_main_first_attempt_and_exact_confirm(self):
        preflight = dict(_jobs(self.audit, AUDIT.name))["preflight"]
        expected = (
            "github.repository == 'trendhub-ab/ai-intelligence-factory'",
            "github.ref == 'refs/heads/main'",
            "github.actor == 'trendhub-ab'",
            "github.event_name == 'workflow_dispatch'",
            "github.run_attempt == 1",
            "inputs.confirm == 'AUDIT_P15_PERSISTENT_NOTE_LEDGERS'",
        )
        for token in expected:
            with self.subTest(token=token):
                self.assertIn(token, "\n".join(preflight))
        self.assertEqual(self.audit.count("      confirm:"), 1)
        self.assertNotIn("      operation:", self.audit)

    def test_same_concurrency_lock_as_existing_v04(self):
        self.assertIn("group: note-draft-create-v2", self.audit)
        self.assertIn("group: note-draft-create-v2", self.v04)
        self.assertIn("cancel-in-progress: false", self.audit)

    def test_pinned_next_and_no_implicit_secret_transfer(self):
        self.assertEqual(self.audit.count("ref: " + PINNED_NEXT), 2)
        self.assertEqual(self.audit.count("persist-credentials: false"), 2)
        self.assertIn("repository: trendhub-ab/ai-intelligence-factory-next", self.audit)
        self.assertIn("test_p15_local_ledger_readonly_audit.py", self.audit)
        self.assertIn("p15_local_ledger_readonly_audit.py --ledger-dir", self.audit)
        for token in (
            "secrets.NOTION_API_KEY", "NOTE_STORAGE_STATE_B64",
            "AIIF_NEXT_GEMINI_API_KEY", "gemini", "run_v04_note_single_draft_bridge.py",
            "production_pipeline.py", "publish_note", "note-create-draft",
            "actions/upload-artifact", "pip install playwright", "ssh ",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, self.audit)

    def test_fails_closed_when_vm_busy_and_stops_only_own_start(self):
        self.assertIn("P15_BLOCKED_CONCURRENT_V04", self.audit)
        self.assertIn('if [ "$state" != "TERMINATED" ]; then', self.audit)
        self.assertIn("P15_VM_NOT_TERMINATED_NO_OWNERSHIP", self.audit)
        self.assertIn('needs.start-note-vm.result == \'success\'', self.audit)
        self.assertIn("gcloud compute instances stop", self.audit)
        self.assertIn("always()", self.audit)
        self.assertIn("runs-on: [self-hosted, linux, x64, aiif-note-cloud]", self.audit)
        self.assertIn("GCP_WORKLOAD_IDENTITY_PROVIDER", self.audit)
        self.assertNotIn("working-directory: /home", self.audit)

    def test_untrusted_workflow_failure_does_not_grant_authority(self):
        self.assertNotIn("contents: write", self.audit)
        self.assertNotIn("actions: write", self.audit)
        self.assertNotIn("id-token: write\n    env:\n      PYTHONDONTWRITEBYTECODE", self.audit)
        self.assertNotIn("notion_create_authorized: true", self.audit)
        self.assertNotIn("note_write_authorized: true", self.audit)
        self.assertNotIn("public_release_authorized: true", self.audit)


if __name__ == "__main__":
    unittest.main()
