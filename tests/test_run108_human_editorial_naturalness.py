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


class Run108HumanEditorialNaturalnessTests(unittest.TestCase):
    def test_prompt_no_longer_exposes_fixed_heading_sequence_or_paragraph_roles(self):
        src = inspect.getsource(pipeline.build_decision_prompt)
        self.assertNotIn("導入見出しは次を使う", src)
        self.assertNotIn("1段落目は", src)
        self.assertNotIn("2段落目は", src)
        self.assertNotIn("その後、以下の見出しをこの順番で出す", src)
        self.assertIn("記事固有の内容から自分で作る", src)
        self.assertIn("内部の意味役割", src)

    def test_formulaic_ai_prose_triggers_high_composite(self):
        article = """## 現場の困りごとから
ここで重要なのは、機能が増えたことではありません。運用の前提が変わることです。
ポイントは二つあります。ひとつは権限分離です。もうひとつは配信です。

## 先に判断を書くと。
注目すべきは、導入のしやすさという点です。ここで重要なのは、速さという点です。

## なぜ、この問題が残り続けるのか。
つまり、従来のやり方ではありません。別の運用モデルです。

## 今回の仕組みを見てみる。
ここで重要なのは、更新を分離できるという点です。

## 導入前に押さえたいポイント。
小さく試すべきです。急ぐ必要はありません。条件を見ます。

### 私なら、この範囲から試す。
限定環境で比較します。
"""
        signals = pipeline._ai_style_composite_signals(article)
        self.assertTrue(signals["high"], signals)
        self.assertGreaterEqual(signals["score"], 5)
        state, issues = pipeline.validate_human_appeal_gate({
            "note_draft": article,
            "title_text": "この仕組みを試す価値はある？",
            "action_text": "限定環境で比較テストする",
        })
        self.assertEqual("WEAK", state)
        self.assertIn("ai_style_composite_high", issues)

    def test_natural_human_prose_does_not_false_positive(self):
        article = """## Koboが読書端末ではなくなる瞬間。
電子書籍リーダーの横に、AIエージェントの承認画面が置かれる。用途だけ聞くと少し奇妙だが、E-inkの低消費電力という特徴には合っている。

Cobaltが面白いのは、Koboを無理やり別物に変えるのではなく、元の読書環境へ戻れる余地を残したままアプリ実行層を足しているところだ。

## 企業導入より、まず試作機として見る。
対応機種はまだ限られる。だから全社導入の候補として評価するより、専用UIの試作に使う方が筋がいい。

私ならシミュレータでSDKを触り、用途が見えた段階で実機を1台だけ用意する。E-inkである必然性がなければ、その時点で止める。

## 面白い。でも買う理由は用途から決めたい。
技術そのものより、「常時点灯させたくない小さな操作画面」が本当に必要か。その問いに答えが出るなら、Cobaltは試す価値がある。
"""
        signals = pipeline._ai_style_composite_signals(article)
        self.assertFalse(signals["high"], signals)

    def test_single_copywriting_contrast_is_not_enough_to_block(self):
        article = "## 何が変わった？\nこれは単なる高速化ではありません。運用単位を変える設計です。\n\n## 私ならどうする。\nまず比較テストします。"
        signals = pipeline._ai_style_composite_signals(article)
        self.assertFalse(signals["high"], signals)

    def test_ai_style_reason_is_review_and_has_targeted_retry_instruction(self):
        code = pipeline.REASON_CODE_APPEAL_AI_STYLE_COMPOSITE
        self.assertEqual(
            pipeline.GATE_SEVERITY_REVIEW,
            pipeline.classify_gate_reason_severity("human_appeal", "ai_style_composite_high", code),
        )
        instruction, sections = pipeline.build_dynamic_retry_instruction([
            {"gate": "human_appeal", "message": "ai_style_composite_high", "reason_code": code, "severity": pipeline.GATE_SEVERITY_REVIEW}
        ])
        self.assertIn("汎用的な接続句の反復", instruction)
        self.assertIn("見出し名・段落分割・文章リズムを変更してよい", instruction)
        self.assertIn("prose_style", sections)

    def test_detector_is_zero_api_local_logic(self):
        src = inspect.getsource(pipeline._ai_style_composite_signals)
        self.assertNotIn("GEMINI", src.upper())
        self.assertNotIn("generate_content", src)

    def test_content_specific_headings_can_satisfy_fact_structure(self):
        article = """電子書籍リーダーの横に、AIエージェントの承認画面が置かれる。用途だけ聞くと奇妙だが、低消費電力の画面として見ると筋が通る。\n\n## Koboが読書端末ではなくなる瞬間。\nCobaltはアプリ実行層を足す。\n\n## 企業導入より、まず試作機として見る。\n対応機種は限られる。私なら限定環境で比較テストし、用途がなければ採用を見送る。"""
        parsed = {
            "note_draft": article,
            "decision_text": "TRY",
            "score": 70,
            "title_text": "Koboを小さなアプリ端末に変えるCobalt。",
            "decision_reason_text": "限定検証に価値がある",
            "action_text": "限定環境で比較テストする",
            "source_summary_text": "CobaltはKobo上のアプリ実行基盤として公開されている。",
        }
        _, failures = pipeline.validate_fact_gate(parsed, "Cobalt", source_context="Official project documentation.")
        self.assertNotIn("required heading missing: 導入", failures)
        self.assertNotIn("required heading missing: 結論", failures)
        self.assertNotIn("required heading missing: 最終判断", failures)
        self.assertNotIn("ARTICLE_STRUCTURE_INCOMPLETE", failures)

    def test_opening_hook_reads_unheaded_lead(self):
        article = """何が変わったのか。今回公開された仕組みは、運用の分け方を変える。\n\n## 仕組みの中身。\n公式資料を確認する。\n\n## 私なら小さく試す。\n限定環境で比較テストする。"""
        excerpt = pipeline._article_opening_excerpt(article)
        self.assertTrue(excerpt.startswith("何が変わったのか"))


if __name__ == "__main__":
    unittest.main()
