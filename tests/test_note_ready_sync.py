import unittest
from unittest.mock import patch

import note_ready_sync as sync
import publication_contract as contract


def rt(value):
    return {"rich_text": [{"type": "text", "plain_text": value, "text": {"content": value}}]}


def title(value):
    return {"title": [{"type": "text", "plain_text": value, "text": {"content": value}}]}


def code_block(body, caption):
    return {
        "type": "code",
        "code": {
            "rich_text": [{"plain_text": body, "text": {"content": body}}],
            "caption": rt(caption)["rich_text"] if caption else [],
        },
    }


class NoteReadySyncTests(unittest.TestCase):
    def test_source_state_accepts_only_ready_uses_first_primary_url_and_reads_eyecatch(self):
        page = {
            "id": "12345678-1234-1234-1234-1234567890ab",
            "url": "https://www.notion.so/123456781234123412341234567890ab",
            "properties": {
                "記事状態": {"select": {"name": "Ready"}},
                "note記事タイトル": rt("note title"),
                "記事名": title("source title"),
                "判断": {"select": {"name": "TRY"}},
                "判断スコア": {"number": 81},
                "記事価値": {"number": 88},
                "情報源": {"select": {"name": "GitHub"}},
                "元情報URL": {"url": "https://example.com/source"},
                "一次情報URL": rt("https://example.com/primary\nhttps://example.com/secondary"),
                "アイキャッチ": {
                    "files": [{"type": "external", "external": {"url": "https://example.com/current.png"}}]
                },
            },
        }
        state = sync._source_state(page)
        self.assertIsNotNone(state)
        self.assertEqual(state["sync_id"], "123456781234123412341234567890ab")
        self.assertEqual(state["title"], "note title")
        self.assertEqual(state["primary_url"], "https://example.com/primary")
        self.assertEqual(state["eyecatch_url"], "https://example.com/current.png")

        page["properties"]["記事状態"] = {"select": {"name": "Needs Editorial Review"}}
        self.assertIsNone(sync._source_state(page))

    def test_source_publishability_requires_body_hash_and_current_policy(self):
        body = "article" * 50
        current = contract.current_ready_caption(body)
        with patch.object(sync, "_block_children", return_value=[code_block(body, current)]):
            self.assertEqual(body, sync._source_current_ready_manuscript("page"))
            self.assertTrue(sync._source_has_current_ready_manuscript("page"))

        with patch.object(sync, "_block_children", return_value=[code_block(body + "tampered", current)]):
            self.assertEqual("", sync._source_current_ready_manuscript("page"))

        with patch.object(sync, "_block_children", return_value=[code_block(body, contract.LEGACY_READY_CAPTION)]):
            self.assertFalse(sync._source_has_current_ready_manuscript("page"))

    def test_latest_valid_current_block_wins(self):
        old = "old" * 100
        new = "new" * 100
        blocks = [
            code_block(old, contract.current_ready_caption(old)),
            code_block(new, contract.current_ready_caption(new)),
        ]
        with patch.object(sync, "_block_children", return_value=blocks):
            self.assertEqual(new, sync._source_current_ready_manuscript("page"))

    def test_files_url_rejects_non_http_asset(self):
        self.assertEqual("", sync._files_url({"files": [{"type": "external", "external": {"url": "file:///tmp/a.png"}}]}))
        self.assertEqual(
            "https://example.com/a.png",
            sync._files_url({"files": [{"type": "file", "file": {"url": "https://example.com/a.png"}}]}),
        )

    def test_system_props_never_overwrite_human_workflow_fields(self):
        state = {
            "sync_id": "abc",
            "title": "Ready article",
            "decision": "WATCH",
            "decision_score": 72,
            "article_value": 85,
            "source": "HackerNews",
            "original_url": "https://example.com/source",
            "primary_url": "https://example.com/primary",
            "content_page_url": "https://www.notion.so/source-page",
        }
        props = sync._system_props(state, today="2026-08-30")
        self.assertEqual(props["品質状態"]["select"]["name"], "Ready")
        for human_field in ("投稿状態", "note公開URL", "投稿予定日", "投稿日"):
            self.assertNotIn(human_field, props)

    def test_destination_state_preserves_posted_for_revocation_policy(self):
        page = {
            "id": "dest-page",
            "properties": {
                "同期ID": rt("abc"),
                "投稿状態": {"select": {"name": "投稿済み"}},
                "品質状態": {"select": {"name": "Ready"}},
            },
        }
        current = sync._destination_state(page)
        self.assertEqual(current["posting_status"], "投稿済み")
        self.assertEqual(current["quality_status"], "Ready")


if __name__ == "__main__":
    unittest.main()
