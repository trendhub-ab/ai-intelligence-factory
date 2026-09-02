from __future__ import annotations

import inspect
import unittest

import run193_note_official_header_upload as run193


class Run193OfficialHeaderUploadTests(unittest.TestCase):
    def test_geometry_accepts_header_icon_above_title(self) -> None:
        title = {"x": 380.0, "y": 220.0, "width": 700.0, "height": 50.0}
        icon = {"x": 382.0, "y": 98.0, "width": 40.0, "height": 40.0, "semantic": "", "has_graphic": True}
        self.assertIsNotNone(run193._header_button_score(icon, title))

    def test_geometry_rejects_body_plus_and_top_right_controls(self) -> None:
        title = {"x": 380.0, "y": 220.0, "width": 700.0, "height": 50.0}
        body_plus = {"x": 320.0, "y": 315.0, "width": 40.0, "height": 40.0, "semantic": "", "has_graphic": True}
        top_right = {"x": 1300.0, "y": 20.0, "width": 60.0, "height": 36.0, "semantic": "", "has_graphic": True}
        self.assertIsNone(run193._header_button_score(body_plus, title))
        self.assertIsNone(run193._header_button_score(top_right, title))

    def test_geometry_rejects_publish_or_save_semantics_even_in_header_zone(self) -> None:
        title = {"x": 380.0, "y": 220.0, "width": 700.0, "height": 50.0}
        publish = {"x": 382.0, "y": 98.0, "width": 40.0, "height": 40.0, "semantic": "公開", "has_graphic": True}
        save = {"x": 382.0, "y": 98.0, "width": 40.0, "height": 40.0, "semantic": "保存", "has_graphic": True}
        self.assertIsNone(run193._header_button_score(publish, title))
        self.assertIsNone(run193._header_button_score(save, title))

    def test_official_flow_uses_upload_menu_not_synthetic_drag_drop(self) -> None:
        source = inspect.getsource(run193)
        self.assertIn("画像をアップロード", source)
        self.assertIn("expect_file_chooser", source)
        self.assertNotIn("DataTransfer", source)
        self.assertNotIn("DragEvent", source)

    def test_ai_close_only_dialog_is_not_a_safe_crop_completion(self) -> None:
        close = "閉じる"
        self.assertTrue(any(term in close for term in run193._CROP_REJECT_TERMS))
        self.assertFalse(any(term in close for term in run193._CROP_POSITIVE_TERMS))

    def test_module_contains_no_public_release_action(self) -> None:
        source = inspect.getsource(run193)
        self.assertNotIn("公開する", source)
        self.assertNotIn("投稿する", source)
        self.assertNotIn("Gemini", source.replace("zero Gemini/model calls", ""))


if __name__ == "__main__":
    unittest.main()
