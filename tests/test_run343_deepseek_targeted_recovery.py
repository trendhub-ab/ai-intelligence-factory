import types
import unittest

import run343_deepseek_targeted_recovery as run343


class Run343DeepSeekTargetedRecoveryTests(unittest.TestCase):
    def _pipeline(self):
        return types.SimpleNamespace(
            CONTENT_STATUS_QUALITY_FAILED="Quality Failed",
            ARTICLE_STATUS_READY="Ready",
        )

    def _text(self, value, *, title=False):
        key = "title" if title else "rich_text"
        return {key: [{"plain_text": value}]}

    def _payload(self, content_status="Quality Failed"):
        return {
            "id": run343.TARGET_PAGE_ID,
            "properties": {
                "記事名": self._text(run343.TARGET_NAME, title=True),
                "元情報URL": {"url": run343.TARGET_URL},
                "一次情報URL": {"url": run343.TARGET_URL},
                "情報源": {"select": {"name": run343.TARGET_SOURCE}},
                "コンテンツ状態": {"select": {"name": content_status}},
                "記事状態": {"select": {"name": "Not Planned"}},
                "選別スコア": {"number": 85},
                "判断スコア": {"number": 85},
                "選別理由": self._text("モデルの価格・性能競争を主導する重要案件"),
                "スコア内訳": self._text("モデルの価格・性能競争を主導する重要案件"),
                "元情報要約": self._text(run343.TARGET_NAME),
                "注目度": {"number": 399},
                "公開日": {"date": {"start": "2026-09-09T11:19:00.000Z"}},
            },
        }

    def test_reconstructs_quality_failed_exact_page_identity(self):
        item = run343.candidate_from_page_payload(self._pipeline(), self._payload())
        self.assertEqual(item["notion_page_id"], run343.TARGET_PAGE_ID)
        self.assertEqual(item["repo"]["nameWithOwner"], run343.TARGET_NAME)
        self.assertEqual(item["repo"]["url"], run343.TARGET_URL)
        self.assertEqual(item["repo"]["source"], run343.TARGET_SOURCE)
        self.assertEqual(item["screening_score"], 85)
        self.assertEqual(item["repo"]["engagement"], 399)

    def test_reconstructs_pending_retry_after_provider_unavailable(self):
        item = run343.candidate_from_page_payload(self._pipeline(), self._payload("Pending Retry"))
        self.assertEqual(item["revalidation_content_status"], "Pending Retry")
        self.assertEqual(item["notion_page_id"], run343.TARGET_PAGE_ID)

    def test_optional_primary_url_can_be_unexposed_when_canonical_url_is_exact(self):
        payload = self._payload()
        payload["properties"]["一次情報URL"] = {"type": "formula", "formula": {"type": "string", "string": run343.TARGET_URL}}
        item = run343.candidate_from_page_payload(self._pipeline(), payload)
        self.assertEqual(item["repo"]["url"], run343.TARGET_URL)

    def test_refuses_wrong_page_id_before_provider(self):
        payload = self._payload()
        payload["id"] = "00000000-0000-0000-0000-000000000000"
        with self.assertRaisesRegex(RuntimeError, "page_id"):
            run343.candidate_from_page_payload(self._pipeline(), payload)

    def test_refuses_title_or_url_drift(self):
        for key, mutation in (
            ("記事名", self._text("another DeepSeek article", title=True)),
            ("元情報URL", {"url": "https://news.ycombinator.com/item?id=1"}),
            ("一次情報URL", {"url": "https://news.ycombinator.com/item?id=2"}),
        ):
            payload = self._payload()
            payload["properties"][key] = mutation
            with self.assertRaisesRegex(RuntimeError, "refusing provider call/mutation"):
                run343.candidate_from_page_payload(self._pipeline(), payload)

    def test_refuses_source_drift(self):
        payload = self._payload()
        payload["properties"]["情報源"] = {"select": {"name": "OfficialVendor"}}
        with self.assertRaisesRegex(RuntimeError, "source"):
            run343.candidate_from_page_payload(self._pipeline(), payload)

    def test_refuses_any_other_content_status(self):
        for status in ("Deep Dive", "Ready", "Draft", "Stocked"):
            with self.subTest(status=status):
                payload = self._payload(status)
                with self.assertRaisesRegex(RuntimeError, "content_status"):
                    run343.candidate_from_page_payload(self._pipeline(), payload)

    def test_refuses_already_ready_target(self):
        payload = self._payload("Pending Retry")
        payload["properties"]["記事状態"] = {"select": {"name": "Ready"}}
        with self.assertRaisesRegex(RuntimeError, "already_ready"):
            run343.candidate_from_page_payload(self._pipeline(), payload)


if __name__ == "__main__":
    unittest.main()
