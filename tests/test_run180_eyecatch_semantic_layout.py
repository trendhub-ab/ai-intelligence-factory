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
            "eyecatch_title": "AIは重要。でも追いきれない。",
            "title_lines": ["AIは重要。", "でも追いきれない。"],
            "title_font_size": 60,
            "title_line_gap": 14,
            "subheadline_lines": ["必要な変化だけを見る。"],
            "subheadline_font_size": 24,
            "highlight_text": "でも追いきれない。",
        }
        self.assertEqual(plan, run180._parse_plan_response(_ParsedResponse(plan)))

    def test_schema_parser_keeps_text_compatibility(self):
        text = '{"eyecatch_title":"AIは重要。","title_lines":["AIは重要。"],"title_font_size":60,"title_line_gap":12,"subheadline_lines":["必要な変化だけを見る。"],"subheadline_font_size":24,"highlight_text":""}'
        parsed = run180._parse_plan_response(_TextResponse(text))
        self.assertEqual("AIは重要。", parsed["eyecatch_title"])

    def test_validation_accepts_bounded_editorial_title_compression(self):
        source_title = "Polars 2.0が目指す「静かな進化」は、なぜデータ開発の現場に大きな影響を与えるのか。"
        eyecatch_title = "Polars 2.0の「静かな進化」がデータ開発を変える。"
        subheadline = "高速データ処理の変化を、実務の視点から読み解く。"
        plan = {
            "eyecatch_title": eyecatch_title,
            "title_lines": ["Polars 2.0の", "「静かな進化」が", "データ開発を変える。"],
            "title_font_size": 64,
            "title_line_gap": 14,
            "subheadline_lines": ["高速データ処理の変化を、", "実務の視点から読み解く。"],
            "subheadline_font_size": 24,
            "highlight_text": "データ開発を変える。",
        }
        validated = run180._validate_layout_plan(source_title, subheadline, plan)
        self.assertIsNotNone(validated)
        self.assertEqual(eyecatch_title, validated["eyecatch_title"])
        self.assertEqual("データ開発を変える。", validated["highlight_text"])
        self.assertGreaterEqual(validated["title_font_size"], 52)

    def test_validation_rejects_title_lines_that_rewrite_eyecatch_title(self):
        source_title = "AIは重要。でも正直、もう追いきれない。"
        subheadline = "必要な変化だけを見る。"
        plan = {
            "eyecatch_title": "AIは重要。でも追いきれない。",
            "title_lines": ["AIは重要。", "でももう追いきれない。"],
            "title_font_size": 60,
            "title_line_gap": 12,
            "subheadline_lines": [subheadline],
            "subheadline_font_size": 24,
            "highlight_text": "追いきれない。",
        }
        self.assertIsNone(run180._validate_layout_plan(source_title, subheadline, plan))

    def test_validation_rejects_loss_of_product_or_version_identifier(self):
        source_title = "Polars 2.0の新しいデータ処理は何が変わるのか。"
        plan = {
            "eyecatch_title": "データ処理の常識が変わる。",
            "title_lines": ["データ処理の", "常識が変わる。"],
            "title_font_size": 66,
            "title_line_gap": 12,
            "subheadline_lines": ["要約"],
            "subheadline_font_size": 24,
            "highlight_text": "常識が変わる。",
        }
        self.assertIsNone(run180._validate_layout_plan(source_title, "要約", plan))

    def test_validation_rejects_title_over_hard_character_limit(self):
        source_title = "AIに関する長い記事タイトル"
        too_long = "あ" * (run180.EYECATCH_TITLE_HARD_MAX_CHARS + 1)
        plan = {
            "eyecatch_title": too_long,
            "title_lines": [too_long[:27], too_long[27:]],
            "title_font_size": 52,
            "title_line_gap": 12,
            "subheadline_lines": ["要約"],
            "subheadline_font_size": 24,
            "highlight_text": "ああああ",
        }
        self.assertIsNone(run180._validate_layout_plan(source_title, "要約", plan))

    def test_request_is_one_call_minimal_thinking_and_not_deep_dive(self):
        source = inspect.getsource(run180._request_layout_plan)
        self.assertEqual(1, source.count("_generate_via_chat("))
        self.assertIn('"thinking_config": {"thinking_level": "minimal"}', source)
        self.assertIn('request_kind="eyecatch_layout"', source)
        self.assertIn("count_as_deep_dive=False", source)
        self.assertNotIn("retry", source.lower())

    def test_title_contract_uses_fuller_source_and_52px_floor(self):
        source = inspect.getsource(run180.install)
        self.assertIn("_source_title_for_direction(title)", source)
        self.assertEqual(52, run180.TITLE_MIN_FONT)
        self.assertEqual(45, run180.EYECATCH_TITLE_TARGET_MAX_CHARS)
        self.assertEqual(52, run180.EYECATCH_TITLE_HARD_MAX_CHARS)
        prompt = run180._layout_prompt(
            "生成AIの速さ競争が変わる。小さなモデルは実務で使えるのか", "要約"
        )
        self.assertIn("理想15〜45文字", prompt)
        self.assertIn("SEO用の記事タイトルとアイキャッチ用タイトルは同一でなくてよい", prompt)
        self.assertIn("52〜76px", prompt)
        self.assertIn("画像、イラスト、背景、カテゴリ、日付、ロゴ、ビジュアル構造には一切触れない", prompt)

    def test_subheadline_and_visual_fallback_paths_remain_existing_contract(self):
        source = inspect.getsource(run180.install)
        self.assertIn("editorial_subheadline(summary, existing_headline)", source)
        self.assertIn("deterministic_fallback = ee.generate_note_editorial_eyecatch", source)
        self.assertIn("return deterministic_fallback(", source)
        self.assertNotIn("return original(", source)

    def test_production_entrypoint_installs_run180_after_run179(self):
        source = (ROOT / "runtime_layers.py").read_text(encoding="utf-8")
        run179_install = source.index("run179_eyecatch_font_refinement.install(pipeline_module)")
        run180_install = source.index("run180_eyecatch_semantic_layout.install(pipeline_module)")
        self.assertLess(run179_install, run180_install)


if __name__ == "__main__":
    unittest.main()
