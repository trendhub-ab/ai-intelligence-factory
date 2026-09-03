import importlib
import unittest

import member_human_language_ux as base
import run214_member_action_specificity as run214
import run215_member_action_final_dedup as run215


class Run215MemberActionFinalDedupTests(unittest.TestCase):
    def setUp(self):
        importlib.reload(run214)
        importlib.reload(run215)

    def test_generic_research_best_for_yields_specific_topic(self):
        state = {
            "best_for": "論文の対象課題が自社ユースケースと一致し、既存手法との比較を小規模に再現できる研究・開発チーム。",
            "topic": "長期Agent運用でHuman-in-the-loopを入れたい組織には有望。実運用の操作負荷を確認する。",
        }
        source, focus = run215._specific_context(state)
        self.assertEqual("topic", source)
        self.assertIn("Human-in-the-loop", focus)

    def test_generic_roadmap_best_for_yields_specific_topic(self):
        state = {
            "best_for": "関連分野の技術選定・リスク評価・研究ロードマップを行い、次に試す候補を比較したいチーム。",
            "topic": "身体エージェントの計画破綻を減らす設計として注目できる。",
        }
        source, focus = run215._specific_context(state)
        self.assertEqual("topic", source)
        self.assertIn("身体エージェント", focus)

    def test_specific_best_for_still_has_priority(self):
        state = {
            "best_for": "自動研究の幻覚低減と実験監査を担当するAI研究チーム。",
            "topic": "別の具体的な話題。",
        }
        source, focus = run215._specific_context(state)
        self.assertEqual("best_for", source)
        self.assertIn("実験監査", focus)

    def test_generic_best_for_is_preserved_when_topic_is_not_specific(self):
        generic_best_for = "論文の対象課題が自社ユースケースと一致し、既存手法との比較を小規模に再現できる研究・開発チーム。"
        state = {
            "best_for": generic_best_for,
            "topic": "最近の変化を確認し、いま検討する価値があるかを見る。",
        }
        source, focus = run215._specific_context(state)
        self.assertEqual("best_for", source)
        self.assertTrue(focus.startswith("論文の対象課題"))

    def test_explicit_action_remains_untouched(self):
        action = "vLLM/SGLangを第一比較にし、ローカル用途はllama.cpp等も含めて再選定する。"
        state = {
            "best_for": "論文の対象課題が自社ユースケースと一致し、既存手法との比較を小規模に再現できる研究・開発チーム。",
            "topic": "具体的な話題。",
        }
        self.assertEqual(action, run214.contextualize_template_action(state, action))

    def test_template_action_becomes_topic_specific_after_install(self):
        run215.install()
        state = {
            "best_for": "論文の対象課題が自社ユースケースと一致し、既存手法との比較を小規模に再現できる研究・開発チーム。",
            "topic": "調査・リサーチAgentの根拠統合品質を改善したい用途で試験価値がある。",
        }
        action = "代表的な1つの処理だけを検証環境で動かし、導入前後の速度・費用・運用負荷を比較する。"
        out = run214.contextualize_template_action(state, action)
        self.assertIn("調査・リサーチAgent", out)
        self.assertNotIn("論文の対象課題が自社ユースケース", out)
        self.assertTrue(out.endswith(action))

    def test_no_provider_or_gemini_path(self):
        source = open("run215_member_action_final_dedup.py", encoding="utf-8").read()
        forbidden = ["GEMINI_API_KEY", "google.genai", "generate_content(", "Client("]
        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
