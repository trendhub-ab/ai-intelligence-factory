from __future__ import annotations

import unittest
from pathlib import Path

import member_human_language_ux as base
import member_human_language_ux_v2 as ux2
import run213_member_topic_specificity as run213


class Run213MemberTopicSpecificityTests(unittest.TestCase):
    def setUp(self) -> None:
        run213.reset_runtime_stats()

    def _state(self) -> dict:
        return {
            "sync_id": "arxiv:2608.00001",
            "name": "Example Paper",
            "topic": "Example Paperの現在の機能・保守状況を確認しています。",
            "judgment_reason": "限定条件では有望だが、実運用条件での再現確認が必要。",
            "main_risk": "評価環境と実環境の差が残る。",
            "next_action": "次回レビュー時に再現性を確認する。",
            "status": "WATCH",
            "classification": "Deep Tech",
            "score": 68,
            "evidence": "https://arxiv.org/abs/2608.00001",
            "primary_url": "https://arxiv.org/abs/2608.00001",
        }

    def test_generic_topic_uses_only_current_specific_reason(self) -> None:
        state = self._state()
        out = run213.apply_current_topic_specificity(state)
        self.assertEqual(out["topic"], state["judgment_reason"])
        self.assertEqual(out["score"], state["score"])
        self.assertEqual(out["status"], state["status"])
        self.assertEqual(out["main_risk"], state["main_risk"])
        self.assertEqual(out["evidence"], state["evidence"])
        self.assertEqual(out["primary_url"], state["primary_url"])
        self.assertEqual(
            run213._RUNTIME_STATS["generic_topics_replaced_from_current_reason"], 1
        )

    def test_non_generic_topic_remains_authoritative(self) -> None:
        state = self._state()
        state["topic"] = "実運用へ移す前に再現性を見る価値がある研究です。"
        out = run213.apply_current_topic_specificity(state)
        self.assertEqual(out["topic"], state["topic"])
        self.assertEqual(
            run213._RUNTIME_STATS["generic_topics_replaced_from_current_reason"], 0
        )

    def test_missing_or_malformed_reason_fails_safe(self) -> None:
        for reason in (
            "",
            "運用設計の確認が必要ため、本番採用の前に小さく検証する判断が妥当です。",
        ):
            run213.reset_runtime_stats()
            state = self._state()
            state["judgment_reason"] = reason
            out = run213.apply_current_topic_specificity(state)
            self.assertTrue(base.GENERIC_TOPIC_RE.match(out["topic"]))
            self.assertEqual(
                run213._RUNTIME_STATS["generic_topics_replaced_from_current_reason"], 0
            )

    def test_known_hybrid_copy_is_repaired_without_touching_identifiers(self) -> None:
        state = self._state()
        state["topic"] = "実道路Safety 根拠を待つ。"
        state["judgment_reason"] = "現実タスクへのTransfer 根拠が重要。"
        out = run213.apply_current_topic_specificity(state)
        self.assertEqual(out["topic"], "実道路安全性の根拠を待つ。")
        self.assertEqual(
            out["judgment_reason"], "現実タスクへの実環境への転移を示す根拠が重要。"
        )
        self.assertEqual(out["name"], state["name"])
        self.assertEqual(out["primary_url"], state["primary_url"])
        self.assertEqual(run213._RUNTIME_STATS["hybrid_copy_repairs"], 2)

    def test_existing_role_separator_makes_reason_distinct_after_topic_promotion(self) -> None:
        state = run213.apply_current_topic_specificity(self._state())
        separated = ux2.refine_judgment_reason(state, {})
        self.assertNotEqual(separated, state["topic"])
        self.assertIn("評価環境と実環境の差", separated)

    def test_module_has_no_provider_path_and_layers_after_run212(self) -> None:
        source = Path("run213_member_topic_specificity.py").read_text(encoding="utf-8")
        lowered = source.lower()
        self.assertIn("run212.install()", source)
        self.assertNotIn("google.genai", lowered)
        self.assertNotIn("gemini_api_key", lowered)
        self.assertNotIn("generate_content", lowered)
        self.assertIn('result["zero_gemini_calls"] = True', source)


if __name__ == "__main__":
    unittest.main()
