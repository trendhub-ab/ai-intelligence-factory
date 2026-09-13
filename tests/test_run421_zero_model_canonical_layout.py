import inspect
import unittest
from unittest import mock

from PIL import ImageFont

import editorial_eyecatch as ee
import run178_eyecatch_editorial_layout_optimizer as r178
import run421_rubygems_zero_model_canonical_layout as r421


class Run421ZeroModelCanonicalLayoutTests(unittest.TestCase):
    def test_deterministic_copy_is_source_bounded_and_exact_partitioned(self):
        with mock.patch.object(ee, "_jp_font", side_effect=lambda size, bold=True: ImageFont.load_default()):
            with mock.patch.object(r421.r418, "_install_canonical_eyecatch_runtime"):
                plan = r421._deterministic_plan()
        expected = ee.editorial_hook_from_title(r421.r418.EXPECTED_NOTE_TITLE, max_chars=48)
        self.assertEqual(plan["eyecatch_title"], expected)
        self.assertEqual(
            r178._canonical_partition_text("".join(plan["title_lines"])),
            r178._canonical_partition_text(expected),
        )
        self.assertIn("OpenAI", plan["eyecatch_title"])
        self.assertIn("RubyGems", plan["eyecatch_title"])

    def test_render_path_contains_no_model_call_or_raw_renderer(self):
        source = inspect.getsource(r421._render_zero_model)
        self.assertNotIn("_generate_via_chat", source)
        self.assertNotIn("_request_layout_plan", source)
        self.assertNotIn("generate_note_editorial_eyecatch", source)
        self.assertIn("_render_with_validated_plan", source)

    def test_exact_target_and_known_broken_asset_are_still_required(self):
        source = inspect.getsource(r421.render_and_attach)
        self.assertIn("require_broken=True", source)
        self.assertIn("_upload_replace", source)
        self.assertIn('"gemini_calls": 0', source)

    def test_existing_private_draft_refresh_is_inherited(self):
        source = inspect.getsource(r421.refresh_existing_private_draft)
        self.assertIn("r418.refresh_existing_private_draft", source)

    def test_no_public_release_surface(self):
        source = inspect.getsource(r421)
        for token in ("publish_note", "click_publish", "release_note", "公開する"):
            self.assertNotIn(token, source)
        self.assertIn('"public_release": False', source)


if __name__ == "__main__":
    unittest.main()
