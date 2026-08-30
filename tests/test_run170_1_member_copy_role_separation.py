import unittest

import member_human_language_ux as base
import member_human_language_ux_v2 as ux2


class TestRun1701MemberCopyRoleSeparation(unittest.TestCase):
    def test_legacy_three_role_reason_falls_back_to_natural_risk_reason(self):
        state = {
            "status": "TEST",
            "classification": "実務判断",
            "topic": "マルチエージェントが本当に必要な業務ならテスト価値は高い。",
            "next_action": "まず1つの実業務フローで単一エージェントとの品質・コスト差を測る。",
            "judgment_reason": (
                "マルチエージェントが本当に必要な業務ならテスト価値は高い。"
                "まず1つの実業務フローで単一エージェントとの品質・コスト差を測る。"
                "一次情報の現状を前提に、用途・保守性・運用コストまで含めて判断する。"
            ),
            "main_risk": "エージェント数とツール権限が増えるほど、コストや失敗箇所が増える。",
        }
        review = {"short_rationale": state["judgment_reason"]}
        reason = ux2.refine_judgment_reason(state, review)
        self.assertIn("本番導入の前に小さく試して確認します", reason)
        self.assertNotIn("一次情報の現状を前提に", reason)
        self.assertNotEqual(reason, state["topic"])
        self.assertNotIn("妥当", reason)

    def test_clean_distinct_single_sentence_reason_is_preserved(self):
        state = {
            "status": "ADOPT",
            "classification": "実務判断",
            "topic": "LLMやAIエージェントの評価まで用途が広がっている。",
            "next_action": "自社要件との適合を最終確認する。",
            "judgment_reason": "実験管理から生成AIの評価まで一つの基盤で扱える。",
            "main_risk": "セルフホスト時は運用負荷がある。",
        }
        self.assertEqual(
            ux2.refine_judgment_reason(state, {}),
            "実験管理から生成AIの評価まで一つの基盤で扱える。",
        )

    def test_deep_tech_duplicate_reason_gets_clear_positioning(self):
        state = {
            "status": "WATCH",
            "classification": "Deep Tech",
            "topic": "Chain-of-Thoughtを監査根拠として扱う運用への警告として有用。",
            "next_action": "今すぐ導入はせず、自社に関係する用途が出たときに最新の研究結果を確認する。",
            "judgment_reason": "Chain-of-Thoughtを監査根拠として扱う運用への警告として有用。",
            "main_risk": "",
        }
        reason = ux2.refine_judgment_reason(
            state,
            {"short_rationale": state["judgment_reason"]},
        )
        self.assertEqual(reason, "研究段階の情報なので、今は導入対象ではなく判断材料として追います。")

    def test_no_malformed_reason_pattern_in_fallback(self):
        state = {
            "status": "TEST",
            "classification": "実務判断",
            "topic": "",
            "next_action": "",
            "judgment_reason": "運用設計の確認が必要ため、本番採用の前に小さく検証する判断が妥当です。",
            "main_risk": "運用設計の確認が必要。",
        }
        reason = ux2.refine_judgment_reason(state, {})
        self.assertFalse(base.BAD_REASON_RE.search(reason))
        self.assertNotIn("必要ため", reason)


if __name__ == "__main__":
    unittest.main()
