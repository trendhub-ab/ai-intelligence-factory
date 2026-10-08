import unittest
from unittest.mock import MagicMock, patch

import eyecatch_publication_contract as eye_contract
import note_ready_sync as sync


def rt(value):
    return {"rich_text": [{"type": "text", "plain_text": value, "text": {"content": value}}]}


def title(value):
    return {"title": [{"type": "text", "plain_text": value, "text": {"content": value}}]}


def current_eyecatch_url(public_title):
    filename = eye_contract.versioned_image_filename("test.png", public_title)
    return "https://example.com/" + filename


def ready_page(page_id, *, article_title="article"):
    return {
        "id": page_id,
        "url": f"https://www.notion.so/{page_id}",
        "properties": {
            "記事状態": {"select": {"name": "Ready"}},
            "記事名": title(article_title),
            "情報源": {"select": {"name": "GitHub"}},
            "元情報URL": {"url": "https://example.com/source"},
            "一次情報URL": rt("https://example.com/primary"),
            "アイキャッチ": {
                "files": [{"type": "external", "external": {"url": current_eyecatch_url(article_title)}}]
            },
        },
    }


def destination_page(page_id, sync_id, *, posting_status="投稿待ち", quality_status="Ready"):
    return {
        "id": page_id,
        "properties": {
            "同期ID": rt(sync_id),
            "投稿状態": {"select": {"name": posting_status}},
            "品質状態": {"select": {"name": quality_status}},
        },
    }


class NoteReadyDeliveryCompatibilityTests(unittest.TestCase):
    def test_broad_sync_revokes_inline_code_false_ready_without_touching_human_status(self):
        target = "3f2479ffdca981dcb344eae700abb976"
        source = ready_page(target)
        existing = destination_page("dest-page", target)
        response = MagicMock(status_code=200)

        with patch.object(sync, "NOTION_API_KEY", "token"), \
             patch.object(sync, "SOURCE_DATA_SOURCE_ID", "source"), \
             patch.object(sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(sync, "_validate_destination_schema"), \
             patch.object(sync, "_query_db", side_effect=[[source], [existing]]), \
             patch.object(sync, "_source_current_ready_manuscript", return_value="# article\n\nUse `temperature` here.\n"), \
             patch.object(sync, "_request", return_value=response) as request, \
             patch.object(sync.time, "sleep"):
            result = sync.sync_note_ready_db()

        self.assertEqual(result["source_ready"], 0)
        self.assertEqual(result["note_delivery_incompatible"], 1)
        self.assertEqual(result["revoked"], 1)
        patch_calls = [call for call in request.call_args_list if call.args and call.args[0] == "PATCH"]
        self.assertEqual(len(patch_calls), 1)
        props = patch_calls[0].kwargs["json"]["properties"]
        self.assertEqual(props["品質状態"]["select"]["name"], "Ready取消")
        self.assertNotIn("投稿状態", props)
        self.assertNotIn("note公開URL", props)

    def test_exact_sync_revokes_inline_code_false_ready_then_fails_closed(self):
        target = "3f2479ffdca981dcb344eae700abb976"
        source = ready_page(target)
        existing = destination_page("dest-page", target)
        response = MagicMock(status_code=200)

        with patch.object(sync, "NOTION_API_KEY", "token"), \
             patch.object(sync, "SOURCE_DATA_SOURCE_ID", "source"), \
             patch.object(sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(sync, "_validate_destination_schema"), \
             patch.object(sync, "_query_db", side_effect=[[source], [existing]]), \
             patch.object(sync, "_source_current_ready_manuscript", return_value="# article\n\nUse `temperature` here.\n"), \
             patch.object(sync, "_request", return_value=response) as request, \
             patch.object(sync.time, "sleep"):
            with self.assertRaisesRegex(ValueError, "note delivery"):
                sync.sync_note_ready_db(target_sync_id=target)

        patch_calls = [call for call in request.call_args_list if call.args and call.args[0] == "PATCH"]
        self.assertEqual(len(patch_calls), 1)
        props = patch_calls[0].kwargs["json"]["properties"]
        self.assertEqual(props["品質状態"]["select"]["name"], "Ready取消")
        self.assertNotIn("投稿状態", props)


if __name__ == "__main__":
    unittest.main(verbosity=2)
