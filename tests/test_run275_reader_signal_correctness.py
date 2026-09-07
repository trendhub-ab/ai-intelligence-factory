from __future__ import annotations

import inspect
from pathlib import Path
import types
import unittest

import reader_quality_precision as run275
import run226_reader_delight_planning as run226
import run228_reader_rhythm_planning as run228

ROOT = Path(__file__).resolve().parents[1]


def _base_signals(**overrides):
    base = {
        "technical_terms_per_1000_chars": 26.4,
        "opening_technical_terms_per_1000_chars": 26.4,
        "plain_language_bridge_present": True,
        "jargon_dense_paragraph_count": 0,
        "implementation_identifier_count": 0,
        "analogy_hits": 0,
        "analogy_used": False,
        "unexplained_jargon": [],
        "bridge_needed": True,
        "opening_non_engineer_access": "REVIEW",
        "reader_temperature_rhythm": "REVIEW",
        "max_explanatory_paragraph_run": 3,
        "jargon_translation": "GOOD",
        "non_engineer_core_clarity": "GOOD",
        "plain_language_bridge": "GOOD",
        "accessibility_issues": ["opening_non_engineer_access_weak", "reader_temperature_rhythm_weak"],
        "accessibility": "REVIEW",
        "enjoyment_issues": [],
        "reader_enjoyment": "GOOD",
        "narrative_pull": "REVIEW",
        "information_budget": "GOOD",
    }
    base.update(overrides)
    return base


class Run275ReaderSignalCorrectnessTests(unittest.TestCase):
    def test_run31_question_opening_is_recognized_without_relaxing_density_limit(self):
        article = (
            "実際に手元の開発環境でAIを動かすと、環境を壊してしまわないかという"
            "不安を抱くのではないでしょうか。ここでは安全に試す条件を見ます。"
        )
        fixed = run275.correct_reader_signals(article, _base_signals())
        self.assertEqual(fixed["opening_non_engineer_access"], "GOOD")
        self.assertNotIn("opening_non_engineer_access_weak", fixed["accessibility_issues"])

        dense = run275.correct_reader_signals(
            article,
            _base_signals(opening_technical_terms_per_1000_chars=49.5),
        )
        self.assertEqual(dense["opening_non_engineer_access"], "REVIEW")
        self.assertIn("opening_non_engineer_access_weak", dense["accessibility_issues"])

    def test_visible_headings_break_uninterrupted_explanation_run(self):
        para = "これは取得済みEvidenceの範囲で技術の仕組みと条件を説明する段落です。" * 5
        article = f"{para}\n\n## 安全性をどう見るか\n\n{para}\n\n## 導入判断\n\n{para}"
        fixed = run275.correct_reader_signals(article, _base_signals())
        self.assertEqual(fixed["max_explanatory_paragraph_run"], 1)
        self.assertEqual(fixed["reader_temperature_rhythm"], "GOOD")
        self.assertNotIn("reader_temperature_rhythm_weak", fixed["accessibility_issues"])

    def test_unheaded_dense_explanation_still_fails_rhythm(self):
        para = "これは取得済みEvidenceの範囲で技術の仕組みと条件を説明する段落です。" * 5
        article = f"{para}\n\n{para}\n\n{para}"
        fixed = run275.correct_reader_signals(article, _base_signals())
        self.assertEqual(fixed["max_explanatory_paragraph_run"], 3)
        self.assertEqual(fixed["reader_temperature_rhythm"], "REVIEW")
        self.assertIn("reader_temperature_rhythm_weak", fixed["accessibility_issues"])

    def test_later_valid_acronym_explanation_repairs_first_occurrence_false_positive(self):
        article = (
            "ant CLIを使って設定します。PCから作業できます。\n\n"
            "ここでCLI（文字入力で操作するツール）の役割を確認します。MCPも利用します。"
        )
        fixed = run275.correct_reader_signals(
            article,
            _base_signals(unexplained_jargon=["CLI", "PC", "MCP"]),
        )
        self.assertEqual(fixed["unexplained_jargon"], ["MCP"])
        self.assertIn("unexplained_acronyms", fixed["accessibility_issues"])

    def test_stable_entity_compounds_are_not_jargon_but_real_unexplained_token_remains(self):
        article = (
            "VT Codeを試します。VT Codeの設計を確認します。"
            "LM Studioと接続し、LM Studio側の設定も見ます。VRAMは別途確認が必要です。"
        )
        fixed = run275.correct_reader_signals(
            article,
            _base_signals(unexplained_jargon=["VT", "LM", "VRAM"]),
        )
        self.assertEqual(fixed["unexplained_jargon"], ["VRAM"])

    def test_actual_bobbin_particle_collision_is_blocked(self):
        pipe = types.SimpleNamespace(
            _reader_experience_signals=lambda article: _base_signals(),
            validate_human_appeal_gate=lambda parsed, peer_articles=None: ("ACCEPTABLE", []),
        )
        run275.install(pipe)
        state, issues = pipe.validate_human_appeal_gate(
            {"note_draft": "検証の結果、この誤検知がに減少しました。"}
        )
        self.assertEqual(state, "WEAK")
        self.assertTrue(any("particle_collision_ga_ni" in issue for issue in issues))

    def test_genuinely_dense_run31_shape_remains_review(self):
        article = (
            "この技術を使うとどうなるのでしょうか。\n\n## 実装\n\n"
            + ("CLI MCP CI CD SDK Runtime Agent Frameworkの実装条件を詳しく説明します。" * 8)
        )
        fixed = run275.correct_reader_signals(
            article,
            _base_signals(
                technical_terms_per_1000_chars=46.1,
                opening_technical_terms_per_1000_chars=49.5,
                jargon_dense_paragraph_count=13,
                information_budget="REVIEW",
                unexplained_jargon=["CLI", "MCP", "CI", "CD"],
                accessibility_issues=["technical_term_concentration", "jargon_translation_weak", "opening_non_engineer_access_weak"],
            ),
        )
        self.assertEqual(fixed["information_budget"], "REVIEW")
        self.assertEqual(fixed["jargon_translation"], "REVIEW")
        self.assertEqual(fixed["accessibility"], "REVIEW")
        self.assertEqual(fixed["opening_non_engineer_access"], "REVIEW")

    def test_prompt_change_is_subtractive_and_keeps_no_style_quota(self):
        delight = run226.editorial_planning_contract()
        rhythm = run228.reader_rhythm_contract()
        self.assertIn("読者の困りごと・迷い・選択", delight)
        self.assertIn("最初の段落を製品名・略語・実装名の説明から始めない", delight)
        self.assertIn("長い技術説明が2段落続いたら", rhythm)
        self.assertIn("正式名称・略語・実装名・フラグ名", rhythm)
        self.assertIn("回数ノルマを設けない", delight)
        self.assertIn("回数ノルマを設けない", rhythm)

    def test_overlay_adds_no_provider_or_model_call_site_and_is_installed_after_historical_stack(self):
        src = inspect.getsource(run275)
        self.assertNotIn("requests.get(", src)
        self.assertNotIn("requests.post(", src)
        self.assertNotIn("genai.Client(", src)
        self.assertNotIn("_generate_via_chat(", src)
        production = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("install_reader_quality_precision(pipeline)", production)
        self.assertGreater(
            production.index("install_reader_quality_precision(pipeline)"),
            production.index("install_runtime_layers(pipeline)"),
        )


if __name__ == "__main__":
    unittest.main()
