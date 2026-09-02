from __future__ import annotations

import inspect
import os
import unittest
from unittest.mock import patch

import run190_note_persistent_cloud as run190


class Run190PersistentCloudTests(unittest.TestCase):
    def test_profile_defaults_to_persistent_home_directory(self) -> None:
        self.assertEqual(run190.DEFAULT_PROFILE_DIR.name, "chrome-profile")
        self.assertIn(".aiif-note", str(run190.DEFAULT_PROFILE_DIR))

    def test_note_domain_filter_rejects_other_login_providers(self) -> None:
        self.assertTrue(run190._note_domain(".note.com"))
        self.assertTrue(run190._note_domain("editor.note.com"))
        self.assertFalse(run190._note_domain("accounts.google.com"))
        self.assertFalse(run190._note_domain("evilnote.com"))
        self.assertTrue(run190._note_origin("https://note.com"))
        self.assertFalse(run190._note_origin("https://accounts.google.com"))

    def test_real_chrome_uses_persistent_context(self) -> None:
        source = inspect.getsource(run190._launch_persistent_context)
        self.assertIn("launch_persistent_context", source)
        self.assertIn('CHANNEL_ENV, "chrome"', source)
        self.assertIn("user_data_dir", source)
        self.assertNotIn("storage_state=", source)

    def test_storage_state_is_only_optional_note_session_bootstrap(self) -> None:
        source = inspect.getsource(run190._seed_note_state)
        self.assertIn("NOTE_STORAGE_STATE_B64", inspect.getsource(run190._decode_bootstrap_state))
        self.assertIn("_note_domain", source)
        self.assertIn("_note_origin", source)
        self.assertNotIn("print(", source)

    def test_persistent_profile_can_run_without_legacy_storage_secret(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NOTE_STORAGE_STATE_B64", None)
            path = run190._compat_storage_path()
        try:
            self.assertTrue(path.exists())
            self.assertEqual("{}", path.read_text(encoding="utf-8"))
        finally:
            path.unlink(missing_ok=True)

    def test_run190_reuses_existing_fail_closed_draft_verification(self) -> None:
        source = inspect.getsource(run190._create_browser_draft)
        self.assertIn("base._upload_header_image", source)
        self.assertIn("base._verify_body_content", source)
        self.assertIn("base._save_draft_and_verify", source)
        self.assertNotIn("Gemini", source)

    def test_run190_installs_latest_official_header_upload_overlay(self) -> None:
        source = inspect.getsource(run190.install)
        self.assertIn("run193.install()", source)
        self.assertNotIn("run189.install()", source)
        self.assertNotIn("run191.install()", source)

    def test_module_contains_no_public_release_action(self) -> None:
        source = inspect.getsource(run190)
        self.assertNotIn("公開する", source)
        self.assertNotIn("投稿する", source)


if __name__ == "__main__":
    unittest.main()
