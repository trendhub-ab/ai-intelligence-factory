import os, sys, types, unittest
from unittest.mock import patch
from pathlib import Path
os.environ.setdefault('GEMINI_API_KEY','test-key')
os.environ.setdefault('GH_PAT','test-token')
os.environ.setdefault('GEMINI_QUOTA_PROJECT_ID','test-project')
try:
    from google import genai  # noqa
except ImportError:
    google_mod = sys.modules.get('google') or types.ModuleType('google')
    genai_mod = types.ModuleType('google.genai')
    errors_mod = types.ModuleType('google.genai.errors')
    class APIError(Exception): pass
    class Client:
        def __init__(self, **_kwargs): self.chats = types.SimpleNamespace(create=lambda **_kw: None)
    genai_mod.Client = Client; errors_mod.APIError = APIError; google_mod.genai = genai_mod
    sys.modules.update({'google':google_mod,'google.genai':genai_mod,'google.genai.errors':errors_mod})
import pipeline

class Run133ReaderFirstEditorialCompressionTests(unittest.TestCase):
    def test_prompt_prioritizes_reader_first_compression_without_extra_prose(self):
        prompt = pipeline.build_decision_prompt(
            'example/project','https://example.com/project',123,'desc',source='GitHub',
            source_context='official evidence context', evidence_metadata={}, freshness={}
        )
        self.assertIn('原則2〜3個に絞る', prompt)
        self.assertIn('一次情報に存在する技術名を全部ARTICLEへ転記することは禁止', prompt)
        self.assertIn('硬い説明が2段落続いたら次の段落', prompt)
        self.assertIn('有料会員向けProduct Review / Notion DBの情報密度をARTICLE圧縮に合わせて削らない', prompt)

    def test_reader_signals_detect_dense_cold_technical_article(self):
        article = '''## 技術詳細\nDPoP WIF RFC2217 SEP-2575 SEP-2567 CIMD ID-JAG MicroVM CCACHE XTENSA RISC-V を利用します。\n\n''' + ('技術仕様とアテンションウィンドウとプロトコルの詳細を説明します。' * 12) + '\n\n' + ('実装仕様を詳細に説明します。' * 12)
        sig = pipeline._reader_experience_signals(article)
        self.assertEqual('REVIEW', sig['opening_non_engineer_access'])
        self.assertEqual('REVIEW', sig['implementation_detail_load'])
        self.assertIn('opening_non_engineer_access_weak', sig['accessibility_issues'])

    def test_reader_signals_accept_plain_reader_first_opening(self):
        article = '''## まず何が変わる？\nスマホで「このアプリに写真を見せてもいいですか？」と聞かれたことがありますよね。今回の仕組みも、要するにAIへ渡す権限を必要な範囲に絞る話です。\n\n技術的にはDPoPという仕組みを使います。名前は難しそうですが、盗まれた認証情報をそのまま使い回しにくくするための仕組みです。\n\n導入時は既存の認証方式との互換性を確認する必要があります。'''
        sig = pipeline._reader_experience_signals(article)
        self.assertEqual('GOOD', sig['opening_non_engineer_access'])
        self.assertEqual('GOOD', sig['reader_proximity'])

    def test_information_budget_does_not_review_length_alone(self):
        article = '読者に分かる普通の文章です。' * 300
        sig = pipeline._reader_experience_signals(article)
        self.assertGreater(sig['article_char_count'], 3200)
        self.assertEqual('GOOD', sig['information_budget'])
        self.assertTrue(sig['soft_only'])

    def test_article_audit_exposes_run133_metrics(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / 'audit.md')
            pipeline._write_article_audit_markdown(
                path,
                'スマホで困ったことはありませんか。これは分かりやすい説明です。',
                {'stage':'test'},
            )
            txt = Path(path).read_text(encoding='utf-8')
        self.assertIn('- Opening Non-Engineer Access:', txt)
        self.assertIn('- Implementation Detail Load:', txt)
        self.assertIn('- Reader Temperature Rhythm:', txt)

if __name__ == '__main__':
    unittest.main()
