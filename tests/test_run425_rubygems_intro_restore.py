import inspect
import unittest

import run425_rubygems_intro_restore as r425


class Run425RubyGemsIntroRestoreTests(unittest.TestCase):
    def test_restore_inserts_exact_three_part_intro_after_h1(self):
        old = f"# {r425.EXPECTED_NOTE_TITLE}\n\n### 元情報\n- source\n\n本文です。"
        what = "自律型AIエージェントが外部サービスを操作した事例です。"
        why = "目的達成の過程で外部サービスへの攻撃者となる運用リスクを示します。"
        conclusion = "今すぐ全面停止する段階ではありません。まず権限と通信制限を点検します。"
        out = r425.restore_intro(old, what, why, conclusion)
        self.assertEqual(out.count("## どんな内容？"), 1)
        self.assertEqual(out.count("**なぜ重要？**"), 1)
        self.assertEqual(out.count("**結論は？**"), 1)
        self.assertNotIn("何が出た？", out)
        self.assertLess(out.index("## どんな内容？"), out.index("### 元情報"))
        self.assertIn("本文です。", out)

    def test_restore_is_idempotent_only_for_same_authoritative_intro(self):
        old = f"# {r425.EXPECTED_NOTE_TITLE}\n\n### 元情報\n- source"
        what = "十分な内容説明として成立する文章です。"
        why = "十分な重要性説明として成立する文章です。"
        conclusion = "十分な結論として成立する文章です。"
        first = r425.restore_intro(old, what, why, conclusion)
        self.assertEqual(r425.restore_intro(first, what, why, conclusion), first)
        with self.assertRaises(r425.Run425RestoreError):
            r425.restore_intro(first, what, why + "変更", conclusion)

    def test_watch_conclusion_does_not_instruct_shutdown(self):
        action = "自社エージェントの外部通信制限と認証情報の分離状況を点検する。"
        conclusion = r425._conclusion_from_action(action)
        self.assertIn("全面停止・全面刷新する段階ではありません", conclusion)
        self.assertIn(action, conclusion)
        self.assertNotIn("今すぐ停止してください", conclusion)

    def test_exact_target_and_zero_model_private_only_contract(self):
        source = inspect.getsource(r425)
        self.assertIn(r425.PAGE_ID, source)
        self.assertIn(r425.EXPECTED_NOTE_TITLE, source)
        for forbidden in ("generate_content(", "_generate_via_chat(", "publish_note", "click_publish", "公開する"):
            self.assertNotIn(forbidden, source)
        self.assertIn('"gemini_calls": 0', source)
        self.assertIn('"public_release": False', source)


if __name__ == "__main__":
    unittest.main()
