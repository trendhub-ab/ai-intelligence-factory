"""Public-repository contract: paid member audit results must never leak by artifact or logs."""
from __future__ import annotations

from pathlib import Path
import unittest


WORKFLOW = Path(".github/workflows/member-experience-quality-audit.yml")


class PublicMemberAuditWorkflowSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_requires_explicit_manual_confirmation_with_no_automatic_triggers(self):
        self.assertIn("workflow_dispatch:", self.source)
        self.assertIn("READ_ONLY_MEMBER_EXPERIENCE", self.source)
        self.assertNotIn("  push:", self.source)
        self.assertNotIn("  schedule:", self.source)

    def test_never_publishes_per_page_paid_catalogue_artifact_or_logs(self):
        self.assertNotIn("upload-artifact", self.source)
        self.assertNotIn("artifact-upload", self.source)
        self.assertIn('mktemp "$RUNNER_TEMP/member-experience-', self.source)
        self.assertIn('mktemp "$RUNNER_TEMP/member-audit-error-', self.source)
        self.assertIn('trap \'rm -f "$REPORT" "$ERROR_LOG"\' EXIT', self.source)
        self.assertIn('> "$REPORT" 2> "$ERROR_LOG"', self.source)
        self.assertIn('json.dumps(summary, sort_keys=True)', self.source)
        self.assertNotIn('json.dumps(result, sort_keys=True)', self.source)

    def test_no_gemini_and_no_production_write_action(self):
        self.assertIn('test -z "${GEMINI_API_KEY:-}"', self.source)
        self.assertIn("python member_experience_quality_audit.py --read-only", self.source)
        self.assertNotIn("python run219_member_human_language_ui.py body", self.source)
        self.assertNotIn("force_full_body_sync: true", self.source)


if __name__ == "__main__":
    unittest.main()
