import unittest

import run296_editorial_format_v2 as r296


class Run296ArticleFormatTests(unittest.TestCase):
    def _legacy_manuscript(self):
        return """# Netflixが推薦の舞台裏をLLMネイティブへ舵を切った理由。

## 30秒でわかるこの記事

**何が出た？**  
Netflixが推薦基盤の新しい方向性を公開しました。

**なぜ重要？**  
推薦システムの設計思想が変わる可能性があります。

**結論は？**  
今は動きを追う価値があります。

### 元情報
- **主一次情報**: [Netflix](https://example.com/source)

---

### Sources / Evidence
- **主一次情報**: [Netflix](https://example.com/source)

※本記事に含まれる見解・提案は筆者個人の意見です。

---

### 調査と判断の時間を減らしたい方へ

無料記事では重要テーマを最後まで公開しています。会員向けには、意思決定DBと月次ダイジェストで、公開後も変化を追い、採用・様子見・見送りの判断に必要なEvidenceとActionを継続的に整理します。

[会員向け意思決定DB＋月次ダイジェストを見る](https://note.com/example?utm_source=note)
"""

    def test_exact_reader_approved_intro_and_cta(self):
        out = r296.normalize_article_format_v2(self._legacy_manuscript())
        self.assertIn("## どんな内容？", out)
        self.assertNotIn("30秒でわかるこの記事", out)
        self.assertNotIn("何が出た？", out)
        self.assertIn("Netflixが推薦基盤の新しい方向性を公開しました。", out)
        self.assertIn("**なぜ重要？**", out)
        self.assertIn("**結論は？**", out)
        self.assertIn("### 有料サブスクのご案内", out)
        self.assertIn(r296.CTA_BODY, out)
        self.assertIn("[詳しくはこちら](https://note.com/example?utm_source=note)", out)
        self.assertNotIn("調査と判断の時間を減らしたい方へ", out)
        self.assertNotIn("会員向け意思決定DB＋月次ダイジェストを見る", out)
        self.assertNotIn("EvidenceとActionを継続的に整理", out)

    def test_summary_text_stays_between_intro_heading_and_why(self):
        summary = "Netflixがユーザー行動や文脈をテキスト化し、vLLMのprefill-onlyモードでスコアリングを行う推薦アーキテクチャGenRecを公開した。"
        old = self._legacy_manuscript().replace(
            "Netflixが推薦基盤の新しい方向性を公開しました。",
            summary,
        )
        out = r296.normalize_article_format_v2(old)
        self.assertEqual(out.count(summary), 1)
        self.assertNotIn("**何が出た？**", out)
        self.assertLess(out.index("## どんな内容？"), out.index(summary))
        self.assertLess(out.index(summary), out.index("**なぜ重要？**"))

    def test_sources_remain_before_cta(self):
        out = r296.normalize_article_format_v2(self._legacy_manuscript())
        self.assertLess(out.index("### Sources / Evidence"), out.index("### 有料サブスクのご案内"))

    def test_cta_destination_is_preserved_byte_for_byte(self):
        url = "https://note.com/example?utm_source=note&utm_content=aif-test"
        old = self._legacy_manuscript().replace(
            "https://note.com/example?utm_source=note", url
        )
        out = r296.normalize_article_format_v2(old)
        self.assertIn(f"[詳しくはこちら]({url})", out)

    def test_missing_cta_link_fails_safe_without_deleting_old_block(self):
        old = self._legacy_manuscript().replace(
            "[会員向け意思決定DB＋月次ダイジェストを見る](https://note.com/example?utm_source=note)",
            "リンク未設定",
        )
        out = r296.normalize_article_format_v2(old)
        self.assertIn("調査と判断の時間を減らしたい方へ", out)
        self.assertIn("リンク未設定", out)


class Run296EyecatchPolicyTests(unittest.TestCase):
    def test_genrec_uses_exact_reviewed_short_copy(self):
        plan = r296.genrec_validated_plan()
        self.assertNotEqual(r296._canon(r296.GENREC_SOURCE_TITLE), r296._canon(plan["eyecatch_title"]))
        self.assertEqual(
            plan["title_lines"],
            ["Netflix推薦の舞台裏", "LLMネイティブへ", "舵を切った理由"],
        )
        self.assertEqual(plan["highlight_text"], "舵を切った理由")
        self.assertEqual(plan["subheadline_lines"], [])
        self.assertTrue(r296.compounds_are_atomic(plan["title_lines"]))

    def test_butaiura_split_is_rejected(self):
        self.assertFalse(r296.compounds_are_atomic(["Netflix推薦の舞台", "裏で変わる"]));
        self.assertTrue(r296.compounds_are_atomic(["Netflix推薦の舞台裏", "で変わる"]))

    def test_long_article_title_cannot_be_reused_verbatim(self):
        long_title = "Netflixが推薦の舞台裏をLLMネイティブへ舵を切った理由。"
        self.assertFalse(r296.eyecatch_copy_is_distinct(long_title, long_title))
        self.assertTrue(r296.eyecatch_copy_is_distinct(long_title, r296.GENREC_EYECATCH_TITLE))

    def test_short_title_may_remain_when_forced_paraphrase_would_add_risk(self):
        self.assertTrue(r296.eyecatch_copy_is_distinct("短い記事タイトル", "短い記事タイトル"))

    def test_target_title_matching_ignores_terminal_punctuation_only(self):
        self.assertTrue(r296.is_genrec_title(r296.GENREC_SOURCE_TITLE))
        self.assertTrue(r296.is_genrec_title(r296.GENREC_SOURCE_TITLE.rstrip("。")))
        self.assertFalse(r296.is_genrec_title("Netflixとは別の記事タイトル"))


class Run296SafetyBoundaryTests(unittest.TestCase):
    def test_module_has_no_note_mutation_or_public_release_surface(self):
        source = open(r296.__file__, encoding="utf-8").read().lower()
        for forbidden in (
            "page.click(",
            "keyboard.press(",
            "publish_note",
            "public_release = true",
            "requests.patch(",
            "requests.post(",
        ):
            self.assertNotIn(forbidden, source)

    def test_no_new_model_request_is_implemented(self):
        source = open(r296.__file__, encoding="utf-8").read()
        self.assertNotIn("_generate_via_chat(", source)
        self.assertNotIn("generate_content(", source)


if __name__ == "__main__":
    unittest.main()
