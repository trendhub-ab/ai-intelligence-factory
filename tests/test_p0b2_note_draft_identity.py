import unittest
from unittest.mock import patch

import note_draft_automation as draft


class FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code


class P0B2NoteDraftIdentityTests(unittest.TestCase):
    def test_extracts_only_opaque_identity_from_confirmed_note_edit_route(self):
        draft_id = "n0123456789abcdef0123456789abcd"
        self.assertEqual(
            draft_id,
            draft._draft_identity_from_url(f"https://note.com/notes/{draft_id}/edit"),
        )

    def test_rejects_non_note_or_non_edit_routes(self):
        for value in (
            "https://example.com/notes/n0123456789abcdef0123456789abcd/edit",
            "https://note.com/notes/n0123456789abcdef0123456789abcd",
            "https://note.com/n/n0123456789abcdef0123456789abcd",
            "",
        ):
            with self.subTest(value=value):
                with self.assertRaises(draft.NoteDraftError):
                    draft._draft_identity_from_url(value)

    def test_mark_created_persists_identity_and_preparing_status_in_one_patch(self):
        draft_id = "n0123456789abcdef0123456789abcd"
        draft_url = f"https://note.com/notes/{draft_id}/edit"
        calls = []

        def fake_request(method, url, *, json=None):
            calls.append((method, url, json))
            return FakeResponse(200)

        with patch.object(draft.ready_sync, "_request", side_effect=fake_request):
            persisted = draft._mark_draft_created("dest-page", draft_url)

        self.assertEqual(draft_id, persisted)
        self.assertEqual(1, len(calls))
        self.assertEqual("PATCH", calls[0][0])
        props = calls[0][2]["properties"]
        self.assertEqual(
            draft.PREPARING_STATUS,
            props["投稿状態"]["select"]["name"],
        )
        self.assertEqual(
            draft_id,
            props[draft.DRAFT_ID_PROPERTY]["rich_text"][0]["text"]["content"],
        )

    def test_invalid_identity_fails_before_any_notion_status_mutation(self):
        calls = []

        def fake_request(*args, **kwargs):
            calls.append((args, kwargs))
            return FakeResponse(200)

        with patch.object(draft.ready_sync, "_request", side_effect=fake_request):
            with self.assertRaises(draft.NoteDraftError):
                draft._mark_draft_created("dest-page", "https://note.com/not-an-edit-route")

        self.assertEqual([], calls)

    def test_failed_identity_patch_fails_closed(self):
        calls = []

        def fake_request(method, url, *, json=None):
            calls.append((method, url, json))
            return FakeResponse(500)

        with patch.object(draft.ready_sync, "_request", side_effect=fake_request):
            with self.assertRaisesRegex(draft.NoteDraftError, "identity/status update failed"):
                draft._mark_draft_created(
                    "dest-page",
                    "https://note.com/notes/n0123456789abcdef0123456789abcd/edit",
                )

        self.assertEqual(1, len(calls))

    def test_run_binds_verified_draft_url_before_telegram_notice(self):
        article = {
            "sync_id": "123456781234123412341234567890ab",
            "title": "Title",
            "destination_page_id": "dest-page",
            "eyecatch_url": "https://example.com/image.png",
            "manuscript": "# Title\n\n" + ("本文" * 120),
        }
        draft_url = "https://note.com/notes/n0123456789abcdef0123456789abcd/edit"
        events = []

        class TempPath:
            def unlink(self, missing_ok=False):
                events.append("storage_cleanup")

        with patch.object(draft, "_prepare_article", return_value=article), \
             patch.object(draft, "_download_eyecatch", return_value=object()), \
             patch.object(draft, "_decode_storage_state", return_value=TempPath()), \
             patch.object(draft, "_create_browser_draft", return_value=draft_url), \
             patch.object(draft, "_mark_draft_created", side_effect=lambda page_id, url: events.append(("bind", page_id, url)) or "n0123456789abcdef0123456789abcd"), \
             patch.object(draft, "_send_telegram_draft_notice", side_effect=lambda url: events.append(("telegram", url)) or True):
            result = draft.run(confirm=draft.CONFIRM_TOKEN)

        bind_index = events.index(("bind", "dest-page", draft_url))
        telegram_index = events.index(("telegram", draft_url))
        self.assertLess(bind_index, telegram_index)
        self.assertEqual("draft_created", result["status"])


if __name__ == "__main__":
    unittest.main()
