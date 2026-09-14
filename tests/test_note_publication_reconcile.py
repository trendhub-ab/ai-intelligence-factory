import unittest
from unittest.mock import patch

import note_publication_reconcile as reconcile


def rt(value):
    return {"rich_text": [{"plain_text": value, "text": {"content": value}}]}


def title(value):
    return {"title": [{"plain_text": value, "text": {"content": value}}]}


def queue_page(*, page_id="dest", sync_id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", title_value="記事 A",
               status="投稿準備中", public_url="", published=""):
    return {
        "id": page_id,
        "properties": {
            "同期ID": rt(sync_id),
            "記事タイトル": title(title_value),
            "品質状態": {"select": {"name": "Ready"}},
            "投稿状態": {"select": {"name": status}},
            "note公開URL": {"url": public_url or None},
            "投稿日": {"date": {"start": published}} if published else {"date": None},
        },
    }


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class PublicationReconcileTests(unittest.TestCase):
    def test_canonical_public_url_rejects_other_users_and_query_noise(self):
        self.assertEqual(
            "https://note.com/trendhub_biz/n/nabc123",
            reconcile._canonical_public_url("https://note.com/trendhub_biz/n/nabc123?from=share"),
        )
        self.assertEqual("", reconcile._canonical_public_url("https://note.com/other/n/nabc123"))
        self.assertEqual("", reconcile._canonical_public_url("http://note.com/trendhub_biz/n/nabc123"))

    def test_publication_date_uses_japan_calendar_day(self):
        self.assertEqual("2026-09-14", reconcile._publication_date("Sun, 13 Sep 2026 15:30:00 +0000"))
        self.assertEqual("", reconcile._publication_date("not a date"))

    def test_exact_public_match_updates_source_then_queue_without_models(self):
        sync_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        row = queue_page(sync_id=sync_id, title_value="記事 A")
        feed = [{"title": "記事 A", "url": "https://note.com/trendhub_biz/n/nabc123", "published": "2026-09-14"}]
        source_page = {
            "id": sync_id,
            "properties": {
                "note記事タイトル": rt("記事 A"),
                "記事状態": {"select": {"name": "Ready"}},
                "公開日": {"date": None},
            },
        }
        calls = []

        def fake_request(method, url, *, json=None):
            calls.append((method, url, json))
            if method == "GET":
                return FakeResponse(200, source_page)
            return FakeResponse(200, {})

        with patch.object(reconcile.sync, "NOTION_API_KEY", "token"), \
             patch.object(reconcile.sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(reconcile.sync, "DEST_DATABASE_ID", ""), \
             patch.object(reconcile, "NOTE_USER_NAME", "trendhub_biz"), \
             patch.object(reconcile, "_fetch_feed", return_value=feed), \
             patch.object(reconcile.sync, "_query_db", return_value=[row]), \
             patch.object(reconcile.sync, "_request", side_effect=fake_request):
            result = reconcile.reconcile_publications(today="2026-09-14")

        self.assertEqual(result["reconciled"], 1)
        self.assertEqual(result["source_updates"], 1)
        self.assertEqual(result["queue_updates"], 1)
        self.assertEqual(result["model_calls"], 0)
        self.assertFalse(result["public_release"])
        patch_calls = [c for c in calls if c[0] == "PATCH"]
        self.assertEqual(len(patch_calls), 2)
        self.assertIn(f"/pages/{sync_id}", patch_calls[0][1])
        self.assertEqual(patch_calls[0][2]["properties"]["公開日"]["date"]["start"], "2026-09-14")
        self.assertEqual(patch_calls[1][2]["properties"]["投稿状態"]["select"]["name"], "投稿済み")
        self.assertEqual(patch_calls[1][2]["properties"]["note公開URL"]["url"], feed[0]["url"])

    def test_no_feed_match_is_noop(self):
        with patch.object(reconcile.sync, "NOTION_API_KEY", "token"), \
             patch.object(reconcile.sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(reconcile, "NOTE_USER_NAME", "trendhub_biz"), \
             patch.object(reconcile, "_fetch_feed", return_value=[]), \
             patch.object(reconcile.sync, "_query_db", return_value=[queue_page()]), \
             patch.object(reconcile.sync, "_request") as request:
            result = reconcile.reconcile_publications(today="2026-09-14")
        self.assertEqual(result["not_yet_public"], 1)
        self.assertEqual(result["reconciled"], 0)
        request.assert_not_called()

    def test_duplicate_queue_title_fails_closed(self):
        rows = [queue_page(page_id="one"), queue_page(page_id="two", sync_id="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")]
        feed = [{"title": "記事 A", "url": "https://note.com/trendhub_biz/n/nabc123", "published": "2026-09-14"}]
        with patch.object(reconcile.sync, "NOTION_API_KEY", "token"), \
             patch.object(reconcile.sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(reconcile, "NOTE_USER_NAME", "trendhub_biz"), \
             patch.object(reconcile, "_fetch_feed", return_value=feed), \
             patch.object(reconcile.sync, "_query_db", return_value=rows), \
             patch.object(reconcile.sync, "_request") as request:
            result = reconcile.reconcile_publications(today="2026-09-14")
        self.assertEqual(result["ambiguous"], 2)
        self.assertEqual(result["reconciled"], 0)
        request.assert_not_called()

    def test_conflicting_existing_public_url_is_never_overwritten(self):
        sync_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        row = queue_page(sync_id=sync_id, public_url="https://note.com/trendhub_biz/n/nother")
        feed = [{"title": "記事 A", "url": "https://note.com/trendhub_biz/n/nabc123", "published": "2026-09-14"}]
        source_page = {
            "id": sync_id,
            "properties": {
                "note記事タイトル": rt("記事 A"),
                "記事状態": {"select": {"name": "Ready"}},
                "公開日": {"date": None},
            },
        }
        calls = []

        def fake_request(method, url, *, json=None):
            calls.append((method, url, json))
            if method == "GET":
                return FakeResponse(200, source_page)
            return FakeResponse(200, {})

        with patch.object(reconcile.sync, "NOTION_API_KEY", "token"), \
             patch.object(reconcile.sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(reconcile, "NOTE_USER_NAME", "trendhub_biz"), \
             patch.object(reconcile, "_fetch_feed", return_value=feed), \
             patch.object(reconcile.sync, "_query_db", return_value=[row]), \
             patch.object(reconcile.sync, "_request", side_effect=fake_request):
            result = reconcile.reconcile_publications(today="2026-09-14")

        self.assertEqual(result["conflict"], 1)
        # Source may be patched first, but the conflicting queue URL is never overwritten.
        queue_patches = [c for c in calls if c[0] == "PATCH" and c[1].endswith("/dest")]
        self.assertEqual(queue_patches, [])

    def test_already_reconciled_is_idempotent(self):
        sync_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        url = "https://note.com/trendhub_biz/n/nabc123"
        row = queue_page(sync_id=sync_id, status="投稿済み", public_url=url, published="2026-09-14")
        feed = [{"title": "記事 A", "url": url, "published": "2026-09-14"}]
        source_page = {
            "id": sync_id,
            "properties": {
                "note記事タイトル": rt("記事 A"),
                "記事状態": {"select": {"name": "Ready"}},
                "公開日": {"date": {"start": "2026-09-14"}},
            },
        }

        def fake_request(method, url, *, json=None):
            if method == "GET":
                return FakeResponse(200, source_page)
            self.fail("idempotent reconciliation must not PATCH")

        with patch.object(reconcile.sync, "NOTION_API_KEY", "token"), \
             patch.object(reconcile.sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(reconcile, "NOTE_USER_NAME", "trendhub_biz"), \
             patch.object(reconcile, "_fetch_feed", return_value=feed), \
             patch.object(reconcile.sync, "_query_db", return_value=[row]), \
             patch.object(reconcile.sync, "_request", side_effect=fake_request):
            result = reconcile.reconcile_publications(today="2026-09-14")

        self.assertEqual(result["already_reconciled"], 1)
        self.assertEqual(result["reconciled"], 0)


if __name__ == "__main__":
    unittest.main()
