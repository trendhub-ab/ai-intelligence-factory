from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run311_note_profile_update as run311

ROOT = Path(__file__).resolve().parents[1]


class Run311NoteProfileUpdateTests(unittest.TestCase):
    def test_profile_target_and_copy_are_exact(self) -> None:
        self.assertEqual(run311.PUBLIC_PROFILE_URL, "https://note.com/trendhub_biz")
        self.assertEqual(run311.CONFIRM_TOKEN, "UPDATE_NOTE_PROFILE_TRENDHUB_BIZ")
        self.assertIn("Product Hunt", run311.LEGACY_PROFILE)
        self.assertNotIn("Product Hunt", run311.CURRENT_PROFILE)
        self.assertIn("Decision Brief", run311.CURRENT_PROFILE)
        self.assertIn("AI意思決定DB", run311.CURRENT_PROFILE)

    def test_updater_changes_only_profile_field_and_exact_save_control(self) -> None:
        source = inspect.getsource(run311.update_profile)
        self.assertIn("_settings_control(page).click()", source)
        self.assertIn("_set_profile_field(page, field, CURRENT_PROFILE)", source)
        self.assertIn("_save_control(page).click()", source)
        self.assertIn("_verify_public(page)", source)
        for forbidden in ("公開に進む", "更新する", "_set_title", "_paste_manuscript", "eyecatch"):
            self.assertNotIn(forbidden, source)

    def test_profile_field_requires_legacy_or_current_marker(self) -> None:
        source = inspect.getsource(run311._find_profile_field)
        self.assertIn("Product Hunt", source)
        self.assertIn("Decision Brief", source)
        self.assertIn('textarea:visible', source)
        self.assertIn('[contenteditable="true"]:visible', source)

    def test_public_verification_removes_product_hunt(self) -> None:
        source = inspect.getsource(run311._verify_public)
        self.assertIn("CURRENT_PROFILE", source)
        self.assertIn("Product Hunt", source)
        self.assertIn("PUBLIC_PROFILE_URL", source)

    def test_workflow_is_manual_exact_and_zero_model(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "note-profile-update.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("UPDATE_NOTE_PROFILE_TRENDHUB_BIZ", workflow)
        self.assertIn("run311_note_profile_update.py", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertIn("zero Gemini calls", workflow)


if __name__ == "__main__":
    unittest.main()
