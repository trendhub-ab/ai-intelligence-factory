from unittest import TestCase
from unittest.mock import Mock, patch

import note_draft_automation as base
import run193_note_official_header_upload as upload


class Run193ExistingEyecatchReplacementTests(TestCase):
    def test_existing_cover_uses_official_remove_then_readd(self):
        page = Mock()
        image = Mock()
        remove = Mock()
        cover = Mock()
        cover_box = {"x": 100, "y": 120, "width": 620, "height": 325}

        with patch.object(upload.run189, "_ensure_editor_route") as route, \
             patch.object(upload, "_find_existing_cover", return_value=(cover, cover_box)) as find_cover, \
             patch.object(upload, "_find_existing_cover_remove_control", return_value=remove) as find_remove, \
             patch.object(upload, "_wait_existing_cover_removed") as wait_removed, \
             patch.object(upload, "_upload_new_header_image") as upload_new:
            upload._upload_header_image(page, image, media_changed="changed")

        route.assert_called_once_with(page)
        find_cover.assert_called_once_with(page)
        find_remove.assert_called_once_with(page, cover_box)
        remove.click.assert_called_once_with()
        wait_removed.assert_called_once_with(page)
        upload_new.assert_called_once_with(page, image, media_changed="changed")

    def test_empty_header_keeps_existing_new_upload_flow(self):
        page = Mock()
        image = Mock()

        with patch.object(upload.run189, "_ensure_editor_route"), \
             patch.object(upload, "_find_existing_cover", return_value=None), \
             patch.object(upload, "_find_existing_cover_remove_control") as find_remove, \
             patch.object(upload, "_wait_existing_cover_removed") as wait_removed, \
             patch.object(upload, "_upload_new_header_image") as upload_new:
            upload._upload_header_image(page, image)

        find_remove.assert_not_called()
        wait_removed.assert_not_called()
        upload_new.assert_called_once_with(page, image, media_changed=None)

    def test_ambiguous_existing_cover_fails_before_any_delete_or_upload(self):
        page = Mock()
        image = Mock()

        with patch.object(upload.run189, "_ensure_editor_route"), \
             patch.object(
                 upload,
                 "_find_existing_cover",
                 side_effect=base.NoteDraftError("note existing header image is ambiguous"),
             ), \
             patch.object(upload, "_find_existing_cover_remove_control") as find_remove, \
             patch.object(upload, "_upload_new_header_image") as upload_new:
            with self.assertRaisesRegex(base.NoteDraftError, "ambiguous"):
                upload._upload_header_image(page, image)

        find_remove.assert_not_called()
        upload_new.assert_not_called()

    def test_ambiguous_remove_control_fails_before_delete_and_readd(self):
        page = Mock()
        image = Mock()
        cover = Mock()
        cover_box = {"x": 100, "y": 120, "width": 620, "height": 325}

        with patch.object(upload.run189, "_ensure_editor_route"), \
             patch.object(upload, "_find_existing_cover", return_value=(cover, cover_box)), \
             patch.object(
                 upload,
                 "_find_existing_cover_remove_control",
                 side_effect=base.NoteDraftError("note existing header remove control is ambiguous"),
             ), \
             patch.object(upload, "_upload_new_header_image") as upload_new:
            with self.assertRaisesRegex(base.NoteDraftError, "remove control is ambiguous"):
                upload._upload_header_image(page, image)

        upload_new.assert_not_called()

    def test_remove_click_failure_never_enters_new_upload_flow(self):
        page = Mock()
        image = Mock()
        cover = Mock()
        remove = Mock()
        remove.click.side_effect = RuntimeError("click failed")
        cover_box = {"x": 100, "y": 120, "width": 620, "height": 325}

        with patch.object(upload.run189, "_ensure_editor_route"), \
             patch.object(upload, "_find_existing_cover", return_value=(cover, cover_box)), \
             patch.object(upload, "_find_existing_cover_remove_control", return_value=remove), \
             patch.object(upload, "_upload_new_header_image") as upload_new:
            with self.assertRaisesRegex(base.NoteDraftError, "existing-header X"):
                upload._upload_header_image(page, image)

        upload_new.assert_not_called()

    def test_unique_cover_detection_rejects_multiple_large_images(self):
        page = Mock()
        title = Mock()
        title.bounding_box.return_value = {"x": 100, "y": 700, "width": 800, "height": 60}

        def make_image(y):
            item = Mock()
            item.is_visible.return_value = True
            item.bounding_box.return_value = {"x": 390, "y": y, "width": 620, "height": 325}
            return item

        first = make_image(100)
        second = make_image(360)
        images = Mock()
        images.count.return_value = 2
        images.nth.side_effect = [first, second]
        page.locator.return_value = images

        with patch.object(upload.base, "_find_title", return_value=title):
            with self.assertRaisesRegex(base.NoteDraftError, "ambiguous"):
                upload._find_existing_cover(page)


if __name__ == "__main__":
    import unittest
    unittest.main()
