from __future__ import annotations

import inspect
import os
import unittest
from unittest.mock import patch

import run190_note_persistent_cloud as run190


class _FakeEditButton:
    def __init__(self, page, count: int, target_url: str) -> None:
        self._page = page
        self._count = count
        self._target_url = target_url

    def count(self) -> int:
        return self._count

    def click(self, timeout: int = 0) -> None:
        del timeout
        self._page.edit_button_clicks += 1
        self._page.url = self._target_url


class _FakeArticleListPage:
    def __init__(self, *, button_count: int = 0, click_url: str = "") -> None:
        self.url = run190.ARTICLE_LIST_URL
        self.button_count = button_count
        self.click_url = click_url
        self.edit_button_clicks = 0
        self.button_query = None

    def goto(self, url: str, **kwargs) -> None:
        del kwargs
        self.url = url

    def wait_for_timeout(self, milliseconds: int) -> None:
        del milliseconds

    def get_by_role(self, role: str, *, name: str, exact: bool):
        self.button_query = (role, name, exact)
        return _FakeEditButton(self, self.button_count, self.click_url)


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
        self.assertIn("base._body_manuscript_for_note", source)
        self.assertNotIn("Gemini", source)

    def test_persistent_cloud_override_forwards_stable_route_callback(self) -> None:
        signature = inspect.signature(run190._create_browser_draft)
        self.assertIn("on_stable_draft_url", signature.parameters)
        source = inspect.getsource(run190._create_browser_draft)
        self.assertIn("on_stable_draft_url=on_stable_draft_url", source)

    def test_creation_requires_expected_note_account_before_any_draft_mutation(self) -> None:
        source = inspect.getsource(run190._create_browser_draft)
        self.assertIn("_assert_expected_note_account(page)", source)
        self.assertLess(
            source.index("_assert_expected_note_account(page)"),
            source.index("base._upload_header_image"),
        )

    def test_expected_creator_name_matches_current_public_creator(self) -> None:
        self.assertEqual(run190.EXPECTED_CREATOR_NAME, "AIF - AI Intelligence Factory")

    def test_expected_profile_href_match_is_exact(self) -> None:
        self.assertTrue(run190._is_expected_profile_href("/trendhub_biz"))
        self.assertTrue(run190._is_expected_profile_href("https://note.com/trendhub_biz"))
        self.assertTrue(run190._is_expected_profile_href("https://note.com/trendhub_biz/"))
        self.assertFalse(run190._is_expected_profile_href("https://evil.example/trendhub_biz"))
        self.assertFalse(run190._is_expected_profile_href("https://note.com/trendhub_biz-other"))
        self.assertFalse(run190._is_expected_profile_href("https://note.com/other"))

    def test_account_proof_uses_authenticated_settings_page_profile_link(self) -> None:
        source = inspect.getsource(run190._assert_expected_note_account)
        self.assertIn("_settings_page_has_expected_profile_link(page)", source)
        self.assertNotIn("page.goto(EXPECTED_NOTE_PROFILE_URL", source)
        self.assertNotIn("_exact_settings_control(page)", source)

    def test_creation_requires_official_article_list_proof_before_returning_success(self) -> None:
        source = inspect.getsource(run190._create_browser_draft)
        self.assertIn("draft_url = base._save_draft_and_verify", source)
        self.assertIn("_verify_draft_in_article_list(page, draft_url, title)", source)
        self.assertLess(
            source.index("_verify_draft_in_article_list(page, draft_url, title)"),
            source.index("return draft_url"),
        )

    def test_official_list_proof_accepts_exact_edit_button_resolving_same_draft_id(self) -> None:
        draft_id = "n40cb200b1c27"
        draft_url = f"https://note.com/notes/{draft_id}/edit"
        title = "Target title"
        page = _FakeArticleListPage(button_count=1, click_url=draft_url)
        with (
            patch.object(run190.base, "_looks_logged_out", return_value=False),
            patch.object(run190, "_article_list_has_draft_id", return_value=False),
            patch.object(run190.run187, "_is_editor_url", side_effect=lambda url: str(url).endswith("/edit")),
            patch.object(run190.reconcile, "draft_identity_from_url", return_value=draft_id),
        ):
            run190._verify_draft_in_article_list(page, draft_url, title)
        self.assertEqual(page.button_query, ("button", f"{title}を編集", True))
        self.assertEqual(page.edit_button_clicks, 1)

    def test_official_list_proof_rejects_duplicate_exact_edit_buttons(self) -> None:
        draft_id = "n40cb200b1c27"
        draft_url = f"https://note.com/notes/{draft_id}/edit"
        page = _FakeArticleListPage(button_count=2, click_url=draft_url)
        with (
            patch.object(run190.base, "_looks_logged_out", return_value=False),
            patch.object(run190, "_article_list_has_draft_id", return_value=False),
            patch.object(run190.reconcile, "draft_identity_from_url", return_value=draft_id),
        ):
            with self.assertRaises(run190.base.NoteDraftError):
                run190._verify_draft_in_article_list(page, draft_url, "Duplicate title")

    def test_official_list_proof_rejects_edit_button_resolving_wrong_draft_id(self) -> None:
        draft_id = "n40cb200b1c27"
        draft_url = f"https://note.com/notes/{draft_id}/edit"
        page = _FakeArticleListPage(button_count=1, click_url="https://note.com/notes/nwrongdraft/edit")
        with (
            patch.object(run190.base, "_looks_logged_out", return_value=False),
            patch.object(run190, "_article_list_has_draft_id", return_value=False),
            patch.object(run190.run187, "_is_editor_url", return_value=True),
            patch.object(run190.reconcile, "draft_identity_from_url", side_effect=[draft_id, "nwrongdraft"]),
        ):
            with self.assertRaises(run190.base.NoteDraftError):
                run190._verify_draft_in_article_list(page, draft_url, "Wrong target")

    def test_official_list_legacy_href_proof_still_passes_without_edit_button(self) -> None:
        draft_id = "n40cb200b1c27"
        draft_url = f"https://note.com/notes/{draft_id}/edit"
        page = _FakeArticleListPage(button_count=0, click_url="")
        with (
            patch.object(run190.base, "_looks_logged_out", return_value=False),
            patch.object(run190, "_article_list_has_draft_id", return_value=True),
            patch.object(run190.reconcile, "draft_identity_from_url", return_value=draft_id),
        ):
            run190._verify_draft_in_article_list(page, draft_url, "Legacy title")
        self.assertIsNone(page.button_query)
        self.assertEqual(page.edit_button_clicks, 0)

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
