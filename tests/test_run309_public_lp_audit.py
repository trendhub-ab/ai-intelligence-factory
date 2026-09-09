from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run309_public_lp_editor_audit as run309


ROOT = Path(__file__).resolve().parents[1]


class Run309PublicLpAuditTests(unittest.TestCase):
    def test_target_is_exact_authorized_fixed_note(self) -> None:
        self.assertEqual(run309.TARGET_NOTE_ID, "ned673e381ef8")
        self.assertEqual(
            run309.TARGET_PUBLIC_URL,
            "https://note.com/trendhub_biz/n/ned673e381ef8",
        )
        self.assertEqual(
            run309.TARGET_EDITOR_URL,
            "https://editor.note.com/notes/ned673e381ef8/edit/",
        )

    def test_audit_source_contains_no_mutation_calls(self) -> None:
        source = inspect.getsource(run309.audit)
        forbidden = (
            "_set_title(",
            "_paste_manuscript(",
            "_save_draft_and_verify(",
            ".click(",
            ".press(",
            ".fill(",
            "evaluate(\"el => el.innerHTML =",
        )
        for token in forbidden:
            self.assertNotIn(token, source)

    def test_workflow_is_exact_confirmation_read_only(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "note-public-lp-audit.yml").read_text(encoding="utf-8")
        self.assertIn("AUDIT_PUBLIC_LP", workflow)
        self.assertIn("run309_public_lp_editor_audit.py", workflow)
        self.assertNotIn("UPDATE_PUBLIC_LP", workflow)
        self.assertNotIn("public release performed: `true`", workflow)


if __name__ == "__main__":
    unittest.main()
