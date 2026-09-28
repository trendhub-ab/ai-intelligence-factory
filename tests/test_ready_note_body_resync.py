from __future__ import annotations

import types
from unittest import TestCase
from unittest.mock import patch

import ready_note_body_resync as target


SYNC_ID = "3e8479ffdca9812e9661f337a84b1df4"
TITLE = "AIの巨人はどこから生まれたのか。2015年、非営利スタートアップ「OpenAI」が掲げた理想と出発点。"
MANUSCRIPT = "## どんな内容？\nOpenAIの設立時点を確認します。\n\n## なぜ重要？\n原点を確認するためです。"


class ReadyNoteBodyResyncTests(TestCase):
    def test_sync_id_is_exact_hex_only(self):
        self.assertEqual(target._normalize_sync_id(SYNC_ID), SYNC_ID)
        with self.assertRaises(target.ReadyNoteBodyResyncError):
            target._normalize_sync_id("3e8479ff-dca9-812e-9661-f337a84b1df4")

    def test_preflight_reconciles_only_after_current_source_proof(self):
        before = {
            "destination_page_id": "dest",
            "sync_id": SYNC_ID,
            "title": TITLE,
            "quality_state": "Ready取消",
            "posting_state": "投稿準備中",
        }
        after = dict(before, quality_state="Ready")
        article = {
            "sync_id": SYNC_ID,
            "title": TITLE,
            "manuscript": MANUSCRIPT,
            "canonical_sha256": "abc",
            "eyecatch_url": "https://example.invalid/current.png",
        }
        with patch.object(target, "_destination_private_row", side_effect=[before, after]), \
             patch.object(target, "_source_current_article", return_value=article) as source, \
             patch.object(target.ready_sync, "sync_note_ready_db", return_value={"source_ready": 1}) as sync:
            result = target.preflight(SYNC_ID)
        source.assert_called_once_with(SYNC_ID, TITLE)
        sync.assert_called_once_with(target_sync_id=SYNC_ID)
        self.assertEqual(result["quality_state_before"], "Ready取消")
        self.assertEqual(result["quality_state"], "Ready")
        self.assertEqual(result["posting_state"], "投稿準備中")

    def test_preflight_does_not_sync_when_source_is_not_current(self):
        before = {
            "destination_page_id": "dest",
            "sync_id": SYNC_ID,
            "title": TITLE,
            "quality_state": "Ready取消",
            "posting_state": "投稿準備中",
        }
        with patch.object(target, "_destination_private_row", return_value=before), \
             patch.object(target, "_source_current_article", side_effect=target.ReadyNoteBodyResyncError("stale source")), \
             patch.object(target.ready_sync, "sync_note_ready_db") as sync:
            with self.assertRaisesRegex(target.ReadyNoteBodyResyncError, "stale source"):
                target.preflight(SYNC_ID)
        sync.assert_not_called()

    def test_prepare_only_never_opens_or_mutates_note(self):
        article = {
            "sync_id": SYNC_ID,
            "title": TITLE,
            "manuscript": MANUSCRIPT,
            "quality_state_before": "Ready取消",
            "quality_state": "Ready",
            "posting_state": "投稿準備中",
        }
        with patch.object(target, "preflight", return_value=article), \
             patch.object(target, "_apply_existing_body") as apply:
            result = target.run(
                confirm=target.CONFIRM_TOKEN,
                sync_id=SYNC_ID,
                prepare_only=True,
            )
        self.assertEqual(result["status"], "body_resync_ready")
        self.assertTrue(result["should_start_vm"])
        self.assertFalse(result["new_draft_created"])
        self.assertFalse(result["public_release"])
        self.assertFalse(result["article_regeneration"])
        self.assertFalse(result["source_manuscript_mutation"])
        apply.assert_not_called()

    def test_wrong_confirmation_fails_closed(self):
        with self.assertRaisesRegex(target.ReadyNoteBodyResyncError, "confirmation"):
            target.run(confirm="NO", sync_id=SYNC_ID, prepare_only=True)

    def test_source_contains_no_source_manuscript_write_path(self):
        source = open(target.__file__, encoding="utf-8").read()
        self.assertNotIn("current_ready_caption(", source)
        self.assertNotIn("build_notion_manuscript_children", source)
        self.assertNotIn("/blocks/{", source)


if __name__ == "__main__":
    import unittest
    unittest.main()
