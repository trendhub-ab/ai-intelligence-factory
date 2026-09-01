import inspect
import unittest

import run186_note_header_image_resilience as run186


class Run186HeaderImageResilienceTests(unittest.TestCase):
    def test_header_label_score_prefers_semantic_controls(self):
        self.assertEqual(0, run186._header_label_score("見出し画像を追加"))
        self.assertEqual(0, run186._header_label_score("アイキャッチ画像を設定"))
        self.assertEqual(0, run186._header_label_score("画像を変更"))
        self.assertEqual(2, run186._header_label_score("画像"))

    def test_header_label_score_rejects_unrelated_controls(self):
        self.assertIsNone(run186._header_label_score("公開設定"))
        self.assertIsNone(run186._header_label_score("プロフィール"))
        self.assertIsNone(run186._header_label_score(""))

    def test_candidate_detection_rejects_body_toolbar_by_geometry(self):
        source = inspect.getsource(run186._candidate_header_control)
        self.assertIn("if y > title_y + 12", source)
        self.assertIn("page.mouse.move", source)
        self.assertIn("title*", source)

    def test_file_input_fallback_is_ambiguity_closed(self):
        source = inspect.getsource(run186._image_file_input)
        self.assertIn("len(usable) == 1", source)

    def test_persistence_has_geometry_fallback(self):
        source = inspect.getsource(run186._persisted_header_image)
        self.assertIn("width >= 480", source)
        self.assertIn("height >= 120", source)
        self.assertIn("y < title_y", source)

    def test_overlay_has_zero_model_and_no_public_release_action(self):
        source = inspect.getsource(run186)
        self.assertNotIn("GEMINI_API_KEY", source)
        self.assertNotIn("_generate_via_chat", source)
        self.assertNotIn("公開に進む", source)
        self.assertNotIn("投稿する", source)


if __name__ == "__main__":
    unittest.main()
