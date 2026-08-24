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

class Run126ReaderExperienceTests(unittest.TestCase):
    def test_prompt_preserves_hard_evidence_and_adds_reader_experience(self):
        prompt = pipeline.build_decision_prompt('x','https://example.com',1,'desc',source_context='primary evidence')
        self.assertIn('SOURCE BOUNDARY', prompt)
        self.assertIn('Evidence-to-Decision', prompt)
        self.assertIn('難しいことを難しく感じさせない', prompt)
        self.assertIn('意味や身近な働き', prompt)
        self.assertIn('比喩を入れること自体を目的', prompt)

    def test_no_analogy_can_still_be_good(self):
        article = '仕事でAIを使うとき、外部ツールとの接続方法が変わりそうです。\n\n## 何が変わるのか\nMCPはAIと外部ツールをつなぐための共通ルールです。公式資料では接続方式が説明されています。\n\n## どう判断するか\nまず検証環境で比較し、条件が合えば導入を判断します。'
        sig = pipeline._reader_experience_signals(article)
        self.assertFalse(sig['analogy_used'])
        self.assertTrue(sig['soft_only'])

    def test_overused_playful_analogies_warn(self):
        article = '例えば猫のように考えます。たとえば犬のように動きます。例えばコンビニのレジです。たとえるなら恋愛です。仕事で使うAIの話です。'
        sig = pipeline._reader_experience_signals(article)
        self.assertIn('analogy_overuse', sig['enjoyment_issues'])

    def test_serious_security_theme_does_not_force_playful_tone(self):
        sober = 'セキュリティ侵害のリスクを扱います。攻撃経路と監査条件を確認し、導入前に検証します。'
        sig = pipeline._reader_experience_signals(sober)
        self.assertNotIn('serious_topic_tone_mismatch', sig['enjoyment_issues'])
        playful = 'セキュリティ攻撃を猫の追いかけっこや恋愛ゲームのように考えます。'
        sig2 = pipeline._reader_experience_signals(playful)
        self.assertIn('serious_topic_tone_mismatch', sig2['enjoyment_issues'])

    def test_unexplained_acronym_is_soft_diagnostic(self):
        article = '仕事で新しい接続方式を検討します。WIMSEを採用候補にします。次に比較検証します。'
        sig = pipeline._reader_experience_signals(article)
        self.assertIn('WIMSE', sig['unexplained_jargon'])
        self.assertEqual('REVIEW', sig['accessibility'])
        parsed={'note_draft':article,'title_text':'接続方式を検討する。','action_text':'比較検証する。','decision_text':next(iter(pipeline.ALLOWED_DECISIONS)),'score':70,'decision_reason_text':'検証のため','source_summary_text':'一次資料を確認'}
        # Reader Experience is not wired as a hard publication gate.
        self.assertNotIn('unexplained_acronyms', pipeline.validate_human_appeal_gate(parsed)[1])

    def test_explained_acronym_is_not_flagged(self):
        article = '仕事で接続方式を検討します。Workload Identity in Multi-System Environments（WIMSE）は、複数システム間のID連携を扱う考え方です。次に比較検証します。'
        sig = pipeline._reader_experience_signals(article)
        self.assertNotIn('WIMSE', sig['unexplained_jargon'])

    def test_announcement_only_opening_is_soft_warning(self):
        article='Googleは新しいAIモデルを発表しました。仕様が公開されました。\n\n## 詳細\nモデルの説明です。'
        sig=pipeline._reader_experience_signals(article)
        self.assertIn('announcement_summary_opening',sig['enjoyment_issues'])

    def test_reader_bridge_and_return_pull(self):
        article='仕事で毎日使うAIの選び方が少し変わりそうです。なぜなら接続先の扱いが変わるからです。\n\n## 次に見ること\nまず小さく比較検証し、導入条件を判断します。'
        sig=pipeline._reader_experience_signals(article)
        self.assertEqual('GOOD',sig['curiosity_pull'])
        self.assertEqual('GOOD',sig['return_pull'])

    def test_audit_contains_reader_experience_without_notion_schema(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'a.md'
            pipeline._write_article_audit_markdown(str(out),'仕事で使うAIの違いを見ます。次に比較検証します。',{'status':'READY'})
            txt=out.read_text(encoding='utf-8')
            self.assertIn('## Reader Experience',txt)
            self.assertIn('- Accessibility:',txt)
            self.assertIn('- Analogy Used:',txt)
            self.assertIn('- Unexplained Jargon:',txt)

    def test_no_new_gemini_call_site(self):
        py=Path(pipeline.__file__).read_text(encoding='utf-8')
        self.assertEqual(7,py.count('_generate_via_chat('))
        self.assertEqual(1,py.count('genai.Client('))

if __name__=='__main__': unittest.main()
