import os
import sys
import types
import unittest

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

import pipeline


class Run123ArticleQualityFinalizationTests(unittest.TestCase):
    def test_five_fields_is_not_misread_as_five_minutes(self):
        draft = "新ロードマップでは5分野に優先配分される。"
        failures = pipeline._find_unsupported_numeric_claims(draft, "The roadmap defines five priority areas.")
        self.assertFalse(any("5分" in f for f in failures), failures)

    def test_real_five_minutes_remains_numeric_claim(self):
        draft = "処理は5分で完了する。"
        failures = pipeline._find_unsupported_numeric_claims(draft, "The operation completes quickly.")
        self.assertTrue(any("5分" in f for f in failures), failures)

    def test_other_bun_compounds_are_not_time_claims(self):
        for token in ("5分割", "5分布", "5分類", "5分岐", "5分析"):
            failures = pipeline._find_unsupported_numeric_claims(f"構成は{token}として説明される。", "official source")
            self.assertFalse(any("5分" in f for f in failures), (token, failures))

    def test_plaintext_section_labels_are_promoted_only_when_unmistakable(self):
        article = """## 30秒でわかるこの記事
短い要約です。

### 元情報
- 主一次情報: 公式資料

導入本文です。""" + ("背景と条件を説明する文章です。" * 18) + """

既存OSを壊さないサンドボックス構造とWi-Fi配信

""" + ("設計上の特徴と実装条件を具体的に説明します。" * 15) + """

「e-ink最適化」を前提としたRust SDKの手ざわり

""" + ("画面更新とSDKの扱いを一次情報の範囲で説明します。" * 15) + """

導入にあたって押さえておくべき対応ハードウェアと制約

""" + ("対応機種と制約を確認してから限定環境で試します。" * 15)
        repaired, changes = pipeline._promote_plaintext_section_titles(article)
        self.assertGreaterEqual(len(changes), 3, changes)
        self.assertIn("### 既存OSを壊さないサンドボックス構造とWi-Fi配信", repaired)
        self.assertIn("### 「e-ink最適化」を前提としたRust SDKの手ざわり", repaired)
        self.assertIn("### 導入にあたって押さえておくべき対応ハードウェアと制約", repaired)

    def test_single_ambiguous_plain_line_is_never_promoted(self):
        article = "## 30秒でわかるこの記事\n要約。\n\n### 元情報\n公式資料。\n\n" + ("長い本文です。" * 180) + "\n\n今後の運用判断をどうするか\n\n" + ("さらに本文です。" * 30)
        repaired, changes = pipeline._promote_plaintext_section_titles(article)
        self.assertEqual([], changes)
        self.assertIn("\n今後の運用判断をどうするか\n", repaired)

    def test_editorial_register_density_plus_ordinal_framing_is_review_signal(self):
        article = """### 再現性を先に整える
第一の柱となるのは、公式環境を揃えることです。ここは実務的な示唆が大きいと言えます。

### 自律実行を分けて考える
今回の提案で最も興味深いのは隔離です。明確なユースケースがあり、第一段階として環境を共通化します。第二段階として限定タスクへ広げるのが妥当な判断と言えます。

### 制約は残る
注目すべき制約もあります。対応環境を確認し、小さく比較検証します。"""
        signals = pipeline._ai_style_composite_signals(article)
        self.assertTrue(signals["editorial_register_dense"], signals)
        self.assertTrue(signals["editorial_register_companion"], signals)
        self.assertTrue(signals["high"], signals)

    def test_one_editorial_phrase_is_not_a_blacklist(self):
        article = """### まず見るところ
今回の変更で興味深いのは、設定を変えずにログを比較できる点だ。

### 制約
対象環境は限られている。私なら手元の検証環境だけで差分を見る。合わなければそこで止める。"""
        signals = pipeline._ai_style_composite_signals(article)
        self.assertFalse(signals["editorial_register_dense"], signals)
        self.assertFalse(signals["high"], signals)

    def test_prompt_requires_markdown_heading_markers_without_fixed_names(self):
        prompt = pipeline.build_decision_prompt("Example", "https://example.com", 0, "desc")
        self.assertIn("必ずMarkdownの `##` または `###`", prompt)
        self.assertIn("見出し文だけを裸の1行として置かない", prompt)

    def test_style_guidance_prevents_register_stacking_without_banning_single_words(self):
        rules = pipeline._human_editorial_style_rules()
        self.assertIn("編集語彙を一記事に積み重ねない", rules)
        self.assertIn("単発で使うのはよい", rules)

    def test_structure_retry_no_longer_demands_legacy_heading_names(self):
        instruction, sections = pipeline.build_dynamic_retry_instruction([{
            "gate": "publication",
            "message": "article_structure_needs_edit",
            "reason_code": pipeline.REASON_CODE_STRUCTURE_MISSING,
            "severity": pipeline.GATE_SEVERITY_REVIEW,
        }])
        self.assertIn("内容固有のMarkdown見出し", instruction)
        self.assertIn("固定見出し名は要求しません", instruction)
        self.assertIn("structure", sections)


if __name__ == "__main__":
    unittest.main()
