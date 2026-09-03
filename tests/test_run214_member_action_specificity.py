from __future__ import annotations

import unittest
from pathlib import Path

import member_human_language_ux as base
import run214_member_action_specificity as run214


class Run214MemberActionSpecificityTests(unittest.TestCase):
    def setUp(self) -> None:
        run214.reset_runtime_stats()

    def _state(self) -> dict:
        return {
            "name": "Example Research",
            "status": "WATCH",
            "classification": "Deep Tech",
            "category": "セキュリティ",
            "best_for": "大規模言語モデルの安全性を評価するAI安全チーム。",
            "topic": "高権限環境での監査設計に重要。",
            "main_risk": "評価条件が実環境へ一般化しない可能性がある。",
            "score": 72,
            "evidence": "https://example.com/source",
        }

    def test_watch_deep_tech_replaces_vague_opening_with_best_for_context(self) -> None:
        state = self._state()
        out = run214.contextualize_template_action(
            state, run214._WATCH_DEEP_TECH_TEMPLATE
        )
        self.assertTrue(out.startswith("「大規模言語モデルの安全性を評価するAI安全チーム」を想定し、"))
        self.assertIn("次回レビュー時に性能・再現性・公開実装", out)
        self.assertNotIn("自社に関係する用途を1つ決め", out)
        self.assertEqual(run214._RUNTIME_STATS["best_for_context_used"], 1)
        self.assertEqual(run214._RUNTIME_STATS["template_actions_refined"], 1)

    def test_current_topic_is_used_only_when_best_for_is_missing(self) -> None:
        state = self._state()
        state["best_for"] = ""
        out = run214.contextualize_template_action(
            state, run214._WATCH_DEEP_TECH_TEMPLATE
        )
        self.assertTrue(out.startswith("今回の論点「高権限環境での監査設計に重要」を踏まえ、"))
        self.assertEqual(run214._RUNTIME_STATS["topic_context_used"], 1)
        self.assertEqual(run214._RUNTIME_STATS["best_for_context_used"], 0)

    def test_explicit_non_template_action_is_never_rewritten(self) -> None:
        state = self._state()
        explicit = "Sandboxと権限境界を先に検証する。"
        out = run214.contextualize_template_action(state, explicit)
        self.assertEqual(out, explicit)
        self.assertEqual(run214._RUNTIME_STATS["template_actions_refined"], 0)

    def test_no_current_context_fails_safe(self) -> None:
        state = self._state()
        state["best_for"] = ""
        state["topic"] = "Example Researchの現在の機能・保守状況を確認しています。"
        out = run214.contextualize_template_action(
            state, run214._WATCH_DEEP_TECH_TEMPLATE
        )
        self.assertEqual(out, run214._WATCH_DEEP_TECH_TEMPLATE)
        self.assertEqual(
            run214._RUNTIME_STATS["template_actions_left_without_context"], 1
        )

    def test_long_context_is_not_mid_sentence_clipped(self) -> None:
        state = self._state()
        state["best_for"] = "あ" * 111 + "。"
        state["topic"] = "実環境での安全性評価に関係する研究。"
        out = run214.contextualize_template_action(
            state, run214._WATCH_DEEP_TECH_TEMPLATE
        )
        self.assertTrue(out.startswith("今回の論点「実環境での安全性評価に関係する研究」を踏まえ、"))
        self.assertNotIn("あ" * 20, out)

    def test_action_only_layer_does_not_mutate_decision_state(self) -> None:
        state = self._state()
        snapshot = dict(state)
        run214.contextualize_template_action(
            state,
            "代表タスクを20件程度用意し、小規模テストで品質・速度・費用を現行候補と比較する。",
        )
        self.assertEqual(state, snapshot)

    def test_module_has_no_provider_path_and_layers_after_run213(self) -> None:
        source = Path("run214_member_action_specificity.py").read_text(encoding="utf-8")
        lowered = source.lower()
        self.assertIn("run213.install()", source)
        self.assertNotIn("google.genai", lowered)
        self.assertNotIn("gemini_api_key", lowered)
        self.assertNotIn("generate_content", lowered)
        self.assertIn('result["zero_gemini_calls"] = True', source)


if __name__ == "__main__":
    unittest.main()
