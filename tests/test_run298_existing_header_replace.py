from __future__ import annotations

import inspect
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import run298_existing_header_replace as overlay


class _FakePage:
    def wait_for_timeout(self, _ms):
        return None


class Run298ExistingHeaderReplaceTests(unittest.TestCase):
    def test_existing_header_uses_only_safe_header_input(self):
        page = _FakePage()
        file_input = MagicMock()
        image = Path("reviewed.png")
        with (
            patch.object(overlay, "_header_hash", return_value=("oldhash", 1)),
            patch.object(overlay.run188, "_safe_header_file_input", return_value=(file_input, 1)),
            patch.object(overlay, "_wait_for_changed_header", return_value=("newhash", 1)) as changed,
            patch.object(overlay.run193, "_upload_header_image") as add_upload,
        ):
            overlay._header_aware_upload(page, image)
        file_input.set_input_files.assert_called_once_with(str(image))
        changed.assert_called_once_with(page, "oldhash")
        add_upload.assert_not_called()

    def test_missing_existing_header_keeps_run193_add_path(self):
        page = _FakePage()
        image = Path("reviewed.png")
        with (
            patch.object(overlay, "_header_hash", return_value=("", 0)),
            patch.object(overlay.run193, "_upload_header_image") as add_upload,
            patch.object(overlay.run188, "_safe_header_file_input") as safe_input,
        ):
            overlay._header_aware_upload(page, image)
        add_upload.assert_called_once_with(page, image)
        safe_input.assert_not_called()

    def test_ambiguous_existing_header_input_fails_before_file_mutation(self):
        page = _FakePage()
        image = Path("reviewed.png")
        with (
            patch.object(overlay, "_header_hash", return_value=("oldhash", 1)),
            patch.object(overlay.run188, "_safe_header_file_input", return_value=(None, 2)),
        ):
            with self.assertRaisesRegex(
                overlay.ExistingHeaderReplaceError,
                "no unambiguous safe image input:2",
            ):
                overlay._replace_existing_header(page, image)

    def test_overlay_has_no_new_draft_public_release_or_model_surface(self):
        source = inspect.getsource(overlay)
        self.assertNotIn("NOTE_NEW_URL", source)
        self.assertNotIn("https://note.com/new", source)
        self.assertNotIn("_create_browser_draft", source)
        self.assertNotIn("generate_content", source)
        self.assertNotIn("client.models", source)
        self.assertNotIn("publish", source.lower())


if __name__ == "__main__":
    unittest.main()