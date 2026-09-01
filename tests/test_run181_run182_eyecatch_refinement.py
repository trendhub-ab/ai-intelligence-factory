import inspect
import unittest
from pathlib import Path
from unittest.mock import patch

import run180_eyecatch_semantic_layout as run180
import run181_eyecatch_visual_balance as run181
import run182_eyecatch_conclusion_emphasis as run182


ROOT = Path(__file__).resolve().parents[1]


class Run181Run182EyecatchRefinementTests(unittest.TestCase):
    def test_run181_boosts_up_to_four_pixels_when_geometry_allows(self):
        with patch.object(run181.ee, "_jp_font", side_effect=lambda size, bold=True: size), patch.object(
            run181.ee, "_text_width", side_effect=lambda draw, text, font: len(text) * font
        ):
            self.assertEqual(56, run181._boost_title_size(["abcdefghij"], 52))

    def test_run181_uses_largest_safe_size_not_blind_plus_four(self):
        with patch.object(run181.ee, "_jp_font", side_effect=lambda size, bold=True: size), patch.object(
            run181.ee, "_text_width", side_effect=lambda draw, text, font: len(text) * font
        ):
            # 14 chars: 56px is 784px, 55px is 770px, 54px is 756px.
            self.assertEqual(54, run181._boost_title_size(["abcdefghijklmn"], 52))

    def test_run181_balance_constants_match_approved_visual_sample(self):
        self.assertEqual(4, run181.TITLE_FONT_BOOST)
        self.assertEqual(80, run181.TITLE_MAX_FONT)
        self.assertEqual(30, run181.TITLE_Y_SHIFT)
        self.assertEqual(16, run181.SUBTITLE_Y_SHIFT)
        self.assertEqual((242, 140, 40), run181.HIGHLIGHT_ORANGE)

    def test_run182_highlight_can_span_two_semantic_lines(self):
        lines = [
            "生成AIの「速さ」競争が変わる。",
            "小さなモデルは実務で",
            "どこまで使えるのか",
        ]
        highlight = "小さなモデルは実務でどこまで使えるのか"
        self.assertEqual([(lines[0], False)], run181._split_line_for_highlight(lines, 0, highlight))
        self.assertEqual([(lines[1], True)], run181._split_line_for_highlight(lines, 1, highlight))
        self.assertEqual([(lines[2], True)], run181._split_line_for_highlight(lines, 2, highlight))

    def test_run182_highlight_can_start_inside_a_line(self):
        lines = ["AIは重要。でも正直、", "もう追いきれない。"]
        highlight = "もう追いきれない。"
        self.assertEqual([(lines[0], False)], run181._split_line_for_highlight(lines, 0, highlight))
        self.assertEqual([(lines[1], True)], run181._split_line_for_highlight(lines, 1, highlight))

    def test_run180_validates_exact_conclusion_phrase_but_disables_rewrite(self):
        headline = "AIは重要。でも正直、もう追いきれない。"
        lines = ["AIは重要。でも正直、", "もう追いきれない。"]
        self.assertEqual(
            "もう追いきれない。",
            run180._validate_highlight_text(headline, lines, "もう追いきれない。"),
        )
        self.assertEqual("", run180._validate_highlight_text(headline, lines, "もう追えません。"))

    def test_run180_disables_overbroad_highlight_instead_of_rejecting_layout(self):
        headline = "AIは重要。でも正直、もう追いきれない。"
        lines = ["AIは重要。でも正直、", "もう追いきれない。"]
        self.assertEqual("", run180._validate_highlight_text(headline, lines, headline))

    def test_existing_single_layout_call_now_returns_highlight_in_same_schema(self):
        self.assertIn("highlight_text", run180._LAYOUT_RESPONSE_SCHEMA["properties"])
        self.assertIn("highlight_text", run180._LAYOUT_RESPONSE_SCHEMA["required"])
        source = inspect.getsource(run180._request_layout_plan)
        self.assertEqual(1, source.count("_generate_via_chat("))
        self.assertIn("_LAYOUT_RESPONSE_SCHEMA", source)
        prompt = run180._layout_prompt("AIは重要。でも正直、もう追いきれない。", "要約")
        self.assertIn("highlight_text", prompt)
        self.assertIn("もう追いきれない。", prompt)

    def test_run181_and_run182_add_no_provider_calls(self):
        self.assertNotIn("_generate_via_chat", inspect.getsource(run181))
        self.assertNotIn("_generate_via_chat", inspect.getsource(run182))

    def test_production_order_is_run180_then_181_then_182(self):
        source = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        p180 = source.index("run180_eyecatch_semantic_layout.install(pipeline_module)")
        p181 = source.index("run181_eyecatch_visual_balance.install(pipeline_module)")
        p182 = source.index("run182_eyecatch_conclusion_emphasis.install(pipeline_module)")
        self.assertLess(p180, p181)
        self.assertLess(p181, p182)


if __name__ == "__main__":
    unittest.main()
