import unittest

import note_ready_sync as sync


def rt(value):
    return {"rich_text": [{"type": "text", "plain_text": value, "text": {"content": value}}]}


def title(value):
    return {"title": [{"type": "text", "plain_text": value, "text": {"content": value}}]}


class NoteReadySyncTests(unittest.TestCase):
    def test_source_state_accepts_only_ready_and_uses_first_primary_url(self):
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
            },
        }
        state = sync._source_state(page)
        self.assertIsNotNone(state)
        self.assertEqual(state["sync_id"], "123456781234123412341234567890ab")
        self.assertEqual(state["title"], "note title")
        self.assertEqual(state["primary_url"], "https://example.com/primary")

        page["properties"]["記事状態"] = {"select": {"name": "Needs Editorial Review"}}
        self.assertIsNone(sync._source_state(page))

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
