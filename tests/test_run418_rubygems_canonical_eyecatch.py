import inspect
import unittest

import run418_rubygems_canonical_eyecatch as r418


class Run418CanonicalEyecatchTests(unittest.TestCase):
    def test_exact_target_and_known_broken_asset_are_pinned(self):
        self.assertEqual(r418.PAGE_ID, "3d9479ff-dca9-819a-814c-e4a0aeb3263f")
        self.assertEqual(r418.SYNC_ID, "3d9479ffdca9819a814ce4a0aeb3263f")
        self.assertEqual(r418.BROKEN_FILENAME, "run414-rubygems.png")
        self.assertEqual(r418.FIXED_FILENAME, "run418-rubygems-canonical.png")

    def test_render_requires_production_stack_and_one_35_layout_call(self):
        source = inspect.getsource(r418._render_canonical)
        self.assertIn("_install_canonical_eyecatch_runtime", source)
        self.assertIn('gemini-3.5-flash', source)
        self.assertIn("Run418 refuses a second model request", source)
        self.assertIn("_request_layout_plan", source)
        self.assertIn("_validate_layout_plan", source)
        self.assertIn("_render_with_validated_plan", source)
        self.assertIn("refuses raw/base eyecatch fallback", source)
        self.assertNotIn("generate_note_editorial_eyecatch(", source)

    def test_runtime_requires_current_visual_layers_and_canonical_japanese_font(self):
        source = inspect.getsource(r418._install_canonical_eyecatch_runtime)
        for marker in (
            "_RUN179_EYECATCH_FONT_REFINEMENT_INSTALLED",
            "_RUN180_EYECATCH_SEMANTIC_LAYOUT_INSTALLED",
            "_RUN181_EYECATCH_VISUAL_BALANCE_INSTALLED",
            "_RUN182_EYECATCH_CONCLUSION_EMPHASIS_INSTALLED",
            "_RUN183_EYECATCH_EMPHASIS_SCALE_INSTALLED",
            "_RUN296_EDITORIAL_FORMAT_V2_INSTALLED",
        ):
            self.assertIn(marker, source)
        self.assertIn("Noto Sans JP", source)

    def test_private_draft_repair_is_header_only_and_in_place(self):
        source = inspect.getsource(r418.refresh_existing_private_draft)
        self.assertIn("_find_one_existing_route", source)
        self.assertIn("_replace_existing_header", source)
        self.assertIn("body changed during header-only repair", source)
        self.assertIn("accidentally changed private draft identity", source)
        self.assertNotIn("_paste_manuscript", source)
        self.assertNotIn("NOTE_NEW_URL", source)

    def test_no_public_release_surface(self):
        source = inspect.getsource(r418)
        forbidden_calls = ("publish_note", "click_publish", "release_note", "公開する")
        for token in forbidden_calls:
            self.assertNotIn(token, source)
        self.assertIn('"public_release": False', source)
        self.assertIn('"duplicate_draft_created": False', source)


if __name__ == "__main__":
    unittest.main()
