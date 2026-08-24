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

class Run127IntellectualEntertainmentPullTests(unittest.TestCase):
    def test_prompt_adds_pull_without_weakening_evidence(self):
        prompt = pipeline.build_decision_prompt('x','https://example.com',1,'desc',source_context='primary evidence')
        self.assertIn('SOURCE BOUNDARY', prompt)
        self.assertIn('次の段落へ進む理由', prompt)
        self.assertIn('なぜ今日・今週・今回', prompt)
        self.assertIn('中盤で企業ホワイトペーパーへ戻らない', prompt)
        self.assertIn('30秒でわかるこの記事', prompt)
        self.assertIn('本文の段落順・見出し順・導入文型を固定するテンプレートではない', prompt)

    def test_H_clear_but_boring_is_softly_detected(self):
        article = '''MCPはAIと外部ツールを接続する仕組みです。\n\n## 詳細\nMCPでは接続方式を定義します。クライアントとサーバーがあります。仕様ではメッセージを扱います。これは接続方法です。\n\n## なぜ重要なのか\n企業では外部ツールとの接続が必要です。導入には設計が必要です。確認事項があります。運用にも注意が必要です。\n\n## 今後どうなるのか\n今後は対応状況を確認します。仕様を確認します。実装を確認します。比較します。\n\n## 最終判断\n導入前に比較検証します。'''
        sig = pipeline._reader_experience_signals(article)
        self.assertEqual('REVIEW', sig['headline_pull'])
        self.assertIn('generic_heading_cluster', sig['enjoyment_issues'])
        self.assertTrue(sig['soft_only'])

    def test_I_company_examples_are_not_hard_failure(self):
        article = '''今回の更新で営業チームのAI接続方法が変わります。\n\n## 会議前の30分が変わる\n営業担当がカレンダーとCRMを確認する場面で使えます。\n\n## まず権限を限定する\n比較検証してから導入を判断します。'''
        sig = pipeline._reader_experience_signals(article)
        self.assertIn(sig['everyday_bridge'], {'PRESENT','NOT_REQUIRED'})
        self.assertTrue(sig['soft_only'])

    def test_J_generic_headings_are_detected_but_specific_headings_pass(self):
        generic='''今回、新しい仕様が公開されました。\n\n## なぜ重要なのか\n説明です。\n\n## 今後どうなるのか\n説明です。\n\n## 最終判断\n比較検証します。'''
        specific='''今回、新しい仕様が公開されました。\n\n## 天才AIにも社員証がいる\n接続権限の話です。\n\n## 最初の仕事は送金ではなく検索でいい\n限定検証します。\n\n## 権限が増えるほど事故も大きくなる\n比較して判断します。'''
        self.assertEqual('REVIEW', pipeline._reader_experience_signals(generic)['headline_pull'])
        self.assertEqual('GOOD', pipeline._reader_experience_signals(specific)['headline_pull'])

    def test_K_news_hook_missing_is_diagnostic_without_fabricating_freshness(self):
        evergreen='''MCPはAIと外部ツールを接続する共通ルールです。初心者でも意味から理解できます。\n\n## AIが道具を使うための共通口\n仕組みを説明します。\n\n## 小さく比較して決める\n導入前に検証します。'''
        sig=pipeline._reader_experience_signals(evergreen)
        self.assertEqual('REVIEW',sig['news_relevance'])
        prompt=pipeline.build_decision_prompt('x','https://example.com',1,'desc',source_context='primary evidence')
        self.assertIn('確認できない「最新」「急速に普及」「業界が注目」は作らない',prompt)

    def test_L_over_entertainment_and_serious_mismatch(self):
        article='''新しいセキュリティ攻撃が発見されました。猫の追いかけっこに例えると簡単です。恋愛に例えるなら駆け引きです。例えばコンビニでも同じです。たとえば犬の散歩でも考えられます。\n\n## 攻撃経路\n脆弱性を確認します。'''
        sig=pipeline._reader_experience_signals(article)
        self.assertIn('analogy_overuse',sig['enjoyment_issues'])
        self.assertIn('serious_topic_tone_mismatch',sig['enjoyment_issues'])

    def test_M_cross_article_repeated_staging_phrases_are_weak_composite_signal(self):
        a='''実は、この違いが大きいです。少し考えてみましょう。

## 仕様A
これは一次情報です。条件を確認し、比較して判断します。

## 制約A
最後は限定検証します。'''
        # Same staging phrases, deliberately different rhythm/structure/opening semantics.
        b='''少し考えてみましょう。別の入口から始めます。長い背景説明をここに置き、読者が何を選ぶのかを先に示します。実は、判断条件は最後に一つだけ残ります。

## 導入候補を先に切る
短い比較です。

## 二つ目の条件を後ろへ回す
制約を示します。さらに別の長い文を置き、文章リズムを変えます。

## ここでは待つ
見送ります。'''
        peer={'name':'a','sequence':pipeline._style_sequence(a),'opening_shingles':tuple(pipeline._sentence_shingles(pipeline._article_opening_excerpt(a,520),5)),'heading_count':2,'rhetorical_phrases':tuple(sorted(pipeline._rhetorical_template_phrases(a)))}
        sig=pipeline._cross_article_naturalness_signals(b,[peer])
        self.assertIn('実は',sig['shared_rhetorical_phrases'])
        self.assertIn('少し考えてみましょう',sig['shared_rhetorical_phrases'])
        self.assertFalse(sig['high'])

    def test_M_same_staging_phrases_plus_same_structure_can_review(self):
        a='''実は、この違いが大きいです。少し考えてみましょう。

## 仕様A
これは一次情報です。長めの説明を置きます。条件を確認し、比較して判断します。

## 制約A
導入条件を確認します。最後は限定検証します。

## 判断A
私なら小さく試します。'''
        b='''実は、この変化が重要です。少し考えてみましょう。

## 仕様B
これは別の一次情報です。長めの説明を置きます。条件を確認し、比較して判断します。

## 制約B
導入条件を確認します。最後は限定検証します。

## 判断B
私なら小さく試します。'''
        peer={'name':'a','sequence':pipeline._style_sequence(a),'opening_shingles':tuple(pipeline._sentence_shingles(pipeline._article_opening_excerpt(a,520),5)),'heading_count':3,'rhetorical_phrases':tuple(sorted(pipeline._rhetorical_template_phrases(a)))}
        sig=pipeline._cross_article_naturalness_signals(b,[peer])
        self.assertTrue(sig['high'])

    def test_scene_can_improve_narrative_pull(self):
        article='''今回、新しいAI接続仕様が公開されました。\n\n## 朝9時、AIに資料をそろえてと頼む\n朝9時。AIに「今日の会議に必要な資料をそろえて」と頼む。予定を確認し、メールを探し、資料をまとめる。\n\n## 裏側では権限設計が必要になる\n何を見てよいかを限定し、比較検証して判断します。'''
        sig=pipeline._reader_experience_signals(article)
        self.assertTrue(sig['scene_present'])
        self.assertEqual('GOOD',sig['narrative_pull'])

    def test_audit_exposes_new_soft_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'a.md'
            pipeline._write_article_audit_markdown(str(out),'今回、新しい仕様が公開されました。\n\n## 固有の変化\n仕事で比較検証します。',{'status':'READY'})
            txt=out.read_text(encoding='utf-8')
            for label in ('Narrative Pull','Article-Specific Angle','Everyday Bridge','Headline Pull','News Relevance'):
                self.assertIn(f'- {label}:',txt)

    def test_no_new_gemini_call_site(self):
        py=Path(pipeline.__file__).read_text(encoding='utf-8')
        self.assertEqual(7,py.count('_generate_via_chat('))
        self.assertEqual(1,py.count('genai.Client('))

if __name__=='__main__': unittest.main()
