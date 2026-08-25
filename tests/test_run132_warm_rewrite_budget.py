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
        self.assertIn('硬い説明文・接続文のうち1〜2箇所', prompt)
        self.assertIn('情報量を増やさず読者に話しかける自然な文へその場で書き換える', prompt)
        self.assertIn('置換であり追記ではない', prompt)

    def test_prompt_protects_evidence_before_length_compression(self):
        prompt = pipeline.build_decision_prompt('x','https://example.com',1,'desc',source_context='primary evidence')
        self.assertIn('2,000〜3,200字の目安', prompt)
        self.assertIn('Reader ProximityやEvidenceを削る前に', prompt)
        self.assertIn('Decisionに不要な内部実装、略語の列挙、二重説明、汎用的な接続文を圧縮', prompt)

    def test_long_article_is_soft_information_budget_review(self):
        article = ('名前は難しそうですが、やっていることは意外と単純です。'
                   '必要な範囲だけ許可する仕組みです。') + (' 技術上の条件を一次資料で確認します。' * 260)
        sig = pipeline._reader_experience_signals(article)
        self.assertGreater(sig['article_char_count'], 3400)
        self.assertEqual('REVIEW', sig['information_budget'])
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
