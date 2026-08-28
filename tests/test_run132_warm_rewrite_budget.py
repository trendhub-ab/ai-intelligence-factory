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

class Run132WarmRewriteBudgetTests(unittest.TestCase):
    def test_prompt_makes_proximity_a_generation_completion_condition(self):
        prompt = pipeline.build_decision_prompt('x','https://example.com',1,'desc',source_context='primary evidence')
        self.assertIn('無料note記事の完成条件として扱う', prompt)
        self.assertIn('硬い説明が2段落続いたら次の段落', prompt)
        self.assertIn('人間の言葉へ戻す', prompt)
        self.assertIn('置換であり追記ではない', prompt)

    def test_prompt_protects_evidence_before_editorial_compression(self):
        prompt = pipeline.build_decision_prompt('x','https://example.com',1,'desc',source_context='primary evidence')
        self.assertIn('Evidence、数値、制約、比較、反証、Decisionは先に削らない', prompt)
        self.assertIn('Decisionに不要な内部実装、規格番号・略語の列挙、重複説明', prompt)

    def test_long_article_alone_does_not_force_information_budget_review(self):
        article = ('名前は難しそうですが、やっていることは意外と単純です。'
                   '必要な範囲だけ許可する仕組みです。') + (' 技術上の条件を一次資料で確認します。' * 260)
        sig = pipeline._reader_experience_signals(article)
        self.assertGreater(sig['article_char_count'], 3400)
        self.assertEqual('GOOD', sig['information_budget'])
        self.assertTrue(sig['soft_only'])

    def test_normal_length_warm_article_keeps_good_budget(self):
        article = ('スマホで「写真へのアクセスを許可しますか？」と聞かれたことはありませんか。'
                   '必要な範囲だけ許可する考え方です。\n\n## 判断\n一次資料の条件を確認して比較します。')
        sig = pipeline._reader_experience_signals(article)
        self.assertEqual('GOOD', sig['reader_proximity'])
        self.assertEqual('GOOD', sig['information_budget'])
        self.assertLess(sig['article_char_count'], 3400)

    def test_audit_exposes_length_and_proximity_density(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'a.md'
            pipeline._write_article_audit_markdown(str(out),'見たことはありませんか。必要な範囲だけ許可します。',{'status':'READY'})
            txt=out.read_text(encoding='utf-8')
            self.assertIn('- Article Character Count:',txt)
            self.assertIn('- Reader Proximity / 1000 chars:',txt)

    def test_no_new_gemini_call_site_or_client(self):
        py=Path(pipeline.__file__).read_text(encoding='utf-8')
        self.assertEqual(7,py.count('_generate_via_chat('))
        self.assertEqual(1,py.count('genai.Client('))

if __name__=='__main__': unittest.main()
