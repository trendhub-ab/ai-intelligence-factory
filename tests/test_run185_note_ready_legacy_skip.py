import unittest
from unittest.mock import patch

import note_draft_automation as base
import run185_note_ready_legacy_skip as run185


def rt(value):
    return {"rich_text": [{"type": "text", "plain_text": value, "text": {"content": value}}]}


def title(value):
    return {"title": [{"type": "text", "plain_text": value, "text": {"content": value}}]}


def queue_page(sync_id, article_title, *, created):
    return {
        "id": "dest-" + sync_id[-6:],
        "created_time": created,
        "properties": {
            "品質状態": {"select": {"name": "Ready"}},
            "投稿状態": {"select": {"name": "投稿待ち"}},
            "同期ID": rt(sync_id),
            "記事タイトル": title(article_title),
            "投稿予定日": {"date": None},
        },
    }


def code_block(body, caption="AIIF_MANUSCRIPT:READY"):
    return {
        "type": "code",
        "code": {
            "rich_text": [{"plain_text": body, "text": {"content": body}}],
            "caption": ([{"plain_text": caption, "text": {"content": caption}}] if caption else []),
        },
    }


class Run185NoteReadyLegacySkipTests(unittest.TestCase):
    def test_control_marker_detection_is_line_scoped(self):
        self.assertTrue(run185._contains_paid_control_marker("前半\n---有料エリア---\n後半"))
        self.assertTrue(run185._contains_paid_control_marker("前半\nここから 有料エリア\n後半"))
        self.assertFalse(
            run185._contains_paid_control_marker(
                "この記事では有料エリアという古い運用について説明します。"
            )
        )

    def test_default_prepare_skips_legacy_marker_and_uses_next_candidate(self):
        old = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        clean = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        pages = [
            queue_page(old, "old", created="2026-07-01T00:00:00.000Z"),
            queue_page(clean, "clean", created="2026-08-01T00:00:00.000Z"),
        ]
        blocks = {
            old: [code_block(("A" * 220) + "\n---有料エリア---\n" + ("B" * 220))],
            clean: [code_block("C" * 450)],
        }
        source = {
            old: {"properties": {"アイキャッチ": {"files": [{"type": "external", "external": {"url": "https://example.com/old.png"}}]}}},
            clean: {"properties": {"アイキャッチ": {"files": [{"type": "external", "external": {"url": "https://example.com/clean.png"}}]}}},
        }
        with patch.object(base.ready_sync, "NOTION_API_KEY", "x"), \
             patch.object(base.ready_sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(base, "_query_ready_queue", return_value=pages), \
             patch.object(base, "_fetch_block_children", side_effect=lambda sid: blocks[sid]), \
             patch.object(base, "_fetch_source_page", side_effect=lambda sid: source[sid]):
            prepared = run185._prepare_article()
        self.assertEqual(clean, prepared["sync_id"])
        self.assertEqual(1, prepared["skipped_legacy_paid_marker_count"])

    def test_explicit_legacy_candidate_stays_fail_closed(self):
        sid = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        pages = [queue_page(sid, "legacy", created="2026-07-01T00:00:00.000Z")]
        blocks = [code_block(("A" * 220) + "\n---有料エリア---\n" + ("B" * 220))]
        source = {"properties": {"アイキャッチ": {"files": [{"type": "external", "external": {"url": "https://example.com/a.png"}}]}}}
        with patch.object(base.ready_sync, "NOTION_API_KEY", "x"), \
             patch.object(base.ready_sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(base, "_query_ready_queue", return_value=pages), \
             patch.object(base, "_fetch_block_children", return_value=blocks), \
             patch.object(base, "_fetch_source_page", return_value=source):
            with self.assertRaises(run185.UnsafeLegacyPaidMarker):
                run185._prepare_article(sid)

    def test_manuscript_allows_ordinary_paid_area_prose(self):
        body = ("通常本文です。" * 25) + "\nこの記事では有料エリアという古い運用について説明します。"
        manuscript = run185._manuscript_from_blocks([code_block(body)])
        self.assertIn("有料エリアという古い運用", manuscript)


if __name__ == "__main__":
    unittest.main()
