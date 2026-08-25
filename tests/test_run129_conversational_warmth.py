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

class Run129ConversationalWarmthTests(unittest.TestCase):
    def test_prompt_allows_conversation_but_does_not_make_catchphrases_mandatory(self):
        prompt = pipeline.build_decision_prompt('x','https://example.com',1,'desc',source_context='primary evidence')
        self.assertIn('AIやITに詳しい友人が隣で', prompt)
        self.assertIn('「ですよね。」「やっぱり、」「なんですよ。」', prompt)
        self.assertIn('使用可能な例であり必須語ではない', prompt)
        self.assertIn('説明は親しみやすく、Evidenceは冷静に、Decisionは頼れる温度', prompt)
        self.assertIn('読者に同意を強要', prompt)

    def test_natural_single_conversational_marker_is_good(self):
        article='''スマホアプリに「写真へのアクセスを許可しますか？」と聞かれたこと、ありますよね。\n\n## 合鍵を丸ごと渡さない\nAIにも同じ発想で必要な権限だけを渡します。DPoPは、その許可証を持つ本人かを確かめやすくする仕組みです。\n\n## 導入判断\n一次資料の制約を確認し、限定環境で比較します。'''
        sig=pipeline._reader_experience_signals(article)
        self.assertEqual('GOOD', sig['conversational_warmth'])
        self.assertGreaterEqual(sig['conversational_marker_count'],1)
        self.assertFalse(sig['conversational_overuse'])

    def test_repeated_catchphrase_is_soft_review_only(self):
        article=('便利ですよね。難しいですよね。気になりますよね。' * 3) + '\n\n## 判断\n一次資料を確認して比較します。'
        sig=pipeline._reader_experience_signals(article)
        self.assertEqual('REVIEW_OVERUSE', sig['conversational_warmth'])
        self.assertTrue(sig['conversational_overuse'])
        self.assertIn('conversational_tone_overuse', sig['enjoyment_issues'])
        self.assertTrue(sig['soft_only'])

    def test_conversation_is_not_required_for_accessibility(self):
        article='''スマホの権限設定のように、AIにも必要な範囲だけ許可します。DPoPは許可証の持ち主を確認する仕組みです。\n\n## 判断\n一次資料の条件を確認して限定環境で比較します。'''
        sig=pipeline._reader_experience_signals(article)
        self.assertNotEqual('REVIEW_OVERUSE', sig['conversational_warmth'])
        self.assertEqual('GOOD', sig['plain_language_bridge'])

    def test_audit_exposes_conversational_warmth(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'a.md'
            pipeline._write_article_audit_markdown(str(out),'スマホで見たことがありますよね。必要な権限だけ許可します。',{'status':'READY'})
            txt=out.read_text(encoding='utf-8')
            self.assertIn('- Conversational Warmth:',txt)
            self.assertIn('- Conversational Marker Count:',txt)

    def test_no_new_gemini_call_site_or_client(self):
        py=Path(pipeline.__file__).read_text(encoding='utf-8')
        self.assertEqual(7,py.count('_generate_via_chat('))
        self.assertEqual(1,py.count('genai.Client('))

if __name__=='__main__': unittest.main()
