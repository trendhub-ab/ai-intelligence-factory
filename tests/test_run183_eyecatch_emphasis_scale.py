import inspect
import unittest
from pathlib import Path

import run181_eyecatch_visual_balance as run181
import run183_eyecatch_emphasis_scale as run183


ROOT = Path(__file__).resolve().parents[1]


class Run183EyecatchEmphasisScaleTests(unittest.TestCase):
    def setUp(self):
        self._scale = run181.HIGHLIGHT_FONT_SCALE
        self._cap = run181.HIGHLIGHT_MAX_FONT
        run181.HIGHLIGHT_FONT_SCALE = 1.20
        run181.HIGHLIGHT_MAX_FONT = 96

    def tearDown(self):
        run181.HIGHLIGHT_FONT_SCALE = self._scale
        run181.HIGHLIGHT_MAX_FONT = self._cap

    def test_policy_is_exactly_twenty_percent(self):
        self.assertEqual(1.20, run183.HIGHLIGHT_FONT_SCALE)
        self.assertEqual(96, run183.HIGHLIGHT_MAX_FONT)

    def test_fit_targets_twenty_percent_when_geometry_allows(self):
        lines = ["AIは重要。でも正直、", "もう追いきれない。"]
        size = run181._fit_highlight_size(lines, 56, 16, "もう追いきれない。")
        self.assertGreaterEqual(size, 56)
        self.assertLessEqual(size, round(56 * 1.20))

    def test_fit_never_exceeds_geometry_cap(self):
        lines = ["OpenAIの新しいエージェント機能、", "仕事はどこまで任せられる？"]
        size = run181._fit_highlight_size(lines, 45, 16, "仕事はどこまで任せられる？")
        self.assertGreaterEqual(size, 45)
        self.assertLessEqual(size, round(45 * 1.20))
        self.assertLessEqual(size, 96)

    def test_multiline_highlight_is_split_across_both_lines(self):
        lines = ["生成AIの『速さ』競争が変わる。", "小さなモデルは実務で", "どこまで使えるのか"]
        highlight = "小さなモデルは実務でどこまで使えるのか"
        second = run181._split_line_for_highlight(lines, 1, highlight)
        third = run181._split_line_for_highlight(lines, 2, highlight)
        self.assertEqual([("小さなモデルは実務で", True)], second)
        self.assertEqual([("どこまで使えるのか", True)], third)

    def test_run183_makes_no_provider_calls(self):
        source = inspect.getsource(run183)
        self.assertNotIn("_generate_via_chat", source)
        self.assertNotIn("GEMINI_API_KEY", source)

    def test_production_order_is_run182_then_run183(self):
        source = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        run182_pos = source.index("run182_eyecatch_conclusion_emphasis.install(pipeline_module)")
        run183_pos = source.index("run183_eyecatch_emphasis_scale.install(pipeline_module)")
        bridge_pos = source.index("reader_value_review_bridge.install(pipeline_module)")
        self.assertLess(run182_pos, run183_pos)
        self.assertLess(run183_pos, bridge_pos)


if __name__ == "__main__":
    unittest.main()
