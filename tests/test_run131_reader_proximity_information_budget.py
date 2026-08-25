import os, sys, types, unittest, tempfile
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

class Run131ReaderProximityInformationBudgetTests(unittest.TestCase):
    def test_prompt_requires_functional_proximity_without_fixed_catchphrase(self):
        prompt = pipeline.build_decision_prompt('x','https://example.com',1,'desc',source_context='primary evidence')
        self.assertIn('原則1〜3箇所', prompt)
        self.assertIn('「読者との距離が近くなる一文」', prompt)
        self.assertIn('固定語でもない', prompt)
        self.assertIn('親しみやすさのために文章を足し算しない', prompt)
        self.assertIn('原則2〜3個に絞る', prompt)
        self.assertIn('Evidence、数値、制約、比較、反証、Decisionは先に削らない', prompt)
        self.assertIn('Fact Gate / Source Boundaryの表面積を増やさない', prompt)

    def test_dry_everyday_noun_no_longer_counts_as_warmth(self):
        article='''スマホの権限設定ではアクセス範囲を管理します。DPoPはトークン所有者を確認する仕組みです。\n\n## 判断\n一次資料の制約を確認して比較します。'''
        sig=pipeline._reader_experience_signals(article)
        self.assertEqual('REVIEW_MISSING', sig['conversational_warmth'])
        self.assertEqual('REVIEW_MISSING', sig['reader_proximity'])
        self.assertEqual(0, sig['reader_proximity_moment_count'])
        self.assertIn('reader_proximity_missing', sig['enjoyment_issues'])

    def test_natural_reader_question_counts_as_proximity(self):
        article='''スマホで「写真へのアクセスを許可しますか？」と聞かれたことはありませんか。AIの権限管理も発想は近く、必要な範囲だけを許可します。\n\n## 判断\n一次資料の制約を確認して比較します。'''
        sig=pipeline._reader_experience_signals(article)
        self.assertEqual('GOOD', sig['conversational_warmth'])
        self.assertEqual('GOOD', sig['reader_proximity'])
        self.assertGreaterEqual(sig['reader_proximity_moment_count'],1)

    def test_friendly_translation_counts_without_desuyone(self):
        article='''名前は難しそうですが、やっていることは意外と単純です。microVMはAIに必要な作業領域だけを渡す小さな隔離環境です。\n\n## 判断\n一次資料の制約を確認して比較します。'''
        sig=pipeline._reader_experience_signals(article)
        self.assertEqual('GOOD', sig['reader_proximity'])
        self.assertGreaterEqual(sig['reader_proximity_moment_count'],1)

    def test_information_budget_flags_dense_double_explanation_only_softly(self):
        dense = ('Transformer Attention Routing Adapter Cache Distillation Gradient Token Policy Model '
                 'アテンションルーティングキャッシュアダプタモデルを説明します。')
        article = '\n\n'.join([dense + ' たとえば身近な箱のようなものです。' for _ in range(4)])
        sig=pipeline._reader_experience_signals(article)
        self.assertEqual('REVIEW', sig['information_budget'])
        self.assertTrue(sig['soft_only'])

    def test_audit_exposes_new_signals(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'a.md'
            pipeline._write_article_audit_markdown(str(out),'見たことはありませんか。必要な範囲だけ許可します。',{'status':'READY'})
            txt=out.read_text(encoding='utf-8')
            self.assertIn('- Reader Proximity:',txt)
            self.assertIn('- Reader Proximity Moment Count:',txt)
            self.assertIn('- Information Budget:',txt)

    def test_no_new_gemini_call_site_or_client(self):
        py=Path(pipeline.__file__).read_text(encoding='utf-8')
        self.assertEqual(7,py.count('_generate_via_chat('))
        self.assertEqual(1,py.count('genai.Client('))

if __name__=='__main__': unittest.main()
