import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SYNTHETIC_REGRESSION_MODE", "true")
import pipeline


class ReaderFirstArticleFormatTests(unittest.TestCase):
    def _parsed(self):
        return {
            "note_draft": (
                "## 現場の困りごとから\n"
                "AIエージェントの運用負荷を下げたい場面で、今回の一次情報は気になります。\n\n"
                "## 先に判断を書くと。\n"
                "限定的な検証には価値があります。\n\n"
                "## なぜ、この問題が残り続けるのか。\n"
                "従来は設定と監視の手作業が残り、運用負荷が大きいからです。\n\n"
                "## 今回の仕組みを見てみる。\n"
                "公式リポジトリでは、運用処理の一部を自動化する仕組みが公開されています。\n\n"
                "## 導入前に押さえたいポイント。\n"
                "本番条件は一次情報だけでは確認できません。\n\n"
                "### 私なら、この範囲から試す。\n"
                "検証環境で既存手順と比較テストします。\n\n"
                "### 結論として、いま取る距離感。\n"
                "本番全面導入ではなく、まず限定した環境で確かめるのが妥当です。"
            ),
            "what_text": "AIエージェント運用の一部を自動化するOSSが公開されました。追加の説明です。",
            "source_summary_text": "公式リポジトリで新しいOSSが公開されています。",
            "why_important_text": "設定と監視の手作業を減らせる可能性があり、運用負荷の判断材料になります。",
            "action_text": "検証環境で既存手順と比較テストします。",
            "decision_reason_text": "小規模検証に必要な情報はあります。",
            "decision_text": "TRY",
        }

    def test_summary_reuses_gated_fields_without_new_generation(self):
        summary = pipeline.build_reader_first_summary(self._parsed())
        self.assertEqual("AIエージェント運用の一部を自動化するOSSが公開されました。", summary["what"])
        self.assertEqual("設定と監視の手作業を減らせる可能性があり、運用負荷の判断材料になります。", summary["why"])
        self.assertEqual("本番全面導入ではなく、まず限定した環境で確かめるのが妥当です。", summary["decision"])

    def test_internal_decision_code_never_leaks_into_reader_header(self):
        parsed = self._parsed()
        parsed["note_draft"] = ""
        parsed["action_text"] = "TRY で進める。"
        summary = pipeline.build_reader_first_summary(parsed)
        self.assertNotIn("TRY", summary["decision"])
        self.assertIn("限定的に試す", summary["decision"])

    def test_decision_fallback_is_reader_friendly(self):
        parsed = {"decision_text": "WAIT"}
        summary = pipeline.build_reader_first_summary(parsed)
        self.assertNotIn("WAIT", summary["decision"])
        self.assertIn("待つ", summary["decision"])

    def test_reader_header_places_summary_before_primary_source(self):
        header = pipeline.build_reader_first_header(
            {"what": "何が出たか。", "why": "なぜ重要か。", "decision": "まず試す。"},
            "acme/repo", "https://github.com/acme/repo", "GitHub", "2026-08-21T18:00:00Z",
        )
        self.assertLess(header.index("## 30秒でわかるこの記事"), header.index("### 元情報"))
        self.assertIn("**主一次情報**: [acme/repo](https://github.com/acme/repo)", header)
        self.assertIn("**発見経路**: GitHub", header)
        self.assertIn("**公開・更新**: 2026-08-22", header)

    def test_final_manuscript_is_reader_first_and_evidence_remains_at_bottom(self):
        parsed = self._parsed()
        summary = pipeline.build_reader_first_summary(parsed)
        with patch.object(pipeline, "ENABLE_SUBSCRIPTION_ATTRIBUTION", False), \
             patch.object(pipeline, "ARTICLE_PUBLICATION_MODE", "free"):
            manuscript = pipeline.build_clean_note_manuscript(
                parsed["note_draft"], "acme/repo", "https://github.com/acme/repo", "MIT",
                source="GitHub", evidence_urls=["https://docs.example.com/guide"],
                title_text="AI運用を軽くするOSSは使える？", reader_summary=summary,
                published_at="2026-08-21T00:00:00+00:00",
            )
        self.assertTrue(manuscript.startswith("# AI運用を軽くするOSSは使える？"))
        self.assertLess(manuscript.index("## 30秒でわかるこの記事"), manuscript.index("## 現場の困りごとから"))
        self.assertLess(manuscript.index("### 元情報"), manuscript.index("## 現場の困りごとから"))
        self.assertGreater(manuscript.index("### Sources / Evidence"), manuscript.index("### 結論として、いま取る距離感。"))
        self.assertIn("### 補助Evidence", manuscript)
        self.assertEqual(2, manuscript.count("https://github.com/acme/repo"))

    def test_hackernews_discovery_is_not_duplicated_in_rights_note(self):
        with patch.object(pipeline, "ENABLE_SUBSCRIPTION_ATTRIBUTION", False):
            manuscript = pipeline.build_clean_note_manuscript(
                "本文です。", "Official Post", "https://example.com/official", "N/A",
                source="HackerNews", title_text="記事タイトル",
                reader_summary={"what": "発表がありました。", "why": "実務判断に関係します。", "decision": "まず確認します。"},
                discovery_url="https://news.ycombinator.com/item?id=1",
            )
        self.assertEqual(2, manuscript.count("発見経路"))  # 上部の元情報 + 末尾Evidenceの各1回
        self.assertIn("発見元の[HackerNews投稿]", manuscript)

    def test_reader_summary_compaction_does_not_create_new_claims(self):
        source = "確認できた事実です。これは二文目です。"
        compact = pipeline._compact_reader_summary(source)
        self.assertEqual("確認できた事実です。", compact)
        self.assertIn(compact.rstrip("。"), source)

    def test_reader_first_header_omits_unknown_date_instead_of_guessing(self):
        header = pipeline.build_reader_first_header(
            {"what": "発表です。", "why": "重要です。", "decision": "確認します。"},
            "Item", "https://example.com/item", "ProductHunt", "unknown",
        )
        self.assertNotIn("公開・更新", header)
        self.assertIn("**発見経路**: Product Hunt", header)


if __name__ == "__main__":
    unittest.main()
