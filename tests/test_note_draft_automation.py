import inspect
import unittest
from datetime import date
from pathlib import Path

import note_draft_automation as draft


ROOT = Path(__file__).resolve().parents[1]


def rt(value):
    return {"rich_text": [{"type": "text", "plain_text": value, "text": {"content": value}}]}


def title(value):
    return {"title": [{"type": "text", "plain_text": value, "text": {"content": value}}]}


def queue_page(sync_id, article_title, *, status="投稿待ち", quality="Ready", scheduled="", created="2026-08-01T00:00:00.000Z"):
    return {
        "id": "dest-" + sync_id[-6:],
        "created_time": created,
        "properties": {
            "品質状態": {"select": {"name": quality}},
            "投稿状態": {"select": {"name": status}},
            "同期ID": rt(sync_id),
            "記事タイトル": title(article_title),
            "投稿予定日": {"date": {"start": scheduled} if scheduled else None},
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


class NoteDraftAutomationTests(unittest.TestCase):
    def test_candidate_accepts_only_ready_waiting(self):
        sid = "123456781234123412341234567890ab"
        self.assertIsNotNone(draft._candidate_from_page(queue_page(sid, "title")))
        self.assertIsNone(draft._candidate_from_page(queue_page(sid, "title", status="投稿準備中")))
        self.assertIsNone(draft._candidate_from_page(queue_page(sid, "title", quality="Ready取消")))

    def test_default_selection_prefers_due_schedule_and_excludes_future(self):
        a = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        b = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        c = "cccccccccccccccccccccccccccccccc"
        pages = [
            queue_page(a, "unscheduled", created="2026-07-01T00:00:00.000Z"),
            queue_page(b, "due", scheduled="2026-09-01", created="2026-08-02T00:00:00.000Z"),
            queue_page(c, "future", scheduled="2026-09-10", created="2026-06-01T00:00:00.000Z"),
        ]
        selected = draft._select_candidate(pages, today=date(2026, 9, 2))
        self.assertEqual(b, selected["sync_id"])

    def test_explicit_sync_id_is_exact_and_still_requires_ready_waiting(self):
        a = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        b = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        pages = [queue_page(a, "A"), queue_page(b, "B", status="投稿準備中")]
        self.assertEqual(a, draft._select_candidate(pages, requested_sync_id=a)["sync_id"])
        with self.assertRaises(draft.NoteDraftError):
            draft._select_candidate(pages, requested_sync_id=b)

    def test_manuscript_prefers_ready_caption_and_preserves_chunk_boundary(self):
        ready1 = ("A" * 110) + "\n"
        ready2 = ("B" * 110) + "\nEND"
        legacy = "LEGACY " * 40
        review = "REVIEW " * 40
        blocks = [
            code_block(legacy, ""),
            code_block(ready1),
            code_block(review, "AIIF_MANUSCRIPT:NEEDS_EDITORIAL_REVIEW"),
            code_block(ready2),
        ]
        manuscript = draft._manuscript_from_blocks(blocks)
        self.assertEqual(ready1 + ready2, manuscript)
        self.assertNotIn("LEGACY", manuscript)
        self.assertNotIn("REVIEW", manuscript)

    def test_eyecatch_url_supports_external_and_notion_file(self):
        external = {"properties": {"アイキャッチ": {"files": [{"type": "external", "external": {"url": "https://example.com/a.png"}}]}}}
        notion_file = {"properties": {"アイキャッチ": {"files": [{"type": "file", "file": {"url": "https://example.com/b.png"}}]}}}
        self.assertEqual("https://example.com/a.png", draft._eyecatch_url(external))
        self.assertEqual("https://example.com/b.png", draft._eyecatch_url(notion_file))

    def test_markdown_converter_keeps_editorial_structure_and_escapes_raw_html(self):
        source = "## 見出し\n\n**重要**です。\n\n- A\n- B\n\n[詳細](https://example.com)\n\n<script>alert(1)</script>"
        rendered = draft._markdown_to_safe_html(source)
        self.assertIn("<h2>見出し</h2>", rendered)
        self.assertIn("<strong>重要</strong>", rendered)
        self.assertIn("<ul>", rendered)
        self.assertIn('<a href="https://example.com">詳細</a>', rendered)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_persistence_check_is_read_only_for_title(self):
        source = inspect.getsource(draft._save_draft_and_verify)
        self.assertNotIn("_set_title(page, title)", source)
        self.assertIn("_find_title", source)

    def test_run184_has_zero_gemini_and_no_release_control(self):
        source = (ROOT / "note_draft_automation.py").read_text(encoding="utf-8")
        self.assertNotIn("_generate_via_chat", source)
        self.assertNotIn("GEMINI_API_KEY", source)
        self.assertNotIn("公開に進む", source)
        self.assertNotIn("投稿する", source)
        self.assertIn("PREPARING_STATUS = \"投稿準備中\"", source)

    def test_workflow_is_manual_only_and_secret_safe(self):
        source = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", source)
        self.assertNotIn("workflow_run:", source)
        self.assertNotIn("schedule:", source)
        self.assertNotIn("push:", source)
        self.assertIn("NOTE_STORAGE_STATE_B64", source)
        self.assertIn("CREATE_NOTE_DRAFT", source)
        self.assertNotIn("upload-artifact", source)


if __name__ == "__main__":
    unittest.main()
