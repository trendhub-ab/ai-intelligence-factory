import sys
import types
import unittest
from unittest.mock import Mock, patch

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.Response = object
    requests_stub.request = lambda *args, **kwargs: None
    sys.modules["requests"] = requests_stub

import note_ready_sync as sync


def rt(value: str) -> dict:
    return {
        "rich_text": [
            {"type": "text", "plain_text": value, "text": {"content": value}}
        ]
    }


def destination_page(posting_status: str, quality_status: str = "Ready") -> dict:
    return {
        "id": "dest-page",
        "properties": {
            "同期ID": rt("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
            "投稿状態": {"select": {"name": posting_status}},
            "品質状態": {"select": {"name": quality_status}},
        },
    }


class Run290QualityWorkflowSeparationTests(unittest.TestCase):
    def test_quality_revocation_props_never_contains_human_workflow_field(self):
        props = sync._quality_revocation_props(today="2026-09-08")
        self.assertEqual(props["品質状態"]["select"]["name"], "Ready取消")
        self.assertEqual(props["最終同期日"]["date"]["start"], "2026-09-08")
        for human_field in ("投稿状態", "note公開URL", "投稿予定日", "投稿日"):
            self.assertNotIn(human_field, props)

    def test_automatic_quality_revocation_preserves_every_posting_status(self):
        posting_statuses = ("投稿待ち", "投稿準備中", "保留", "取下げ", "投稿済み")
        for posting_status in posting_statuses:
            with self.subTest(posting_status=posting_status):
                response = Mock(status_code=200, text="")
                with patch.object(sync, "NOTION_API_KEY", "token"), \
                     patch.object(sync, "SOURCE_DATA_SOURCE_ID", "source"), \
                     patch.object(sync, "DEST_DATA_SOURCE_ID", "dest"), \
                     patch.object(sync, "_validate_destination_schema"), \
                     patch.object(
                         sync,
                         "_query_db",
                         side_effect=[[], [destination_page(posting_status)]],
                     ), \
                     patch.object(sync, "_request", return_value=response) as request, \
                     patch.object(sync.time, "sleep"):
                    result = sync.sync_note_ready_db()

                self.assertEqual(result["revoked"], 1)
                self.assertEqual(request.call_count, 1)
                payload = request.call_args.kwargs["json"]
                props = payload["properties"]
                self.assertEqual(props["品質状態"]["select"]["name"], "Ready取消")
                self.assertNotIn("投稿状態", props)

    def test_already_quality_revoked_row_is_idempotent_and_not_written(self):
        with patch.object(sync, "NOTION_API_KEY", "token"), \
             patch.object(sync, "SOURCE_DATA_SOURCE_ID", "source"), \
             patch.object(sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(sync, "_validate_destination_schema"), \
             patch.object(
                 sync,
                 "_query_db",
                 side_effect=[[], [destination_page("保留", quality_status="Ready取消")]],
             ), \
             patch.object(sync, "_request") as request:
            result = sync.sync_note_ready_db()

        self.assertEqual(result["revoked"], 0)
        request.assert_not_called()

    def test_new_ready_row_still_enters_posting_waiting(self):
        state = {
            "sync_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "title": "Ready article",
            "decision": "WATCH",
            "decision_score": 72,
            "article_value": 85,
            "source": "HackerNews",
            "original_url": "https://example.com/source",
            "primary_url": "https://example.com/primary",
            "content_page_url": "https://www.notion.so/source-page",
            "eyecatch_url": "https://example.com/eyecatch.png",
        }
        source_page = {"id": state["sync_id"], "properties": {"情報源": {"select": {"name": "HackerNews"}}}}
        response = Mock(status_code=200, text="")
        with patch.object(sync, "NOTION_API_KEY", "token"), \
             patch.object(sync, "SOURCE_DATA_SOURCE_ID", "source"), \
             patch.object(sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(sync, "_validate_destination_schema"), \
             patch.object(sync, "_query_db", side_effect=[[source_page], []]), \
             patch.object(sync, "_source_state", return_value=state), \
             patch.object(sync, "_source_current_ready_manuscript", return_value="body"), \
             patch.object(sync, "_request", return_value=response) as request, \
             patch.object(sync.time, "sleep"):
            result = sync.sync_note_ready_db()

        self.assertEqual(result["created"], 1)
        props = request.call_args.kwargs["json"]["properties"]
        self.assertEqual(props["投稿状態"]["select"]["name"], "投稿待ち")
        self.assertEqual(props["品質状態"]["select"]["name"], "Ready")

    def test_existing_ready_update_still_preserves_human_workflow_fields(self):
        props = sync._system_props(
            {
                "sync_id": "abc",
                "title": "Ready article",
                "decision": "TRY",
                "decision_score": 80,
                "article_value": 90,
                "source": "GitHub",
                "original_url": "https://example.com/source",
                "primary_url": "https://example.com/primary",
                "content_page_url": "https://www.notion.so/source-page",
            },
            today="2026-09-08",
        )
        for human_field in ("投稿状態", "note公開URL", "投稿予定日", "投稿日"):
            self.assertNotIn(human_field, props)


if __name__ == "__main__":
    unittest.main()
