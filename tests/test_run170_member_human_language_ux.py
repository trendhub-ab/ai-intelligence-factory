import unittest

import member_human_language_ux as ux
import member_presentation_body_sync as body


class TestRun170MemberHumanLanguageUX(unittest.TestCase):
    def base_state(self):
        return {
            "sync_id": "x:1",
            "name": "Example",
            "plain_summary": "LLMをPoCで評価するMLOps基盤。",
            "status": "TEST",
            "score": 84,
            "judgment_reason": "運用設計の確認が必要ため、本番採用の前に小さく検証する判断が妥当です。",
            "topic": "Exampleの現在の機能・保守状況を確認しています。",
            "next_action": "代表業務を1つ選び、小さく試して効果と運用負荷を確認する。",
            "main_risk": "運用設計の確認が必要。",
            "best_for": "AI導入チーム。",
            "avoid_for": "単発利用。",
            "confidence": "高",
            "readiness": "高",
            "category": "開発ツール",
            "classification": "実務判断",
            "change_reason": "",
            "evidence": "https://example.com/source",
            "primary_url": "https://example.com",
            "related_article": "",
        }

    def test_review_copy_replaces_generic_topic_and_bad_reason(self):
        state = self.base_state()
        reviewed = {
            "plain_summary": "LLMの実験と評価をまとめて管理するMLOps基盤。",
            "topic_trigger": "AIエージェントの評価まで用途が広がっている。",
            "short_rationale": "実務で使える機能は多いが、運用条件は自社環境で確認したい。",
            "main_risk": "自社運用時の権限設計が必要。",
            "best_for": "AI開発チーム。",
            "avoid_for": "管理が不要な単発作業。",
        }
        out = ux.humanize_state(state, reviewed)
        self.assertEqual(out["topic"], "AIエージェントの評価まで用途が広がっている。")
        self.assertNotIn("必要ため", out["judgment_reason"])
        self.assertNotIn("妥当", out["judgment_reason"])
        self.assertIn("大規模言語モデル（LLM）", out["plain_summary"])
        self.assertIn("AI・機械学習の開発・運用管理（MLOps）", out["plain_summary"])
        self.assertIn("小規模な試行（PoC）", ux._humanize_terms("PoC"))
        self.assertNotEqual(out["next_action"], state["next_action"])

    def test_generic_deep_tech_boilerplate_is_not_exposed(self):
        state = self.base_state()
        state.update(
            {
                "classification": "Deep Tech",
                "status": "WATCH",
                "main_risk": ux.GENERIC_DEEP_RISK,
                "best_for": ux.GENERIC_DEEP_BEST,
                "avoid_for": ux.GENERIC_DEEP_AVOID,
                "next_action": "次回レビューまで監視し、成熟度・保守状況の変化を確認する。",
            }
        )
        reviewed = {
            "plain_summary": "視覚モデルの誤りを減らす研究。",
            "topic_trigger": "実環境への移行時の誤差が課題になっている。",
            "short_rationale": "研究として有望だが、実環境への移行では誤差が残る。",
        }
        out = ux.humanize_state(state, reviewed)
        self.assertEqual(out["main_risk"], "実環境への移行では誤差が残る。")
        self.assertEqual(out["best_for"], "")
        self.assertEqual(out["avoid_for"], "")
        self.assertIn("今すぐ導入はせず", out["next_action"])
        self.assertNotIn("監視し、成熟度", out["next_action"])

    def test_detail_body_starts_with_what_then_decision(self):
        state = ux.humanize_state(self.base_state(), {})
        blocks = ux._human_build_children(state)
        fingerprints = [(block.get("type"), body._block_text(block)) for block in blocks]
        headings = [text for block_type, text in fingerprints if block_type == "heading_3"]
        self.assertGreaterEqual(len(headings), 4)
        self.assertEqual(headings[0], "これは何？")
        self.assertEqual(headings[1], "いまの判断")
        self.assertEqual(headings[2], "なぜ今見る？")
        self.assertEqual(headings[3], "次にやること")
        visible_text = "\n".join(text for _, text in fingerprints)
        self.assertIn("まず試す（TEST）", visible_text)
        self.assertNotIn("判断が妥当", visible_text)

    def test_status_labels_are_customer_language(self):
        self.assertEqual(ux.STATUS_HUMAN["ADOPT"], "導入を検討")
        self.assertEqual(ux.STATUS_HUMAN["TEST"], "まず試す")
        self.assertEqual(ux.STATUS_HUMAN["WATCH"], "様子を見る")
        self.assertEqual(ux.STATUS_HUMAN["AVOID"], "見送る")


if __name__ == "__main__":
    unittest.main()
