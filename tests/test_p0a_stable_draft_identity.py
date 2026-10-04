from __future__ import annotations

# GREEN trigger: stable identity implementation is now under contract.
import sys
import types
import unittest
from contextlib import contextmanager
from unittest import mock

import run291_note_private_draft_audit as audit


SYNC_ID = "a" * 32
DRAFT_ID = "nStable_Draft-123"


def _page(*, draft_id: str | None = DRAFT_ID) -> dict:
    props = {
        "同期ID": {"rich_text": [{"plain_text": SYNC_ID}]},
        "記事タイトル": {"title": [{"plain_text": "Expected title"}]},
        "品質状態": {"select": {"name": "Ready"}},
        "投稿状態": {"select": {"name": "投稿準備中"}},
        "note公開URL": {"url": None},
        "投稿日": {"date": None},
    }
    if draft_id is not None:
        props["note下書きID"] = {"rich_text": [{"plain_text": draft_id}]}
    return {"id": "destination-page", "properties": props}


class _FakePage:
    def __init__(self) -> None:
        self.url = "https://note.com/"
        self.goto_calls: list[str] = []

    def goto(self, url, *args, **kwargs):
        self.goto_calls.append(str(url))
        self.url = str(url)
        return None

    def wait_for_timeout(self, *args, **kwargs):
        return None

    def set_default_timeout(self, *args, **kwargs):
        return None


class _FakeContext:
    def __init__(self) -> None:
        self.page = _FakePage()

    def new_page(self):
        return self.page

    def close(self):
        return None


class _FakePlaywrightManager:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


@contextmanager
def _fake_playwright_import():
    package = types.ModuleType("playwright")
    package.__path__ = []
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: _FakePlaywrightManager()
    package.sync_api = sync_api
    with mock.patch.dict(sys.modules, {"playwright": package, "playwright.sync_api": sync_api}):
        yield


class StableDraftIdentityContractTests(unittest.TestCase):
    def test_destination_row_requires_persisted_private_draft_identity(self) -> None:
        with mock.patch.object(audit.ready_sync, "_query_db", return_value=[_page(draft_id=None)]):
            with self.assertRaises(audit.PrivateDraftAuditError) as caught:
                audit._destination_row(SYNC_ID)
        self.assertIn("identity", str(caught.exception).lower())

    def test_destination_row_returns_opaque_private_draft_identity(self) -> None:
        with mock.patch.object(audit.ready_sync, "_query_db", return_value=[_page()]):
            row = audit._destination_row(SYNC_ID)
        self.assertEqual(row["draft_id"], DRAFT_ID)
        self.assertNotIn("https://", row["draft_id"])

    def test_browser_audit_navigates_directly_and_never_reads_history(self) -> None:
        context = _FakeContext()
        article = {"title": "Expected title", "manuscript": "approved body", "draft_id": DRAFT_ID}
        private_url = f"https://note.com/notes/{DRAFT_ID}/edit"
        safe_metrics = {"title_match": True, "body_visible_chars": 777}

        self.assertFalse(hasattr(audit, "_recent_private_edit_urls"))
        with _fake_playwright_import(), \
             mock.patch.object(audit.run190, "_profile_dir", side_effect=AssertionError("history profile forbidden")), \
             mock.patch.object(audit.run190, "_launch_persistent_context", return_value=context), \
             mock.patch.object(audit.note_base, "_looks_logged_out", return_value=False), \
             mock.patch.object(audit.run187, "_is_editor_url", return_value=True), \
             mock.patch.object(audit, "_title_value", return_value="Expected title"):
            result = audit._browser_audit(article, page_auditor=lambda page, title, manuscript: dict(safe_metrics))

        self.assertEqual(context.page.goto_calls, [private_url])
        self.assertEqual(result, safe_metrics)
        self.assertNotIn(DRAFT_ID, str(result))
        self.assertNotIn(private_url, str(result))

    def test_malformed_private_draft_identity_fails_before_browser_or_history(self) -> None:
        bad_values = (
            "https://note.com/notes/secret/edit",
            "abc/../../secret",
            "abc?x=1",
            "abc def",
            "abc\nsecret",
        )
        for value in bad_values:
            with self.subTest(value=value), \
                 _fake_playwright_import(), \
                 mock.patch.object(audit.run190, "_launch_persistent_context", side_effect=AssertionError("browser forbidden")):
                with self.assertRaises(audit.PrivateDraftAuditError):
                    audit._browser_audit({"title": "Expected title", "manuscript": "body", "draft_id": value})


if __name__ == "__main__":
    unittest.main()
