from pathlib import Path
import unittest
from unittest.mock import patch

import run_vtcode_existing_draft_repair as repair


class VTCodeExistingDraftRepairTests(unittest.TestCase):
    def test_exact_chatops_command_dispatches_only_private_repair(self):
        workflow = Path('.github/workflows/vtcode-existing-draft-repair.yml').read_text()
        bridge = Path('.github/workflows/chatops-note.yml').read_text()
        self.assertIn("REPAIR_VTCODE_EXISTING_DRAFT", workflow)
        self.assertIn("run_vtcode_existing_draft_repair.py", workflow)
        self.assertIn("'/aiif note repair vtcode'", bridge)
        self.assertIn("workflow='vtcode-existing-draft-repair.yml'", bridge)
        self.assertNotIn('publish-note', workflow)
    def test_repaired_article_has_short_title_complete_provenance_and_disclaimer(self):
        article = repair.load_manuscript()
        self.assertTrue(article.startswith("# VT Code："))
        self.assertNotIn("Show HN:", article.splitlines()[0])
        self.assertEqual(article.count("### Sources / Evidence"), 1)
        self.assertIn("**主一次情報**", article)
        self.assertIn("**出典について**", article)
        self.assertIn("※本記事に含まれる見解・提案は", article)
        self.assertLess(article.index("※本記事"), article.index("### 有料サブスクのご案内"))

    def test_repaired_article_passes_current_production_gates(self):
        result = repair.validate_repaired_manuscript()
        self.assertEqual(result["issues"], [])
        self.assertTrue(result["fact_ok"])
        self.assertTrue(result["editorial_ok"])
        self.assertEqual(result["publication_state"], "PASS")
        self.assertEqual(result["human_state"], "ACCEPTABLE")

    def test_eyecatch_is_full_size_and_has_no_duplicate_draft_path(self):
        from PIL import Image
        with Image.open(repair.IMAGE_PATH) as image:
            self.assertEqual(image.size, (1280, 670))
        source = Path('run_vtcode_existing_draft_repair.py').read_text()
        self.assertNotIn('"/new"', source)
        self.assertIn('same_edit_route', source)

    def test_preflight_rejects_other_article_or_posted_destination(self):
        page = {"id": repair.DESTINATION_PAGE_ID,
                "properties": {"同期ID": {"rich_text": [{"plain_text": repair.SYNC_ID}]},
                               "投稿状態": {"select": {"name": "投稿済み"}},
                               "品質状態": {"select": {"name": "Ready"}}}}
        with patch.object(repair.ready_sync, "_query_db", return_value=[page]):
            with self.assertRaisesRegex(repair.VTCodeRepairError, "投稿準備中"):
                repair.destination_preflight()

    def test_preflight_rejects_public_url_even_with_preparing_status(self):
        page = {"id": repair.DESTINATION_PAGE_ID,
                "properties": {"同期ID": {"rich_text": [{"plain_text": repair.SYNC_ID}]},
                               "投稿状態": {"select": {"name": "投稿準備中"}},
                               "品質状態": {"select": {"name": "Ready"}},
                               "note公開URL": {"url": "https://note.com/example/n/public"}}}
        with patch.object(repair.ready_sync, "_query_db", return_value=[page]):
            with self.assertRaisesRegex(repair.VTCodeRepairError, "public-post evidence"):
                repair.destination_preflight()

    def test_route_preflight_precedes_notional_source_write(self):
        with patch.object(repair, "validate_repaired_manuscript", return_value={"fact_ok": True, "editorial_ok": True, "publication_state": "PASS", "human_state": "ACCEPTABLE"}), \
             patch.object(repair, "destination_preflight", return_value={"posting_state": "投稿準備中", "quality_state": "Ready"}), \
             patch.object(repair, "_source_preflight", return_value={}), \
             patch.object(repair, "draft_preflight", side_effect=repair.VTCodeRepairError("ambiguous route")), \
             patch.object(repair, "sync_corrected_source") as source:
            with self.assertRaisesRegex(repair.VTCodeRepairError, "ambiguous route"):
                repair.run(confirm=repair.CONFIRM_TOKEN)
        source.assert_not_called()

    def test_crop_wait_requires_replacement_identity_for_existing_cover(self):
        from unittest.mock import Mock
        import run193_note_official_header_upload as upload
        page = Mock()
        page.wait_for_timeout.return_value = None
        changed = Mock(side_effect=[False, True])
        with patch.object(upload.run188, "_header_preview_present", return_value=True), \
             patch.object(upload, "_visible_modal_roots", return_value=[]):
            upload._finish_real_crop_or_preview(page, media_changed=changed)
        self.assertEqual(changed.call_count, 2)
        page.wait_for_timeout.assert_called_once()

    def test_existing_cover_change_button_is_preferred_before_geometry(self):
        from unittest.mock import Mock
        import run193_note_official_header_upload as upload
        existing = Mock()
        with patch.object(upload.base, "_first_visible", return_value=existing) as controls:
            self.assertIs(upload._find_header_add_control(Mock()), existing)
        selectors = controls.call_args.args[1]
        self.assertIn('button[aria-label="画像を変更"]', selectors)

    def test_existing_cover_hover_reveals_change_control(self):
        from unittest.mock import Mock
        import run193_note_official_header_upload as upload
        button = Mock()
        with patch.object(upload.base, "_first_visible", return_value=None), \
             patch.object(upload.run186, "_candidate_header_control", return_value=button) as hover:
            self.assertIs(upload._find_header_add_control(Mock()), button)
        hover.assert_called_once()

    def test_preflight_is_zero_model_and_does_not_open_note(self):
        with patch.object(repair, "validate_repaired_manuscript", return_value={"fact_ok": True, "editorial_ok": True, "publication_state": "PASS", "human_state": "ACCEPTABLE"}), \
             patch.object(repair, "destination_preflight", return_value={"posting_state": "投稿準備中", "quality_state": "Ready"}), \
             patch.object(repair, "_source_preflight", return_value={}), \
             patch.object(repair, "browser_repair") as browser, \
             patch.object(repair, "sync_corrected_source") as source:
            result = repair.run(confirm=repair.CONFIRM_TOKEN, prepare_only=True)
        browser.assert_not_called()
        source.assert_not_called()
        self.assertEqual(result["status"], "repair_ready")
        self.assertFalse(result["public_release"])
        self.assertFalse(result["new_draft_created"])
