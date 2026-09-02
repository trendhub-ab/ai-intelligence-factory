from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import note_draft_automation as base
import publication_contract as contract
import run185_note_ready_legacy_skip as run185
import run194_note_current_contract as run194


def code_block(body: str, caption: str = "") -> dict:
    return {
        "type": "code",
        "code": {
            "rich_text": [{"plain_text": body, "text": {"content": body}}],
            "caption": (
                [{"plain_text": caption, "text": {"content": caption}}]
                if caption
                else []
            ),
        },
    }


class Run194NoteCurrentContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.current_body = "現在の品質契約で生成された記事です。" * 30
        self.legacy_body = "過去の品質ロジックで生成された記事です。" * 30

    def test_current_caption_is_required_and_selected_over_legacy(self) -> None:
        blocks = [
            code_block(self.legacy_body, contract.LEGACY_READY_CAPTION),
            code_block(self.current_body, contract.CURRENT_READY_CAPTION),
        ]
        self.assertEqual(self.current_body, run194._manuscript_from_blocks(blocks))

    def test_legacy_ready_only_is_fail_closed(self) -> None:
        with self.assertRaises(run194.StalePublicationContract):
            run194._manuscript_from_blocks(
                [code_block(self.legacy_body, contract.LEGACY_READY_CAPTION)]
            )

    def test_captionless_legacy_ready_is_fail_closed(self) -> None:
        with self.assertRaises(run194.StalePublicationContract):
            run194._manuscript_from_blocks([code_block(self.legacy_body)])

    def test_current_manuscript_still_rejects_paid_control_marker(self) -> None:
        body = self.current_body + "\n**▼▼▼ ここから先は有料エリアです ▼▼▼**\n" + self.current_body
        with self.assertRaises(run185.UnsafeLegacyPaidMarker):
            run194._manuscript_from_blocks(
                [code_block(body, contract.CURRENT_READY_CAPTION)]
            )

    def _candidate(self, sync_id: str) -> dict:
        return {
            "destination_page_id": "dest-" + sync_id[:4],
            "sync_id": sync_id,
            "title": "title-" + sync_id[:4],
            "scheduled_date": "",
            "created_time": "2026-09-01T00:00:00.000Z",
        }

    def test_automatic_selection_skips_stale_and_uses_current(self) -> None:
        stale_id = "1" * 32
        current_id = "2" * 32
        candidates = [self._candidate(stale_id), self._candidate(current_id)]

        def children(sync_id: str):
            if sync_id == stale_id:
                return [code_block(self.legacy_body, contract.LEGACY_READY_CAPTION)]
            return [code_block(self.current_body, contract.CURRENT_READY_CAPTION)]

        with (
            patch.object(base.ready_sync, "NOTION_API_KEY", "test"),
            patch.object(base.ready_sync, "DEST_DATA_SOURCE_ID", "dest"),
            patch.object(base, "_query_ready_queue", return_value=[]),
            patch.object(run185, "_ordered_candidates", return_value=candidates),
            patch.object(base, "_fetch_source_page", return_value={}),
            patch.object(base, "_fetch_block_children", side_effect=children),
            patch.object(base, "_eyecatch_url", return_value="https://example.com/current.png"),
        ):
            prepared = run194._prepare_article()

        self.assertEqual(current_id, prepared["sync_id"])
        self.assertEqual(1, prepared["skipped_stale_contract_count"])
        self.assertEqual(contract.CONTRACT_ID, prepared["publication_contract"])

    def test_explicit_stale_sync_id_never_silently_switches(self) -> None:
        stale_id = "3" * 32
        candidate = self._candidate(stale_id)
        with (
            patch.object(base.ready_sync, "NOTION_API_KEY", "test"),
            patch.object(base.ready_sync, "DEST_DATA_SOURCE_ID", "dest"),
            patch.object(base, "_query_ready_queue", return_value=[]),
            patch.object(run185, "_ordered_candidates", return_value=[candidate]),
            patch.object(base, "_fetch_source_page", return_value={}),
            patch.object(
                base,
                "_fetch_block_children",
                return_value=[code_block(self.legacy_body, contract.LEGACY_READY_CAPTION)],
            ),
        ):
            with self.assertRaises(run194.StalePublicationContract):
                run194._prepare_article(stale_id)

    def test_module_adds_zero_model_and_no_public_release_action(self) -> None:
        source = inspect.getsource(run194)
        self.assertNotIn("_generate_via_chat(", source)
        self.assertNotIn("genai.Client(", source)
        self.assertNotIn("公開する", source)
        self.assertNotIn("投稿する", source)


if __name__ == "__main__":
    unittest.main()
