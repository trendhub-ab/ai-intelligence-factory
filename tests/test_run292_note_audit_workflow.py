from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "note-private-draft-audit.yml"


class Run292NoteAuditWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_live_audit_uses_renderer_faithful_run292_entrypoint(self) -> None:
        self.assertIn("xvfb-run -a python run292_note_rendered_body_audit.py", self.source)
        self.assertIn("tests.test_run292_note_rendered_body_audit", self.source)
        self.assertIn("tests.test_run293_private_draft_guard_diagnostics", self.source)
        self.assertIn("NOTE_AUDIT_PREPARE_ONLY: 'false'", self.source)

    def test_run293_diagnostic_contract_runs_before_live_browser_audit(self) -> None:
        live = self.source.split("  audit-private-draft:", 1)[1].split("\n  stop-cloud-vm:", 1)[0]
        test_pos = live.find("python -m unittest tests.test_run293_private_draft_guard_diagnostics -v")
        audit_pos = live.find("xvfb-run -a python run292_note_rendered_body_audit.py")
        self.assertGreaterEqual(test_pos, 0)
        self.assertGreater(audit_pos, test_pos)
        self.assertIn("Run291/292/293 read-only regression tests", live)

    def test_safe_summary_runs_even_when_live_audit_fails_closed(self) -> None:
        marker = "- name: Summarize non-content audit metrics only"
        section = self.source.split(marker, 1)[1].split("\n  stop-cloud-vm:", 1)[0]
        self.assertIn("if: ${{ always() }}", section)
        self.assertIn("diagnostic_code", section)
        self.assertIn("legacy_expected_visible_chars", section)
        self.assertIn("common_prefix_ratio", section)
        self.assertIn("Run293 private note draft read-only audit", section)
        self.assertIn("unpublished content / draft URL exposed: `false`", section)

    def test_vm_stop_remains_mandatory_after_successful_start_even_on_audit_failure(self) -> None:
        stop = self.source.split("\n  stop-cloud-vm:", 1)[1]
        self.assertIn("if: ${{ always() && needs.start-cloud-vm.result == 'success' }}", stop)
        self.assertIn("gcloud compute instances stop", stop)

    def test_workflow_has_no_draft_creation_public_release_or_screenshot_artifact_surface(self) -> None:
        for forbidden in (
            "CREATE_NOTE_DRAFT",
            "note-create-draft.yml",
            "公開する",
            "publish_note",
            "page.screenshot",
            "actions/upload-artifact",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.source)


if __name__ == "__main__":
    unittest.main()
