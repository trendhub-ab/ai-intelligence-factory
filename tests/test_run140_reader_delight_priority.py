import inspect
import tempfile
import unittest
from pathlib import Path
import pipeline


class Run140ReaderDelightPriorityTests(unittest.TestCase):
    def test_prompt_makes_reader_delight_top_editorial_goal(self):
        prompt = pipeline.build_decision_prompt('x','https://example.com',1,'desc',source_context='primary evidence')
        self.assertIn('無料note記事の最上位編集目標', prompt)
        self.assertIn('「楽しい」「わかりやすい」「自分にも関係がある」', prompt)
        self.assertIn('技術レポートとして整っているだけでは完成としない', prompt)
        self.assertIn('Evidence・数値・制約・反証・Decisionの正確さは絶対に落とさず', prompt)

    def test_plain_but_dry_report_is_not_reader_delight_good(self):
        article = '''## 概要\nこの仕組みはAIへの権限を制限するものです。必要な範囲だけ許可することで管理しやすくなります。\n\n## 仕組み\n利用時には設定を確認します。条件に応じて権限を変更します。\n\n## 判断\n導入前に一次資料を確認します。'''
        sig = pipeline._reader_experience_signals(article)
        self.assertEqual('GOOD', sig['opening_non_engineer_access'])
        self.assertEqual('REVIEW', sig['reader_delight'])

    def test_fake_chatty_article_is_not_reader_delight_good(self):
        article = ('便利ですよね。気になりますよね。大事ですよね。' * 4) + '\n\nAIへの権限を必要な範囲だけにします。'
        sig = pipeline._reader_experience_signals(article)
        self.assertEqual('REVIEW_OVERUSE', sig['conversational_warmth'])
        self.assertEqual('REVIEW', sig['reader_delight'])

    def test_reader_first_story_can_be_reader_delight_good(self):
        article = '''仕事でAIに資料を渡そうとして、「このファイルにはアクセスできません」と止まったことはありませんか。AIが賢くなっても、何を見せてよいかを決める部分は意外と地味で、しかも重要です。\n\n今回の仕組みは、家の合鍵を必要な人にだけ渡す感覚に近いものです。AIにも必要な範囲だけ許可し、それ以上は触らせない。難しい名前より、まずこの役割を覚えておけば十分です。\n\nでは導入すれば安心かというと、そこは別の話です。既存システムとの互換性や一次資料の制約を確認し、小さな環境で試してから広げるのが現実的です。私なら、まず機密情報を含まない作業から比較します。'''
        sig = pipeline._reader_experience_signals(article)
        self.assertEqual('GOOD', sig['reader_delight'])
        self.assertEqual('GOOD', sig['plain_language_bridge'])
        self.assertEqual('GOOD', sig['reader_proximity'])

    def test_audit_exposes_reader_delight(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'audit.md'
            pipeline._write_article_audit_markdown(str(out), 'スマホで困ったことはありませんか。必要な範囲だけ許可する話です。', {'status':'READY'})
            text = out.read_text(encoding='utf-8')
            self.assertIn('- Reader Delight:', text)

    def test_no_new_gemini_call_site(self):
        src = inspect.getsource(pipeline)
        self.assertEqual(7, src.count('_generate_via_chat('))
        self.assertEqual(1, src.count('genai.Client('))


if __name__ == '__main__':
    unittest.main()
