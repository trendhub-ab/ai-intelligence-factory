from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlsplit

import member_offer_copy as offer
import note_manuscript as note


class HumanPaidOfferCopyTests(unittest.TestCase):
    URL = (
        "https://note.com/trendhub_biz/n/ned673e381ef8"
        "?utm_source=note&utm_medium=free_article&utm_content=aif-123"
    )

    def test_security_cta_is_specific_but_never_invents_article_paid_coverage(self):
        text = offer.render(
            tracking_url=self.URL,
            reader_summary={"what": "AIエージェントの認証情報漏えいをめぐる調査"},
            source="HackerNews",
            divider="\n\n---\n\n",
        )
        self.assertIn("自分の環境なら、どこを確認するか", text)
        self.assertIn("月額1,980円", text)
        self.assertIn("利用登録・招待", text)
        self.assertIn("Notionの有料プランへ加入する必要はありません", text)
        self.assertIn(self.URL, text)
        self.assertNotIn("この記事の続き", text)
        self.assertNotIn("この記事をDBに収録", text)
        self.assertNotIn("毎日更新", text)

    def test_research_and_tool_topics_get_different_reader_questions(self):
        research = offer.render(
            tracking_url=self.URL, reader_summary={"why": "最新の研究成果"},
            source="ArXiv",
        )
        tool = offer.render(
            tracking_url=self.URL, reader_summary={"what": "APIの新機能"},
            source="OfficialVendor",
        )
        generic = offer.render(
            tracking_url=self.URL, reader_summary={"what": "2015年の歴史的な発表"},
            source="HackerNews",
        )
        self.assertIn("研究の面白さ", research)
        self.assertIn("一から比較", tool)
        self.assertIn("今日の話題", generic)
        self.assertNotEqual(research, tool)

    def test_malformed_or_empty_tracking_url_yields_no_cta(self):
        for url in ("", "javascript:alert(1)", "http://example.org/join"):
            self.assertEqual("", offer.render(tracking_url=url))
        valid = note.build_subscription_tracking_url(
            "aif-123",
            enabled=True,
            default_landing_url="https://note.com/trendhub_biz/n/ned673e381ef8",
            campaign_id="actual",
        )
        self.assertEqual(
            ["aif-123"], parse_qs(urlsplit(valid).query)["utm_content"]
        )
        rendered = note.build_subscription_cta(
            "aif-123", valid, reader_summary={"what": "開発ツールを比較"}
        )
        self.assertIn(valid, rendered)
        self.assertEqual(1, rendered.count("[月額1,980円の内容を確認する]"))


if __name__ == "__main__":
    unittest.main()
