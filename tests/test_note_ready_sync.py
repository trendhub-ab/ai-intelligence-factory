import unittest
from unittest.mock import patch

import note_ready_sync as sync
import publication_contract as contract
import eyecatch_publication_contract as eye_contract


def rt(value):
    return {"rich_text": [{"type": "text", "plain_text": value, "text": {"content": value}}]}


def title(value):
    return {"title": [{"type": "text", "plain_text": value, "text": {"content": value}}]}


def current_eyecatch_url(public_title):
    filename = eye_contract.versioned_image_filename("test.png", public_title)
    return "https://example.com/" + filename


def code_block(body, caption):
    return {
        "type": "code",
        "code": {
            "rich_text": [{"plain_text": body, "text": {"content": body}}],
            "caption": rt(caption)["rich_text"] if caption else [],
        },
    }


def ready_page(page_id, *, source="GitHub", article_title="article"):
    return {
        "id": page_id,
        "url": f"https://www.notion.so/{page_id}",
        "properties": {
            "記事状態": {"select": {"name": "Ready"}},
            "記事名": title(article_title) if article_title else {"title": []},
            "情報源": {"select": {"name": source}},
            "元情報URL": {"url": "https://example.com/source"},
            "一次情報URL": rt("https://example.com/primary"),
            "アイキャッチ": {"files": []},
        },
    }


class NoteReadySyncTests(unittest.TestCase):
    def test_exact_target_sync_only_writes_matching_ready_and_never_revokes_others(self):
        from unittest.mock import MagicMock

        target = "3d4479ffdca981a2880bf46d5c02403d"
        other = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        pages = [ready_page(target), ready_page(other)]
        for page in pages:
            page["properties"]["アイキャッチ"] = {
                "files": [{"type": "external", "external": {"url": current_eyecatch_url("article")}}]
            }
        old_dest = {"id": "old-page", "properties": {"同期ID": rt(other), "品質状態": {"select": {"name": "Ready"}}}}
        response = MagicMock(status_code=200)
        with patch.object(sync, "NOTION_API_KEY", "token"), \
             patch.object(sync, "SOURCE_DATA_SOURCE_ID", "source"), \
             patch.object(sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(sync, "_validate_destination_schema"), \
             patch.object(sync, "_query_db", side_effect=[pages, [old_dest]]), \
             patch.object(sync, "_source_current_ready_manuscript", return_value="manuscript") as manuscript, \
             patch.object(sync, "_request", return_value=response) as request, \
             patch.object(sync.time, "sleep"):
            result = sync.sync_note_ready_db(target_sync_id=target)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["revoked"], 0)
        manuscript.assert_called_once_with(target)
        writes = [call for call in request.call_args_list if call.args and call.args[0] in ("POST", "PATCH")]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0].kwargs["json"]["properties"]["同期ID"]["rich_text"][0]["text"]["content"], target)

    def test_exact_target_sync_fails_closed_when_ready_missing_or_invalid(self):
        target = "3d4479ffdca981a2880bf46d5c02403d"
        with patch.object(sync, "NOTION_API_KEY", "token"), \
             patch.object(sync, "SOURCE_DATA_SOURCE_ID", "source"), \
             patch.object(sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(sync, "_validate_destination_schema"), \
             patch.object(sync, "_query_db", side_effect=[[], []]), \
             patch.object(sync, "_request") as request:
            with self.assertRaisesRegex(ValueError, "Exact Ready target"):
                sync.sync_note_ready_db(target_sync_id=target)
            request.assert_not_called()
        with self.assertRaisesRegex(ValueError, "Invalid target_sync_id"):
            sync.sync_note_ready_db(target_sync_id="wrong")

    def test_exact_target_updates_existing_hyphenated_sync_id_without_duplicate(self):
        from unittest.mock import MagicMock

        target = "3d4479ffdca981a2880bf46d5c02403d"
        page = ready_page(target)
        page["properties"]["アイキャッチ"] = {
            "files": [{"type": "external", "external": {"url": current_eyecatch_url("article")}}]
        }
        hyphenated = "3d4479ff-dca9-81a2-880b-f46d5c02403d"
        existing = {"id": "existing", "properties": {"同期ID": rt(hyphenated), "品質状態": {"select": {"name": "Ready"}}}}
        with patch.object(sync, "NOTION_API_KEY", "token"), \
             patch.object(sync, "SOURCE_DATA_SOURCE_ID", "source"), \
             patch.object(sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(sync, "_validate_destination_schema"), \
             patch.object(sync, "_query_db", side_effect=[[page], [existing]]), \
             patch.object(sync, "_source_current_ready_manuscript", return_value="manuscript"), \
             patch.object(sync, "_request", return_value=MagicMock(status_code=200)) as request, \
             patch.object(sync.time, "sleep"):
            result = sync.sync_note_ready_db(target_sync_id=target)
        self.assertEqual((result["created"], result["updated"], result["revoked"]), (0, 1, 0))
        self.assertEqual([call.args[0] for call in request.call_args_list], ["PATCH"])

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
                    "files": [{"type": "external", "external": {"url": current_eyecatch_url("note title")}}]
                },
            },
        }
        state = sync._source_state(page)
        self.assertIsNotNone(state)
        self.assertEqual(state["sync_id"], "123456781234123412341234567890ab")
        self.assertEqual(state["title"], "note title")
        self.assertEqual(state["primary_url"], "https://example.com/primary")
        self.assertEqual(state["eyecatch_url"], current_eyecatch_url("note title"))

        page["properties"]["アイキャッチ"] = {
            "files": [{"type": "external", "external": {"url": "https://example.com/legacy.png"}}]
        }
        self.assertIsNone(sync._source_state(page))

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

    def test_sync_metrics_account_for_every_ready_source_row(self):
        source_pages = [
            ready_page("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", source="GitHub", article_title="stale"),
            ready_page("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", source="GitHub", article_title=""),
            ready_page("cccccccccccccccccccccccccccccccc", source="ProductHunt", article_title="retired"),
        ]
        with patch.object(sync, "NOTION_API_KEY", "token"), \
             patch.object(sync, "SOURCE_DATA_SOURCE_ID", "source"), \
             patch.object(sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(sync, "_validate_destination_schema"), \
             patch.object(sync, "_query_db", side_effect=[source_pages, []]), \
             patch.object(sync, "_source_current_ready_manuscript", return_value=""):
            result = sync.sync_note_ready_db()

        self.assertEqual(result["source_ready_status_rows"], 3)
        self.assertEqual(result["source_ready"], 0)
        self.assertEqual(result["stale_publication_contract"], 1)
        self.assertEqual(result["unsupported_source"], 1)
        self.assertEqual(result["invalid_source_state"], 1)
        classified = (
            result["source_ready"]
            + result["stale_publication_contract"]
            + result["incomplete_publication_assets"]
            + result["unsupported_source"]
            + result["invalid_source_state"]
        )
        self.assertEqual(classified, result["source_ready_status_rows"])


if __name__ == "__main__":
    unittest.main()
