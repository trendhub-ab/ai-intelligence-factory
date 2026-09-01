from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run188_note_header_upload_fallback as run188


class Run188NoteHeaderUploadFallbackTests(unittest.TestCase):
    def test_header_input_scoring_prefers_explicit_header_semantics(self) -> None:
        self.assertEqual(
            run188._header_input_score(
                {"accept": "image/*", "semantic": "見出し画像 upload", "ancestor_above_title": False},
                3,
            ),
            0,
        )
        self.assertEqual(
            run188._header_input_score(
                {"accept": "image/png", "semantic": "image", "ancestor_above_title": True},
                2,
            ),
            1,
        )

    def test_single_unlabelled_image_input_is_allowed_but_multiple_are_ambiguous(self) -> None:
        meta = {"accept": "image/*", "semantic": "", "ancestor_above_title": False}
        self.assertEqual(run188._header_input_score(meta, 1), 3)
        self.assertIsNone(run188._header_input_score(meta, 2))

    def test_non_image_file_input_is_rejected(self) -> None:
        self.assertIsNone(
            run188._header_input_score(
                {"accept": "application/pdf", "semantic": "cover", "ancestor_above_title": True},
                1,
            )
        )

    def test_mime_detection_is_image_scoped(self) -> None:
        self.assertEqual(run188._mime_for_path(Path("cover.png")), "image/png")
        self.assertEqual(run188._mime_for_path(Path("cover.jpg")), "image/jpeg")
        self.assertEqual(run188._mime_for_path(Path("cover.webp")), "image/webp")

    def test_overlay_uses_safe_file_input_then_header_zone_drop_without_release_action(self) -> None:
        source = inspect.getsource(run188)
        self.assertIn('input[type="file"]', source)
        self.assertIn("DataTransfer", source)
        self.assertIn("dragenter", source)
        self.assertIn("dragover", source)
        self.assertIn("drop", source)
        self.assertIn("base._upload_header_image = _upload_header_image", source)
        self.assertNotIn("Gemini", source.replace("zero Gemini/model calls", ""))
        self.assertNotIn("公開する", source)
        self.assertNotIn("投稿する", source)


if __name__ == "__main__":
    unittest.main()
