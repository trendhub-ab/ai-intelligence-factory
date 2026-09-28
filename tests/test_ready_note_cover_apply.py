from __future__ import annotations

import types
from unittest import TestCase
from unittest.mock import patch

import ready_note_cover_apply as target


SYNC_ID = "3e8479ffdca9812e9661f337a84b1df4"
TITLE = "AIの巨人はどこから生まれたのか。2015年、非営利スタートアップ「OpenAI」が掲げた理想と出発点。"
MANUSCRIPT = "## どんな内容？\nOpenAIの設立時点を確認します。\n\n## なぜ重要？\n原点を確認するためです。"


class ReadyNoteCoverApplyTests(TestCase):
    def test_route_comparison_ignores_query_but_requires_note_edit_route(self):
        left = "https://note.com/notes/abc123/edit?foo=1"
        right = "https://note.com/notes/abc123/edit"
        with patch.object(target.audit_base, "_is_note_edit_url", side_effect=lambda v: "/notes/abc123/edit" in v):
            self.assertTrue(target._same_edit_route(left, right))

    def test_preflight_requires_current_ready_asset_and_manuscript(self):
        article = {
            "sync_id": SYNC_ID,
            "title": TITLE,
            "manuscript": MANUSCRIPT,
            "destination_page_id": "dest",
        }
        page_response = types.SimpleNamespace(status_code=200, json=lambda: {"id": SYNC_ID})
        state = {
            "sync_id": SYNC_ID,
            "title": TITLE,
            "source": "HackerNews",
            "eyecatch_url": "https://example.invalid/current.png",
        }
        destination = {
            "destination_page_id": "dest",
            "sync_id": SYNC_ID,
            "title": TITLE,
        }
        with patch.object(target.audit_base, "_expected_article", return_value=article), \
             patch.object(target.audit_base, "_destination_row", return_value=destination), \
             patch.object(target.ready_sync, "_request", return_value=page_response), \
             patch.object(target.ready_sync, "_source_state", return_value=state), \
             patch.object(target.ready_sync, "_source_current_ready_manuscript", return_value=MANUSCRIPT), \
             patch.object(target.eyecatch_contract, "require_current_asset_url", return_value=state["eyecatch_url"]):
            result = target.preflight(SYNC_ID)
        self.assertEqual(result["sync_id"], SYNC_ID)
        self.assertEqual(result["quality_state"], "Ready")
        self.assertEqual(result["posting_state"], "投稿準備中")
        self.assertEqual(result["eyecatch_url"], state["eyecatch_url"])

    def test_prepare_only_never_mutates_note_or_source(self):
        article = {
            "sync_id": SYNC_ID,
            "title": TITLE,
            "manuscript": MANUSCRIPT,
            "eyecatch_url": "https://example.invalid/current.png",
            "quality_state": "Ready",
            "posting_state": "投稿準備中",
        }
        with patch.object(target, "preflight", return_value=article), \
             patch.object(target, "_apply_to_existing_draft") as apply_cover, \
             patch.object(target.note_base, "_download_eyecatch") as download:
            result = target.run(
                confirm=target.CONFIRM_TOKEN,
                sync_id=SYNC_ID,
                prepare_only=True,
            )
        self.assertEqual(result["status"], "cover_apply_ready")
        self.assertTrue(result["should_start_vm"])
        self.assertFalse(result["article_regeneration"])
        self.assertFalse(result["source_manuscript_mutation"])
        self.assertFalse(result["new_draft_created"])
        self.assertFalse(result["public_release"])
        apply_cover.assert_not_called()
        download.assert_not_called()

    def test_wrong_confirmation_fails_closed(self):
        with self.assertRaisesRegex(target.ReadyNoteCoverError, "confirmation"):
            target.run(confirm="NO", sync_id=SYNC_ID, prepare_only=True)

    def test_source_contains_no_manuscript_restamp_path(self):
        source = open(target.__file__, encoding="utf-8").read()
        self.assertNotIn("current_ready_caption(", source)
        self.assertNotIn("build_notion_manuscript_children", source)
        self.assertNotIn("/blocks/{", source)


if __name__ == "__main__":
    import unittest
    unittest.main()
