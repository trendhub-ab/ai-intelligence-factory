from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "note-private-draft-audit.yml"
MODULE = ROOT / "run291_note_private_draft_audit.py"


class Run291WorkflowContractTests(unittest.TestCase):
    def test_workflow_is_manual_read_only_and_has_no_artifact_or_model_surface(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", source)
        self.assertNotIn("schedule:", source)
        self.assertNotIn("push:\n", source)
        self.assertIn("AUDIT_NOTE_DRAFT", source)
        self.assertIn("run291_note_private_draft_audit.py", source)
        self.assertIn("[self-hosted, linux, x64, aiif-note-cloud]", source)
        self.assertIn("Start persistent note Chrome VM", source)
        self.assertIn("Stop persistent note Chrome VM", source)
        for forbidden in (
            "GEMINI_API_KEY",
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID",
            "actions/upload-artifact",
            "CREATE_NOTE_DRAFT",
            "run194_note_persistent_cloud.py",
            "note-create-draft.yml",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_module_has_no_success_screenshot_or_note_mutation_calls(self) -> None:
        source = MODULE.read_text(encoding="utf-8")
        for forbidden in (
            "page.screenshot(",
            "_mark_draft_created(",
            "_upload_header_image(",
            "_paste_manuscript(",
            "_save_draft_and_verify(",
            ".click(",
            ".fill(",
            "keyboard.press",
            "keyboard.insert_text",
            "requests.post(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_audit_result_contract_never_names_private_content_fields(self) -> None:
        source = MODULE.read_text(encoding="utf-8")
        # These values are used internally for verification, but the final result assembly must
        # stay metric-only and must never expose an edit URL.
        result_section = source[source.index("def run(*") : source.index("def main()")]
        self.assertNotIn('result["draft_url"]', result_section)
        self.assertNotIn('result["title"]', result_section)
        self.assertNotIn('result["manuscript"]', result_section)


if __name__ == "__main__":
    unittest.main()
