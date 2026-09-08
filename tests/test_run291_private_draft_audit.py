from __future__ import annotations

import inspect
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.Response = object
    requests_stub.RequestException = Exception
    requests_stub.request = lambda *args, **kwargs: None
    requests_stub.get = lambda *args, **kwargs: None
    requests_stub.post = lambda *args, **kwargs: None
    sys.modules["requests"] = requests_stub

import run291_note_private_draft_audit as audit


class Run291UrlAndHistoryTests(unittest.TestCase):
    def test_note_edit_route_gate_is_narrow(self) -> None:
        self.assertTrue(audit._is_note_edit_url("https://editor.note.com/notes/n123/edit/"))
        self.assertTrue(audit._is_note_edit_url("https://note.com/notes/n123/edit"))
        for value in (
            "http://editor.note.com/notes/n123/edit",
            "https://note.com/new",
            "https://note.com/notes/n123",
            "https://evilnote.com/notes/n123/edit",
            "https://editor.note.com/notes/n123/edit/extra",
        ):
            with self.subTest(value=value):
                self.assertFalse(audit._is_note_edit_url(value))

    def test_recent_history_returns_only_private_note_edit_routes_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp)
            history = profile / "Default" / "History"
            history.parent.mkdir(parents=True)
            conn = sqlite3.connect(str(history))
            try:
                conn.execute("CREATE TABLE urls (url TEXT, last_visit_time INTEGER)")
                conn.executemany(
                    "INSERT INTO urls(url, last_visit_time) VALUES (?, ?)",
                    [
                        ("https://editor.note.com/notes/old/edit/", 10),
                        ("https://editor.note.com/notes/new/edit/", 30),
                        ("https://note.com/new", 40),
                        ("https://evilnote.com/notes/leak/edit/", 50),
                        ("https://editor.note.com/notes/new/edit/", 20),
                    ],
                )
                conn.commit()
            finally:
                conn.close()

            result = audit._recent_private_edit_urls(profile)

        self.assertEqual(
            result,
            [
                "https://editor.note.com/notes/new/edit/",
                "https://editor.note.com/notes/old/edit/",
            ],
        )


class Run291BodyAuditTests(unittest.TestCase):
    def test_body_metrics_require_approved_prefix_suffix_and_sources_before_cta(self) -> None:
        manuscript = (
            "導入です。これは本文です。\n\n"
            "## 見出し\n詳しい説明です。\n\n"
            "### Sources / Evidence\n- source A\n\n"
            "### 調査と判断の時間を減らしたい方へ\nCTAです。"
        )
        actual = audit.note_base._plain_manuscript_text(manuscript)
        metrics = audit._body_text_metrics(actual, manuscript, "別のタイトル")
        self.assertTrue(metrics["prefix_match"])
        self.assertTrue(metrics["suffix_match"])
        self.assertTrue(metrics["sources_before_cta"])
        self.assertFalse(metrics["duplicate_title_prefix"])

    def test_cta_before_sources_fails_closed(self) -> None:
        manuscript = (
            "導入です。本文です。\n\n"
            "### Sources / Evidence\nsource\n\n"
            "### 調査と判断の時間を減らしたい方へ\nCTA"
        )
        actual = (
            "導入です。本文です。 調査と判断の時間を減らしたい方へ CTA "
            "Sources / Evidence source"
        )
        with self.assertRaises(audit.PrivateDraftAuditError):
            audit._body_text_metrics(actual, manuscript, "タイトル")

    def test_duplicate_title_at_body_start_fails_closed(self) -> None:
        title = "Netflixの推薦"
        manuscript = (
            "本文開始。詳しい説明です。\n\n"
            "### Sources / Evidence\nsource\n\n"
            "### 調査と判断の時間を減らしたい方へ\nCTA"
        )
        expected = audit.note_base._plain_manuscript_text(manuscript)
        with self.assertRaises(audit.PrivateDraftAuditError):
            audit._body_text_metrics(title + " " + expected, manuscript, title)


class Run291ExecutionBoundaryTests(unittest.TestCase):
    def test_prepare_only_is_zero_vm_safe_and_emits_no_unpublished_content(self) -> None:
        article = {
            "sync_id": "a" * 32,
            "title": "secret unpublished title",
            "manuscript": "secret unpublished body",
        }
        with patch.object(audit, "_expected_article", return_value=article), patch.object(
            audit, "_browser_audit"
        ) as browser:
            result = audit.run(confirm=audit.CONFIRM_TOKEN, sync_id="a" * 32, prepare_only=True)
        browser.assert_not_called()
        self.assertEqual(result["status"], "audit_ready")
        self.assertTrue(result["zero_gemini_calls"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["draft_mutation"])
        self.assertFalse(result["public_release"])
        self.assertNotIn("title", result)
        self.assertNotIn("manuscript", result)
        self.assertNotIn("draft_url", result)

    def test_full_result_keeps_draft_url_and_body_out_of_logs(self) -> None:
        article = {
            "sync_id": "b" * 32,
            "title": "secret unpublished title",
            "manuscript": "secret unpublished body",
        }
        metrics = {
            "title_match": True,
            "eyecatch_present": True,
            "editor_route_hash": "123456789abc",
        }
        with patch.object(audit, "_expected_article", return_value=article), patch.object(
            audit, "_browser_audit", return_value=metrics
        ):
            result = audit.run(confirm=audit.CONFIRM_TOKEN, sync_id="b" * 32)
        self.assertEqual(result["status"], "audit_passed")
        self.assertNotIn("title", result)
        self.assertNotIn("manuscript", result)
        self.assertNotIn("draft_url", result)

    def test_module_has_no_draft_mutation_publication_or_screenshot_surface(self) -> None:
        source = inspect.getsource(audit)
        forbidden = (
            "_mark_draft_created(",
            "_upload_header_image(",
            "_paste_manuscript(",
            "_save_draft_and_verify(",
            ".click(",
            ".fill(",
            "keyboard.press",
            "keyboard.insert_text",
            "page.screenshot(",
            "requests.post(",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
