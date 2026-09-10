from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run311_note_profile_update as run311
import run330_note_profile_exact_update as run330

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "note-profile-update.yml").read_text(encoding="utf-8")
CHATOPS = (ROOT / ".github" / "workflows" / "chatops-note.yml").read_text(encoding="utf-8")


class Run330ExactProfileUpdateTests(unittest.TestCase):
    def test_exact_route_field_name_and_copy_contract(self) -> None:
        self.assertEqual(run330.CONFIRM_TOKEN, "UPDATE_NOTE_PROFILE_TRENDHUB_BIZ_RUN330_EXACT_BIOGRAPHY")
        self.assertEqual(run330.BIO_SELECTOR, 'textarea[name="editBiography"][aria-label="自己紹介"]:visible')
        self.assertEqual(run330.NICKNAME_SELECTOR, 'input[name="editNickname"][aria-label="クリエイター名"]:visible')
        self.assertEqual(run330.EXPECTED_NICKNAME, "AI Intelligence Factory")
        self.assertIn("Product Hunt", run311.LEGACY_PROFILE)
        self.assertNotIn("Product Hunt", run311.CURRENT_PROFILE)

    def test_update_uses_run329_direct_route_and_never_clicks_public_settings(self) -> None:
        source = inspect.getsource(run330.update_profile)
        href_source = inspect.getsource(run330._settings_href)
        settings_source = inspect.getsource(run330._open_settings_and_assert_account)
        self.assertIn("_settings_href(page)", source)
        self.assertIn("get_attribute(\"href\")", href_source)
        self.assertIn("run329.PROFILE_SETTINGS_URL", href_source)
        self.assertIn("page.goto(run329.PROFILE_SETTINGS_URL", settings_source)
        self.assertNotIn("_settings_control(page).click()", source)
        self.assertNotIn("_settings_control(page).click()", settings_source)

    def test_only_biography_is_filled_and_save_is_exactly_once(self) -> None:
        source = inspect.getsource(run330.update_profile)
        self.assertIn("bio.fill(run311.CURRENT_PROFILE)", source)
        self.assertIn("save.click()", source)
        self.assertIn("save_clicks += 1", source)
        self.assertIn("if save_clicks != 1", source)
        self.assertNotIn("nickname.fill", source)
        self.assertNotIn("keyboard.insert_text", source)
        for forbidden in ("公開に進む", "更新する", "eyecatch", "_paste_manuscript"):
            self.assertNotIn(forbidden, source)

    def test_all_other_settings_are_snapshotted_and_verified_unchanged(self) -> None:
        snapshot = inspect.getsource(run330._form_snapshot)
        source = inspect.getsource(run330.update_profile)
        self.assertIn("querySelectorAll('input, textarea, select')", snapshot)
        self.assertIn("editBiography", snapshot)
        self.assertIn("before_snapshot", source)
        self.assertIn("_form_snapshot(page) != before_snapshot", source)
        self.assertIn("after_fresh_snapshot != before_snapshot", source)
        self.assertIn("other_settings_unchanged", source)

    def test_public_state_is_fail_closed_and_idempotent(self) -> None:
        public_source = inspect.getsource(run330._public_state)
        source = inspect.getsource(run330.update_profile)
        self.assertIn("run311.LEGACY_PROFILE", public_source)
        self.assertIn("run311.CURRENT_PROFILE", public_source)
        self.assertIn('"Product Hunt"', public_source)
        self.assertIn('public_state == "current"', source)
        self.assertIn("already_current_verified_no_mutation", source)
        self.assertIn("updated_and_verified_exact_biography_only", source)
        self.assertIn("_verify_public_current(page)", source)

    def test_live_workflow_and_chatops_dispatch_run330_only(self) -> None:
        token = run330.CONFIRM_TOKEN
        self.assertIn("workflow_dispatch:", WORKFLOW)
        self.assertIn(token, WORKFLOW)
        self.assertIn("run330_note_profile_exact_update.py", WORKFLOW)
        self.assertIn("tests.test_run330_note_profile_exact_update", WORKFLOW)
        self.assertNotIn("xvfb-run -a python run311_note_profile_update.py", WORKFLOW)
        self.assertIn("/aiif note profile update", CHATOPS)
        self.assertIn(token, CHATOPS)
        self.assertIn("note-profile-update.yml", CHATOPS)
        self.assertNotIn("schedule:", WORKFLOW)
        self.assertNotIn("push:", WORKFLOW)
        for text in (WORKFLOW.upper(), CHATOPS.upper()):
            self.assertNotIn("GEMINI_API", text)
            self.assertNotIn("GOOGLE_API_KEY", text)
            self.assertNotIn("NOTION_API", text)


if __name__ == "__main__":
    unittest.main()
