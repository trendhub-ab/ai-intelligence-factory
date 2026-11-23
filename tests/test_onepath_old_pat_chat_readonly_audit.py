"""Static fail-closed check for OnePath OLD PAT metadata audit.

Only owner-authenticated Issue triggers. Zero secrets/config modifications.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / ".github/workflows/onepath-old-pat-chat-readonly-audit.yml"


class OnePathOldPatReadOnlyAuditContractTests(unittest.TestCase):
    def test_owner_issue_exact_identity_and_metadata_only(self):
        content = PATH.read_text(encoding="utf-8")
        for required in (
            "on:\n  issues:\n    types: [opened]",
            "github.actor == 'trendhub-ab'",
            "github.event.issue.user.login == 'trendhub-ab'",
            "github.event.action == 'opened'",
            "github.event.issue.title == 'AIIF OLD: READ-ONLY ONEPATH EXISTING PAT AUDIT'",
            "github.event.issue.body == 'VERIFY_OLD_GH_PAT_METADATA_ONLY_NO_WRITES'",
            "github.event.repository.private == false",
            "github.run_attempt == 1",
            "permissions:\n  contents: read",
            "OLD_GH_PAT_PRESENT:",
            "OLD_PAT_NEXT_VARIABLES",
            "OLD_PAT_NEXT_SECRETS",
            "OLD_PAT_OLD_SECRETS",
            "ONEPATH_OLD_AUDIT_READ_SUCCESS_IS_NOT_WRITE_PERMISSION",
            'gh api "$path" --silent >/dev/null 2>&1',
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_v1_retirement_guard_whitelists_exact_metadata_only_audit(self):
        source = (ROOT / "v1_retirement_contract_guard.py").read_text(
            encoding="utf-8")
        for required in (
            'assert len(files) == 90',
            'ONEPATH_OLD_PAT_AUDIT_BRIDGE = "onepath-old-pat-chat-readonly-audit.yml"',
            'ONEPATH_OLD_PAT_AUDIT_JOBS = ["audit-old-owner-pat"]',
            'assert disabled_count == 81',
            'assert onepath_old_pat_audit_count == 1',
            '"ONEPATH_OLD_PAT_AUDIT_FORBIDDEN:"',
            '"gh api --method"',
            '"ONEPATH_OLD_PAT_AUDIT_REQUIRED_FIELD_MISSING:"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)

    def test_no_write_api_or_vm_model_or_note(self):
        content = PATH.read_text(encoding="utf-8")
        for forbidden in (
            "workflow_dispatch:",
            "schedule:",
            "pull_request_target:",
            "id-token: write",
            "contents: write",
            "actions: write",
            "secrets: write",
            "gh secret set",
            "gh variable set",
            "gh api -X POST",
            "gh api --method POST",
            "gh api -X PUT",
            "gcloud ",
            "actions/checkout",
            "google-github-actions/auth",
            "NOTION_API_KEY: ${{ secrets.NOTION_API_KEY }}",
            "NOTE_STORAGE_STATE_B64: ${{ secrets.NOTE_STORAGE_STATE_B64 }}",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, content)


if __name__ == "__main__":
    unittest.main()
