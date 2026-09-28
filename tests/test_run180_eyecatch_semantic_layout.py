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
    def test_long_title_without_valid_plan_never_renders_truncated_fallback(self):
        from unittest.mock import patch
        from types import SimpleNamespace

        source = "Show HN: VT Code – My attempt at building a coding-agent harness：いま何を判断材料にするべきか"
        module = SimpleNamespace(SYNTHETIC_REGRESSION_MODE=True)
        with patch.object(run180.ee, "generate_note_editorial_eyecatch") as legacy:
            run180.install(module)
            with self.assertRaisesRegex(ValueError, "complete eyecatch title"):
                module.generate_note_editorial_eyecatch(source, "概要", "/tmp/not-written.png")
            legacy.assert_not_called()
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

    def test_validation_rejects_openai_title_cut_off_at_comma(self):
        source_title = "AIの巨人はどこから生まれたのか。2015年、非営利スタートアップ「OpenAI」が掲げた理想と出発点。"
        bad_title = "AIの巨人はどこから生まれたのか。2015年、"
        plan = {
            "eyecatch_title": bad_title,
            "title_lines": ["AIの巨人は", "どこから生まれたのか。", "2015年、"],
            "title_font_size": 60,
            "title_line_gap": 12,
            "subheadline_lines": ["原点を読む。"],
            "subheadline_font_size": 24,
            "highlight_text": "2015年、",
        }
        self.assertIsNone(run180._validate_layout_plan(source_title, "原点を読む。", plan))

    def test_validation_accepts_complete_openai_visual_copy(self):
        source_title = "AIの巨人はどこから生まれたのか。2015年、非営利スタートアップ「OpenAI」が掲げた理想と出発点。"
        good_title = "OpenAI、2015年の原点。"
        plan = {
            "eyecatch_title": good_title,
            "title_lines": ["OpenAI、", "2015年の原点。"],
            "title_font_size": 68,
            "title_line_gap": 12,
            "subheadline_lines": ["原点を読む。"],
            "subheadline_font_size": 24,
            "highlight_text": "2015年の原点。",
        }
        validated = run180._validate_layout_plan(source_title, "原点を読む。", plan)
        self.assertIsNotNone(validated)
        self.assertEqual(good_title, validated["eyecatch_title"])

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


    def test_observed_ga_title_allows_semantic_compression_without_freezing_sentence_words(self):
        source_title = "Power your agents: Gemini 3.8 Live with Live Avatar is now generally available"
        required = run180._required_source_tokens(source_title)
        self.assertIn("Gemini", required)
        self.assertIn("3.8", required)
        self.assertIn("Live", required)
        self.assertIn("Avatar", required)
        for generic in ("Power", "your", "agents", "generally", "available"):
            self.assertNotIn(generic, required)

        eyecatch_title = "Gemini 3.8 Live with Live Avatar、一般提供開始。"
        plan = {
            "eyecatch_title": eyecatch_title,
            "title_lines": ["Gemini 3.8 Live", "with Live Avatar、", "一般提供開始。"],
            "title_font_size": 52,
            "title_line_gap": 12,
            "subheadline_lines": ["一般提供の意味を確認する。"],
            "subheadline_font_size": 24,
            "highlight_text": "一般提供開始。",
        }
        validated = run180._validate_layout_plan(
            source_title, "一般提供の意味を確認する。", plan
        )
        self.assertIsNotNone(validated)
        self.assertEqual(eyecatch_title, validated["eyecatch_title"])

    def test_ascii_wrap_guard_distinguishes_word_boundary_from_token_split(self):
        source = "Gemini 3.8 Live with Live Avatar、一般提供開始。"
        self.assertFalse(
            run180._ascii_token_split(
                ["Gemini 3.8 Live", "with Live Avatar、", "一般提供開始。"],
                source,
            )
        )
        self.assertTrue(
            run180._ascii_token_split(
                ["Open", "AI、一般提供開始。"],
                "OpenAI、一般提供開始。",
            )
        )

    def test_observed_ga_title_has_zero_provider_semantic_fallback(self):
        source_title = "Power your agents: Gemini 3.8 Live with Live Avatar is now generally available"
        self.assertEqual(
            "Gemini 3.8 Live with Live Avatar、一般提供開始。",
            run180._deterministic_safe_semantic_title(source_title),
        )
        plan = run180._deterministic_semantic_fallback_plan(
            source_title,
            "音声と映像を組み合わせた対話AIの一般提供について整理します。",
        )
        self.assertIsNotNone(plan)
        self.assertEqual(
            "Gemini 3.8 Live with Live Avatar、一般提供開始。",
            plan["eyecatch_title"],
        )
        self.assertNotIn("…", "".join(plan["title_lines"]))
        self.assertLessEqual(len(plan["title_lines"]), 3)

    def test_semantic_fallback_refuses_unrecognized_long_title(self):
        source_title = "A long English title about an AI system with no exact availability wording"
        self.assertEqual("", run180._deterministic_safe_semantic_title(source_title))
        self.assertIsNone(
            run180._deterministic_semantic_fallback_plan(source_title, "要約")
        )

    def test_sgps_bounded_title_fallback_preserves_every_character(self):
        title = "1台のGPUで実機が動く。ロボットAIの学習コストを激変させる「SGPS」の衝撃。"
        plan = run180._deterministic_complete_title_plan(
            title,
            "SGPSは視覚方策学習の計算負荷を下げる研究手法です。",
        )
        self.assertIsNotNone(plan)
        self.assertEqual(title, plan["eyecatch_title"])
        self.assertEqual(title, "".join(plan["title_lines"]))
        self.assertNotIn("…", "".join(plan["title_lines"]))
        self.assertLessEqual(len(plan["title_lines"]), 3)

    def test_run169_ready_title_complete_fallback_preserves_full_title(self):
        title = "AIが「目的のために手段を選ばず」セキュリティを突破した日。OpenAIが直面した自律モデルの暴走。"
        plan = run180._deterministic_complete_title_plan(
            title,
            "AIエージェントの自律的な攻撃行動と、企業が考えるべき安全境界を整理します。",
        )
        self.assertIsNotNone(plan)
        self.assertEqual(title, plan["eyecatch_title"])
        self.assertEqual(
            run180.r178._canonical_partition_text(title),
            run180.r178._canonical_partition_text("".join(plan["title_lines"])),
        )
        self.assertLessEqual(len(plan["title_lines"]), 3)
        self.assertGreaterEqual(plan["title_font_size"], 44)
        self.assertFalse(run180._ascii_token_split(plan["title_lines"]))
        self.assertNotRegex("".join(plan["title_lines"]), r"[.…]{2,}|…")

    def test_complete_fallback_is_used_before_legacy_truncating_renderer(self):
        source = inspect.getsource(run180.install)
        complete_pos = source.index("_deterministic_complete_title_plan(title, summary)")
        legacy_pos = source.index("return deterministic_fallback(")
        self.assertLess(complete_pos, legacy_pos)

    def test_complete_fallback_does_not_semantically_shorten_overlong_titles(self):
        title = "長いタイトル" * 12
        self.assertIsNone(run180._deterministic_complete_title_plan(title, "要約"))

    def test_request_uses_36_then_35_fallback_and_not_deep_dive(self):
        calls = []
        plan = {
            "eyecatch_title": "AIは重要。",
            "title_lines": ["AIは重要。"],
            "title_font_size": 60,
            "title_line_gap": 12,
            "subheadline_lines": ["必要な変化だけを見る。"],
            "subheadline_font_size": 24,
            "highlight_text": "",
        }

        def provider(model_name, prompt, **kwargs):
            calls.append((model_name, kwargs))
            if model_name == "gemini-3.6-flash":
                raise RuntimeError("primary unavailable")
            return _ParsedResponse(plan)

        class Logger:
            def warning(self, *_args, **_kwargs):
                pass

        fake = type("FakePipeline", (), {
            "SYNTHETIC_REGRESSION_MODE": False,
            "_generate_via_chat": staticmethod(provider),
            "logger": Logger(),
        })()

        parsed = run180._request_layout_plan(fake, "AIは重要。", "必要な変化だけを見る。")
        self.assertEqual(plan, parsed)
        self.assertEqual(
            ["gemini-3.6-flash", "gemini-3.5-flash"],
            [model for model, _kwargs in calls],
        )
        for _model, kwargs in calls:
            self.assertEqual("eyecatch_layout", kwargs["request_kind"])
            self.assertFalse(kwargs["count_as_deep_dive"])

        source = inspect.getsource(run180._request_layout_plan)
        self.assertEqual(1, source.count("_generate_via_chat("))
        self.assertIn('"thinking_config": {"thinking_level": "minimal"}', source)

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
        self.assertIn("自然な独立コピーとして意味が完結", prompt)
        self.assertIn("元タイトルの前半を文字数で切り取っただけの断片は禁止", prompt)
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
