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
        self.assertEqual("公式リポジトリで新しいOSSが公開されています。", summary["what"])
        self.assertEqual("設定と監視の手作業を減らせる可能性があり、運用負荷の判断材料になります。", summary["why"])
        self.assertEqual("検証環境で既存手順と比較テストします。", summary["decision"])
        self.assertNotIn("導入", summary["decision"])

    def test_historical_watch_uses_gated_action_instead_of_fake_adoption_language(self):
        parsed = {
            "note_draft": "",
            "decision_text": "WATCH",
            "action_text": (
                "2015年時点の設立趣旨が、その後の組織構造の変化に伴って"
                "どう変遷したかを歴史的な事実経過として整理・比較します。"
            ),
            "decision_reason_text": "歴史的な起点として比較する価値があります。",
        }
        summary = pipeline.build_reader_first_summary(parsed)
        self.assertIn("整理・比較", summary["decision"])
        self.assertNotIn("導入", summary["decision"])
        self.assertNotIn("採用", summary["decision"])

    def test_watch_fallback_is_topic_neutral_when_action_is_too_technical(self):
        parsed = {
            "note_draft": "",
            "decision_text": "WATCH",
            "action_text": "RFC-1234 /v2/internal-control endpoint compatibility matrix を確認する。",
        }
        summary = pipeline.build_reader_first_summary(parsed)
        self.assertIn("結論を急がず", summary["decision"])
        self.assertNotIn("導入", summary["decision"])

    def test_internal_decision_code_never_leaks_into_reader_header(self):
        parsed = self._parsed()
        parsed["note_draft"] = ""
        parsed["action_text"] = "TRY で進める。"
        summary = pipeline.build_reader_first_summary(parsed)
        self.assertNotIn("TRY", summary["decision"])
        self.assertTrue(summary["decision"])

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
        self.assertLess(header.index("## どんな内容？"), header.index("## なぜ重要？"))
        self.assertLess(header.index("## なぜ重要？"), header.index("## 結論は？"))
        self.assertLess(header.index("## 結論は？"), header.index("### 元情報"))
        self.assertNotIn("30秒でわかるこの記事", header)
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
        self.assertLess(manuscript.index("## どんな内容？"), manuscript.index("## なぜ重要？"))
        self.assertLess(manuscript.index("## なぜ重要？"), manuscript.index("## 結論は？"))
        self.assertLess(manuscript.index("## 結論は？"), manuscript.index("### 元情報"))
        self.assertLess(manuscript.index("### 元情報"), manuscript.index("## 現場の困りごとから"))
        self.assertLess(manuscript.index("## 現場の困りごとから"), manuscript.index("## なぜ、この問題が残り続けるのか。"))
        self.assertNotIn("## 先に判断を書くと。", manuscript)
        self.assertEqual(1, manuscript.count("### 元情報"))
        self.assertGreater(manuscript.index("### Sources / Evidence"), manuscript.index("### 結論として、いま取る距離感。"))
        self.assertIn("### 補助Evidence", manuscript)
        # Recent published notes show the primary source once in the opening 元情報 and once again in the audit footer.
        self.assertEqual(2, manuscript.count("https://github.com/acme/repo"))

    def test_hackernews_discovery_is_not_duplicated_in_rights_note(self):
        with patch.object(pipeline, "ENABLE_SUBSCRIPTION_ATTRIBUTION", False):
            manuscript = pipeline.build_clean_note_manuscript(
                "本文です。", "Official Post", "https://example.com/official", "N/A",
                source="HackerNews", title_text="記事タイトル",
                reader_summary={"what": "発表がありました。", "why": "実務判断に関係します。", "decision": "まず確認します。"},
                discovery_url="https://news.ycombinator.com/item?id=1",
            )
        self.assertEqual(2, manuscript.count("発見経路"))
        self.assertIn("発見元の[HackerNews投稿]", manuscript)

    def test_reader_summary_prefers_plain_source_summary_over_jargon_list(self):
        parsed = self._parsed()
        parsed["what_text"] = (
            "MCPの将来的な機能拡張と標準化の方針が策定され、タスク管理（SEP-2663）、"
            "DPoPやWorkload Identity Federation、Progressive Discoveryなどが提示された。"
        )
        parsed["source_summary_text"] = "MCPの次期ロードマップが公開され、今後の重点領域が示されました。"
        summary = pipeline.build_reader_first_summary(parsed)
        self.assertEqual("MCPの次期ロードマップが公開され、今後の重点領域が示されました。", summary["what"])
        self.assertNotIn("SEP-2663", summary["what"])
        self.assertNotIn("Workload Identity Federation", summary["what"])

    def test_reader_first_body_removes_duplicate_source_sentence_and_early_decision_section(self):
        parsed = self._parsed()
        parsed["note_draft"] = (
            "## 現場の困りごとから\n"
            "導入の背景です。\n\n"
            "本記事は、公式ブログの一次情報に基づいています。\n\n"
            "## 先に判断を書くと。\n"
            "まず小規模に試す価値があります。\n\n"
            "## なぜ、この問題が残り続けるのか。\n"
            "理由を説明します。\n\n"
            "### 結論として、いま取る距離感。\n"
            "最終判断は限定検証です。"
        )
        summary = pipeline.build_reader_first_summary(parsed)
        with patch.object(pipeline, "ENABLE_SUBSCRIPTION_ATTRIBUTION", False):
            manuscript = pipeline.build_clean_note_manuscript(
                parsed["note_draft"], "Official", "https://example.com/official", "N/A",
                source="HackerNews", title_text="記事タイトル", reader_summary=summary,
            )
        self.assertNotIn("本記事は、公式ブログの一次情報に基づいています。", manuscript)
        self.assertNotIn("## 先に判断を書くと。", manuscript)
        self.assertIn("### 結論として、いま取る距離感。", manuscript)
        self.assertIn("最終判断は限定検証です。", manuscript)

    def test_human_appeal_opening_skips_title_and_fixed_reader_summary(self):
        article = (
            "# 記事タイトル\n\n"
            "## どんな内容？\n\n要約です。\n\n"
            "## なぜ重要？\n\n重要性です。\n\n"
            "## 結論は？\n\n判断です。\n\n"
            "### 元情報\n"
            "- **主一次情報**: [Source](https://example.com)\n"
            "- **発見経路**: Hacker News\n\n"
            "もしAIにコード修正を任せたとき、何が変わったか追えなければ困ります。\n\n"
            "## 詳細\n本文です。"
        )
        opening = pipeline._article_opening_excerpt(article)
        self.assertTrue(opening.startswith("もしAIにコード修正を任せたとき"))
        self.assertNotIn("どんな内容？", opening)
        self.assertNotIn("主一次情報", opening)

    def test_reader_summary_compaction_does_not_create_new_claims(self):
        source = "確認できた事実です。これは二文目です。"
        compact = pipeline._compact_reader_summary(source)
        self.assertEqual("確認できた事実です。", compact)
        self.assertIn(compact.rstrip("。"), source)

    def test_reader_first_header_omits_unknown_date_instead_of_guessing(self):
        header = pipeline.build_reader_first_header(
            {"what": "発表です。", "why": "重要です。", "decision": "確認します。"},
            "Item", "https://example.com/item", "OfficialVendor", "unknown",
        )
        self.assertNotIn("公開・更新", header)
        self.assertIn("**発見経路**: 公式ベンダー", header)
        self.assertNotIn("Product Hunt", header)


if __name__ == "__main__":
    unittest.main()
