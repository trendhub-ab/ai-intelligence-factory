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

class Run128NonEngineerAccessibilityBridgeTests(unittest.TestCase):
    def test_prompt_targets_non_engineer_without_dropping_specialist_terms(self):
        prompt = pipeline.build_decision_prompt('x','https://example.com',1,'desc',source_context='primary evidence')
        self.assertIn('中学生〜非エンジニアが一読後に核心を自分の言葉で1文説明', prompt)
        self.assertIn('未知語を、説明なしで2個以上', prompt)
        self.assertIn('恋愛、買い物、スマホの権限、鍵、学校、旅行、料理、家族、趣味', prompt)
        self.assertIn('比喩は概念理解の補助でありEvidenceではない', prompt)
        self.assertIn('正式名称', prompt)
        self.assertIn('SOURCE BOUNDARY', prompt)

    def test_jargon_heavy_article_without_bridge_is_soft_review(self):
        article = '''今回、MCPのロードマップが公開されました。DPoPとWIF、SEP-2663を使い、ステートレスな認証とプログレッシブ・ディスカバリを組み合わせます。\n\n## 認証モデル\nDPoPはアクセストークンのproof-of-possessionを扱い、WIFはworkload federationを扱います。SEP-2663はauthorization profileを定義します。これらをMCPクライアントとゲートウェイへ適用します。\n\n## 導入判断\n限定環境で比較検証します。'''
        sig = pipeline._reader_experience_signals(article)
        self.assertTrue(sig['bridge_needed'])
        self.assertEqual('REVIEW_NEEDED', sig['everyday_bridge'])
        self.assertEqual('REVIEW', sig['plain_language_bridge'])
        self.assertEqual('REVIEW', sig['non_engineer_core_clarity'])
        self.assertIn('plain_language_bridge_missing', sig['accessibility_issues'])
        self.assertTrue(sig['soft_only'])

    def test_daily_life_bridge_can_keep_specialist_term_and_pass_translation(self):
        article = '''今回、AIの権限管理方式が更新されました。難しそうですが、日常のスマホで考えると役割が見えます。\n\n## アプリに家の合鍵を丸ごと渡さない\nスマホアプリが「写真だけ見せてください」と許可を求めるのと同じで、AIにも必要な権限だけを渡します。DPoPは、平たく言えば「その許可証を持っている本人か」を確かめやすくする仕組みです。正式にはアクセストークンを鍵と結びつけるproof-of-possessionの方式で、ここから先は一次資料の条件を確認します。\n\n## どこまで試すか\nまず限定環境で比較検証し、認証ログを見て判断します。'''
        sig = pipeline._reader_experience_signals(article)
        self.assertTrue(sig['plain_language_bridge_present'])
        self.assertEqual('PRESENT', sig['everyday_bridge'])
        self.assertEqual('GOOD', sig['plain_language_bridge'])
        self.assertEqual('GOOD', sig['jargon_translation'])
        self.assertEqual('GOOD', sig['non_engineer_core_clarity'])

    def test_romance_is_allowed_but_not_required(self):
        romance = '恋愛で最初のデートに自分の経歴を100項目すべて話さないのと同じです。必要になった情報から少しずつ見せる。これがプログレッシブ・ディスカバリの考え方です。'
        sober = 'スマホで必要な権限だけを許可する場面を考えると分かりやすいです。必要な情報だけを順番に見せる。これがプログレッシブ・ディスカバリの考え方です。'
        self.assertEqual('PRESENT', pipeline._reader_experience_signals(romance)['everyday_bridge'])
        self.assertEqual('PRESENT', pipeline._reader_experience_signals(sober)['everyday_bridge'])

    def test_accessibility_remains_soft_only_and_does_not_modify_hard_gate(self):
        article = 'WIMSEとDPoPとMCPを統合します。SEP-2663も使います。'
        sig = pipeline._reader_experience_signals(article)
        self.assertTrue(sig['soft_only'])
        parsed={'note_draft':article,'title_text':'認証方式を検討する。','action_text':'比較検証する。','decision_text':next(iter(pipeline.ALLOWED_DECISIONS)),'score':70,'decision_reason_text':'検証のため','source_summary_text':'一次資料を確認'}
        reasons = pipeline.validate_human_appeal_gate(parsed)[1]
        self.assertNotIn('plain_language_bridge_missing', reasons)
        self.assertNotIn('jargon_translation_weak', reasons)

    def test_audit_exposes_run128_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'a.md'
            pipeline._write_article_audit_markdown(str(out),'スマホの権限のように必要な範囲だけ許可します。DPoPは本人確認を補助する方式です。',{'status':'READY'})
            txt=out.read_text(encoding='utf-8')
            self.assertIn('- Plain-Language Bridge:',txt)
            self.assertIn('- Jargon Translation:',txt)
            self.assertIn('- Non-Engineer Core Clarity:',txt)

    def test_no_new_gemini_call_site_or_client(self):
        py=Path(pipeline.__file__).read_text(encoding='utf-8')
        self.assertEqual(7,py.count('_generate_via_chat('))
        self.assertEqual(1,py.count('genai.Client('))

if __name__=='__main__': unittest.main()
