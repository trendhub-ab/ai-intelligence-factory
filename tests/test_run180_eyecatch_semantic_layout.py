import inspect
import unittest
from pathlib import Path

import run180_eyecatch_semantic_layout as run180


ROOT = Path(__file__).resolve().parents[1]


class _ParsedResponse:
    def __init__(self, value):
        self.parsed = value
        self.text = ""


class _TextResponse:
    def __init__(self, text):
        self.parsed = None
        self.text = text


class Run180EyecatchSemanticLayoutTests(unittest.TestCase):
    def test_schema_parser_prefers_response_parsed(self):
        plan = {
            "title_lines": ["AIは重要。", "でも追いきれない。"],
            "title_font_size": 52,
            "title_line_gap": 14,
            "subheadline_lines": ["必要な変化だけを見る。"],
            "subheadline_font_size": 24,
        }
        self.assertEqual(plan, run180._parse_plan_response(_ParsedResponse(plan)))

    def test_schema_parser_keeps_text_compatibility(self):
        text = '{"title_lines":["AIは重要。"],"title_font_size":52,"title_line_gap":12,"subheadline_lines":["必要な変化だけを見る。"],"subheadline_font_size":24}'
        parsed = run180._parse_plan_response(_TextResponse(text))
        self.assertEqual(["AIは重要。"], parsed["title_lines"])

    def test_validation_accepts_semantic_partition_without_rewrite(self):
        headline = "AIは重要。でも正直、もう追いきれない。"
        subheadline = "増え続けるAI情報から、仕事に必要な変化だけを見る。"
        plan = {
            "title_lines": ["AIは重要。でも正直、", "もう追いきれない。"],
            "title_font_size": 52,
            "title_line_gap": 16,
            "subheadline_lines": ["増え続けるAI情報から、", "仕事に必要な変化だけを見る。"],
            "subheadline_font_size": 24,
        }
        validated = run180._validate_layout_plan(headline, subheadline, plan)
        self.assertIsNotNone(validated)
        self.assertEqual(plan["title_lines"], validated["title_lines"])

    def test_validation_rejects_model_copy_rewrite(self):
        headline = "AIは重要。でも正直、もう追いきれない。"
        subheadline = "必要な変化だけを見る。"
        plan = {
            "title_lines": ["AIは重要。", "でももう追いきれない。"],
            "title_font_size": 48,
            "title_line_gap": 12,
            "subheadline_lines": [subheadline],
            "subheadline_font_size": 24,
        }
        self.assertIsNone(run180._validate_layout_plan(headline, subheadline, plan))

    def test_request_is_one_call_minimal_thinking_and_not_deep_dive(self):
        source = inspect.getsource(run180._request_layout_plan)
        self.assertEqual(1, source.count("_generate_via_chat("))
        self.assertIn('"thinking_config": {"thinking_level": "minimal"}', source)
        self.assertIn('request_kind="eyecatch_layout"', source)
        self.assertIn("count_as_deep_dive=False", source)
        self.assertNotIn("retry", source.lower())

    def test_long_title_contract_uses_fuller_headline_and_42px_floor(self):
        source = inspect.getsource(run180.install)
        self.assertIn("max_chars=48", source)
        self.assertEqual(42, run180.TITLE_MIN_FONT)
        prompt = run180._layout_prompt("生成AIの速さ競争が変わる。小さなモデルは実務で使えるのか", "要約")
        self.assertIn("25文字以上", prompt)
        self.assertIn("エージェント", prompt)
        self.assertIn("途中で切らない", prompt)

    def test_fallback_is_direct_deterministic_renderer_not_run178_wrapper(self):
        source = inspect.getsource(run180.install)
        self.assertIn("deterministic_fallback = ee.generate_note_editorial_eyecatch", source)
        self.assertIn("return deterministic_fallback(", source)
        self.assertNotIn("return original(", source)

    def test_production_entrypoint_installs_run180_after_run179(self):
        source = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        run179_install = source.index("run179_eyecatch_font_refinement.install(pipeline_module)")
        run180_install = source.index("run180_eyecatch_semantic_layout.install(pipeline_module)")
        self.assertLess(run179_install, run180_install)


if __name__ == "__main__":
    unittest.main()
