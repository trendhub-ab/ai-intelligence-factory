import inspect
import os
import sys
import types
import unittest
from pathlib import Path

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GH_PAT", "test-token")
os.environ.setdefault("GEMINI_QUOTA_PROJECT_ID", "test-project")

try:
    from google import genai  # noqa: F401
except ImportError:
    google_mod = sys.modules.get("google") or types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")
    class APIError(Exception): pass
    class Client:
        def __init__(self, **_kwargs): self.chats = types.SimpleNamespace(create=lambda **_kw: None)
    genai_mod.Client = Client
    errors_mod.APIError = APIError
    google_mod.genai = genai_mod
    sys.modules.update({"google": google_mod, "google.genai": genai_mod, "google.genai.errors": errors_mod})

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import pipeline


class Run121HumanEditorialFingerprintTests(unittest.TestCase):
    def setUp(self):
        pipeline.reset_article_style_memory()

    def test_prompt_explicitly_prevents_over_explaining_and_cross_article_templates(self):
        rules = pipeline._human_editorial_style_rules()
        self.assertIn("同じ内容を言い換えて二度説明しない", rules)
        self.assertIn("接続詞で論理を毎回明示しすぎない", rules)
        self.assertIn("別の記事でも使える汎用的な導入", rules)

    def test_over_explaining_plus_transition_density_is_reviewed(self):
        article = """## ログをどう見るか
この仕組みは運用ログを一か所にまとめて確認できるため、障害時に状況を追いやすくなります。そのため、運用担当者は確認箇所を減らしやすくなります。つまり、状況把握を一か所から始められるということです。

## 実務で効くところ
運用ログをまとめて確認できるので、障害時の状況確認を一か所から始められます。そのため、確認の入口を揃えやすくなります。つまり、運用時の見通しを持ちやすいということです。

## ただし条件は残る
一方で、対象範囲には制約があります。ただし、限定環境なら比較できます。そのため、まず検証するのが妥当です。つまり、本番移行を急ぐ必要はないということです。

## 私ならここから
限定環境で比較テストします。"""
        signals = pipeline._human_editorial_depth_signals(article)
        self.assertTrue(signals["high"], signals)
        state, issues = pipeline.validate_human_appeal_gate({
            "note_draft": article,
            "title_text": "ログ基盤は本当に変わる？",
            "action_text": "限定環境で比較テストする",
        }, [])
        self.assertEqual("WEAK", state)
        self.assertIn("ai_style_composite_high", issues)

    def test_natural_editorial_variation_does_not_false_positive(self):
        article = """## Koboが読書端末ではなくなる瞬間。
電子書籍リーダーの横に、AIエージェントの承認画面が置かれる。用途だけ聞くと少し奇妙だが、E-inkの低消費電力という特徴には合っている。

Cobaltが面白いのは、Koboを無理やり別物に変えるのではなく、元の読書環境へ戻れる余地を残したままアプリ実行層を足しているところだ。

## 企業導入より、まず試作機として見る。
対応機種はまだ限られる。全社導入の候補として評価するより、専用UIの試作に使う方が筋がいい。

私ならシミュレータでSDKを触り、用途が見えた段階で実機を1台だけ用意する。E-inkである必然性がなければ、その時点で止める。"""
        self.assertFalse(pipeline._human_editorial_depth_signals(article)["high"])
        self.assertFalse(pipeline._cross_article_naturalness_signals(article, [])["high"])

    def test_near_clone_rhetorical_fingerprint_is_detected_across_articles(self):
        first = """朝いちばんに確認したいのは、性能表ではありません。今回の更新で、運用時のログが一段見やすくなりました。

## まず触るならログから
設定を全部変える必要はありません。既存環境のまま観察できる範囲があります。

## 数字より先に見る制約
公開資料では対象範囲が限られています。私は本番移行より、比較テストを先に置きます。

## 次にやること
小さな環境でログを取り、今の監視と差分を比べます。"""
        second = """朝いちばんに確認したいのは、ベンチマークではありません。今回の公開で、開発時の挙動が一段見やすくなりました。

## まず触るならログから
構成を全部変える必要はありません。既存環境のまま観察できる範囲があります。

## 数字より先に見る制約
公開資料では対象範囲が限られています。私は本番移行より、比較テストを先に置きます。

## 次にやること
小さな環境でログを取り、今の監視と差分を比べます。"""
        pipeline._remember_article_style("first", first)
        signals = pipeline._cross_article_naturalness_signals(second)
        self.assertTrue(signals["high"], signals)
        state, issues = pipeline.validate_human_appeal_gate({
            "note_draft": second,
            "title_text": "別の技術をどう見る？",
            "action_text": "限定環境で比較テストする",
        })
        self.assertEqual("WEAK", state)
        self.assertIn("cross_article_fingerprint_high", issues)

    def test_different_article_shape_is_not_flagged_merely_for_same_decision(self):
        first = """朝いちばんに確認したいのは、性能表ではありません。更新でログが見やすくなりました。

## 観察から入る
既存環境のまま確認できます。

## 私なら比べる
限定環境で比較テストします。"""
        second = """論文の数字は派手だ。しかし企業が先に見るべきなのは、再現条件が公開されているかどうかだ。

## 再現できる範囲を切り分ける
今回の結果は研究条件の中で示されたものだ。外部検証までは確認できない。

条件が揃うまで本番導入は待つ。代わりに、手元の評価セットへ追加して差分だけを見る。"""
        pipeline._remember_article_style("first", first)
        self.assertFalse(pipeline._cross_article_naturalness_signals(second)["high"])

    def test_cross_article_reason_is_review_and_retry_can_change_information_order(self):
        code = pipeline.REASON_CODE_APPEAL_CROSS_ARTICLE_FINGERPRINT
        self.assertEqual(
            pipeline.GATE_SEVERITY_REVIEW,
            pipeline.classify_gate_reason_severity("human_appeal", "cross_article_fingerprint_high", code),
        )
        instruction, sections = pipeline.build_dynamic_retry_instruction([
            {"gate": "human_appeal", "message": "cross_article_fingerprint_high", "reason_code": code, "severity": pipeline.GATE_SEVERITY_REVIEW}
        ])
        self.assertIn("同じRunの別記事", instruction)
        self.assertIn("情報提示順も変更してよい", instruction)
        self.assertIn("cross_article_style", sections)

    def test_style_memory_is_run_local_and_bounded(self):
        for i in range(20):
            pipeline._remember_article_style(str(i), "## 見出し\n" + ("長い文章です。" * 20))
        self.assertLessEqual(len(pipeline._RUN_ARTICLE_STYLE_MEMORY), 12)
        pipeline.reset_article_style_memory()
        self.assertEqual([], pipeline._RUN_ARTICLE_STYLE_MEMORY)

    def test_detectors_are_zero_api(self):
        src = inspect.getsource(pipeline._human_editorial_depth_signals) + inspect.getsource(pipeline._cross_article_naturalness_signals)
        self.assertNotIn("GEMINI", src.upper())
        self.assertNotIn("generate_content", src)
        self.assertNotIn("_generate_via_chat", src)

    def test_generation_gate_uses_run_memory_but_nonpersistent_regen_does_not(self):
        src = inspect.getsource(pipeline.generate_intelligence_report)
        self.assertIn("_RUN_ARTICLE_STYLE_MEMORY if persist_results else []", src)
        self.assertIn("_remember_article_style(name", src)

    def test_deterministic_rescue_cannot_bypass_cross_article_gate(self):
        src = inspect.getsource(pipeline._publication_rescue_can_be_ready)
        self.assertIn("validate_human_appeal_gate(parsed, peer_articles)", src)
        caller = inspect.getsource(pipeline.generate_intelligence_report)
        self.assertGreaterEqual(caller.count("peer_articles=_RUN_ARTICLE_STYLE_MEMORY if persist_results else []"), 2)


if __name__ == "__main__":
    unittest.main()
