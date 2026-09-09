from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run315_member_onboarding_update as run315
import run317_member_onboarding_server_save as run317

ROOT = Path(__file__).resolve().parents[1]


class Run317MemberOnboardingServerSaveTests(unittest.TestCase):
    def test_exact_target_and_source_states_are_hard_bound(self) -> None:
        self.assertEqual(run317.CONFIRM_TOKEN, "SAVE_MEMBER_ONBOARDING_SERVER_N284E428C80F4_SHA4826AABC")
        self.assertEqual(run315.TARGET_NOTE_ID, "n284e428c80f4")
        self.assertEqual(run317.NEW_BODY_SHA256, "aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6")
        source = inspect.getsource(run317._source_state)
        self.assertIn("run315.AUDITED_TITLE", source)
        self.assertIn("run315.AUDITED_BODY_SHA256", source)
        self.assertIn("run315.NEW_TITLE", source)
        self.assertIn("NEW_BODY_SHA256", source)

    def test_rewrite_uses_exact_range_and_exact_temporary_save(self) -> None:
        rewrite = inspect.getsource(run317._rewrite_and_save)
        button = inspect.getsource(run317._exact_temporary_save_button)
        self.assertIn("_paste_manuscript_dom_range", rewrite)
        self.assertIn("run315.MANUSCRIPT", rewrite)
        self.assertIn("run315._verify_editor", rewrite)
        self.assertIn("一時保存", button)
        self.assertIn("is_enabled", button)
        self.assertNotIn("Control+A", rewrite)

    def test_fresh_proof_is_cookie_only_and_not_persistent_profile(self) -> None:
        proof = inspect.getsource(run317._verify_fresh_server_state)
        context = inspect.getsource(run317._new_cookie_only_context)
        self.assertIn("_launch_clean_browser", proof)
        self.assertIn("_new_cookie_only_context", proof)
        self.assertIn("context.add_cookies", context)
        self.assertIn("browser.new_context", context)
        self.assertNotIn("storage_state", proof)
        self.assertNotIn("_launch_persistent_context", proof)
        self.assertNotIn("_seed_note_state", proof)
        self.assertIn('"fresh_context_local_storage_seeded": False', proof)

    def test_server_save_never_publishes_or_mutates_membership(self) -> None:
        source = inspect.getsource(run317.save_server_revision)
        self.assertNotIn("公開に進む", source)
        self.assertNotIn("_ensure_membership_selected", source)
        self.assertNotIn("_verify_public", source)
        self.assertIn('"public_release": False', source)
        self.assertIn('"membership_mutation": False', source)
        self.assertIn('"zero_gemini_calls": True', source)

    def test_workflow_is_manual_exact_and_zero_model(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "note-member-onboarding-server-save.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("SAVE_MEMBER_ONBOARDING_SERVER_N284E428C80F4_SHA4826AABC", workflow)
        self.assertIn("run317_member_onboarding_server_save.py", workflow)
        self.assertIn("fresh cookie-only context verified", workflow)
        self.assertIn("zero Gemini calls: `true`", workflow)
        self.assertNotIn("NOTE_STORAGE_STATE_B64", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("push:", workflow)

    def test_chatops_route_is_exact_and_server_save_only(self) -> None:
        bridge = (ROOT / ".github" / "workflows" / "chatops-note.yml").read_text(encoding="utf-8")
        self.assertIn("/aiif note onboarding server-save", bridge)
        self.assertIn("onboarding_server_save", bridge)
        self.assertIn("note-member-onboarding-server-save.yml", bridge)
        self.assertIn("server-save proof only", bridge)


if __name__ == "__main__":
    unittest.main()
