import inspect
import unittest

import editorial_eyecatch as ee
import run180_eyecatch_semantic_layout as run180
import run181_eyecatch_visual_balance as run181


class Run230EyecatchRemoveLowerLeadMinimalTests(unittest.TestCase):
    def test_direct_renderer_no_longer_draws_lower_lead(self):
        source = inspect.getsource(ee.generate_note_editorial_eyecatch)
        self.assertNotIn("editorial_subheadline(", source)
        self.assertNotIn("sub_y =", source)
        self.assertNotIn("sub_lines =", source)
        self.assertNotIn("draw.rectangle((48, sub_y + 2, 53, sub_y + 42)", source)

    def test_balanced_renderer_no_longer_draws_lower_lead(self):
        source = inspect.getsource(run181._render_balanced_plan)
        self.assertNotIn('validated["subheadline_lines"]', source)
        self.assertNotIn('validated["subheadline_font_size"]', source)
        self.assertNotIn("sub_y =", source)
        self.assertNotIn("draw.rectangle((48, sub_y + 2, 53, sub_y + 42)", source)

    def test_run229_gemini_title_contract_is_untouched(self):
        self.assertEqual("gemini-3.5-flash", run180.EYECATCH_LAYOUT_MODEL)
        self.assertEqual(1400, run180.EYECATCH_LAYOUT_MAX_OUTPUT_TOKENS)
        self.assertIn("subheadline_lines", run180._LAYOUT_RESPONSE_SCHEMA["properties"])
        self.assertIn("subheadline_font_size", run180._LAYOUT_RESPONSE_SCHEMA["properties"])
        prompt = run180._layout_prompt(
            "Polars 2.0が変えるデータ開発", "既存の下部説明テキスト"
        )
        self.assertIn("subheadline_lines", prompt)

    def test_title_geometry_constants_are_unchanged(self):
        self.assertEqual(4, run181.TITLE_FONT_BOOST)
        self.assertEqual(80, run181.TITLE_MAX_FONT)
        self.assertEqual(760, run181.TITLE_MAX_WIDTH)
        self.assertEqual(30, run181.TITLE_Y_SHIFT)
        self.assertEqual(16, run181.SUBTITLE_Y_SHIFT)
        self.assertEqual(468, run181.TITLE_SAFE_BOTTOM)


if __name__ == "__main__":
    unittest.main()
