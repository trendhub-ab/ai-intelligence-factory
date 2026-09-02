from __future__ import annotations

import inspect
import json
import os
import tempfile
import unittest
from pathlib import Path
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
        self.newer_body = "同じ品質世代で再生成された新しい記事です。" * 30
        self.legacy_body = "過去の品質ロジックで生成された記事です。" * 30

    def current_block(self, body: str) -> dict:
        return code_block(body, contract.current_ready_caption(body))

    def test_latest_byte_valid_current_manuscript_is_selected(self) -> None:
        blocks = [
            code_block(self.legacy_body, contract.LEGACY_READY_CAPTION),
            self.current_block(self.current_body),
            self.current_block(self.newer_body),
        ]
        self.assertEqual(self.newer_body, run194._manuscript_from_blocks(blocks))

    def test_body_tamper_invalidates_current_caption(self) -> None:
        caption = contract.current_ready_caption(self.current_body)
        with self.assertRaises(run194.StalePublicationContract):
            run194._manuscript_from_blocks([code_block(self.current_body + "tampered", caption)])

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
            run194._manuscript_from_blocks([self.current_block(body)])

    def _candidate(self, sync_id: str) -> dict:
        return {
            "destination_page_id": "dest-" + sync_id[:4],
            "sync_id": sync_id,
            "title": "title-" + sync_id[:4],
            "scheduled_date": "",
            "created_time": "2026-09-01T00:00:00.000Z",
        }

    def test_automatic_selection_skips_stale_and_missing_eyecatch(self) -> None:
        stale_id = "1" * 32
        no_image_id = "2" * 32
        current_id = "3" * 32
        candidates = [
            self._candidate(stale_id),
            self._candidate(no_image_id),
            self._candidate(current_id),
        ]

        def children(sync_id: str):
            if sync_id == stale_id:
                return [code_block(self.legacy_body, contract.LEGACY_READY_CAPTION)]
            return [self.current_block(self.current_body)]

        def image(source_page):
            return source_page.get("image", "")

        with (
            patch.object(base.ready_sync, "NOTION_API_KEY", "test"),
            patch.object(base.ready_sync, "DEST_DATA_SOURCE_ID", "dest"),
            patch.object(base, "_query_ready_queue", return_value=[]),
            patch.object(run185, "_ordered_candidates", return_value=candidates),
            patch.object(
                base,
                "_fetch_source_page",
                side_effect=lambda sid: {"image": "https://example.com/current.png" if sid == current_id else ""},
            ),
            patch.object(base, "_fetch_block_children", side_effect=children),
            patch.object(base, "_eyecatch_url", side_effect=image),
        ):
            prepared = run194._prepare_article()

        self.assertEqual(current_id, prepared["sync_id"])
        self.assertEqual(1, prepared["skipped_stale_contract_count"])
        self.assertEqual(1, prepared["skipped_incomplete_asset_count"])
        self.assertEqual(contract.CONTRACT_ID, prepared["publication_contract"])
        self.assertEqual(contract.manuscript_sha256(self.current_body), prepared["manuscript_sha256"])

    def test_explicit_missing_eyecatch_never_silently_switches(self) -> None:
        sid = "4" * 32
        candidate = self._candidate(sid)
        with (
            patch.object(base.ready_sync, "NOTION_API_KEY", "test"),
            patch.object(base.ready_sync, "DEST_DATA_SOURCE_ID", "dest"),
            patch.object(base, "_query_ready_queue", return_value=[]),
            patch.object(run185, "_ordered_candidates", return_value=[candidate]),
            patch.object(base, "_fetch_source_page", return_value={}),
            patch.object(base, "_fetch_block_children", return_value=[self.current_block(self.current_body)]),
            patch.object(base, "_eyecatch_url", return_value=""),
        ):
            with self.assertRaises(run194.IncompletePublicationAsset):
                run194._prepare_article(sid)

    def test_explicit_stale_sync_id_never_silently_switches(self) -> None:
        stale_id = "5" * 32
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

    def test_automatic_empty_queue_is_successful_noop_and_writes_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result_file = Path(tmpdir) / "note_result.json"
            env = {
                "NOTE_TARGET_SYNC_ID": "",
                "NOTE_DRAFT_RESULT_FILE": str(result_file),
            }
            with (
                patch.dict(os.environ, env, clear=False),
                patch.object(
                    base,
                    "main",
                    side_effect=base.NoteDraftError("No eligible Ready / 投稿待ち article is available"),
                ),
            ):
                result = run194.run_base_main_with_safe_noop()

            self.assertEqual("no_eligible_ready", result["status"])
            self.assertTrue(result["zero_gemini_calls"])
            self.assertFalse(result["telegram_notified"])
            persisted = json.loads(result_file.read_text(encoding="utf-8"))
            self.assertEqual("no_eligible_ready", persisted["status"])
            self.assertEqual(contract.CONTRACT_ID, persisted["publication_contract"])

    def test_automatic_all_current_candidates_rejected_is_also_safe_noop(self) -> None:
        with patch.dict(os.environ, {"NOTE_TARGET_SYNC_ID": ""}, clear=False), patch.object(
            base,
            "main",
            side_effect=base.NoteDraftError(
                "No complete current publication-contract Ready article is available "
                "(stale_skipped=2, asset_skipped=1, paid_marker_skipped=0)"
            ),
        ):
            result = run194.run_base_main_with_safe_noop()
        self.assertEqual("no_eligible_ready", result["status"])

    def test_explicit_sync_id_empty_queue_remains_fail_closed(self) -> None:
        with patch.dict(os.environ, {"NOTE_TARGET_SYNC_ID": "a" * 32}, clear=False), patch.object(
            base,
            "main",
            side_effect=base.NoteDraftError("No eligible Ready / 投稿待ち article is available"),
        ):
            with self.assertRaises(base.NoteDraftError):
                run194.run_base_main_with_safe_noop()

    def test_unrelated_note_error_remains_fail_closed(self) -> None:
        with patch.dict(os.environ, {"NOTE_TARGET_SYNC_ID": ""}, clear=False), patch.object(
            base,
            "main",
            side_effect=base.NoteDraftError("Notion API key is not configured"),
        ):
            with self.assertRaises(base.NoteDraftError):
                run194.run_base_main_with_safe_noop()

    def test_module_adds_zero_model_and_no_public_release_action(self) -> None:
        source = inspect.getsource(run194)
        self.assertNotIn("_generate_via_chat(", source)
        self.assertNotIn("genai.Client(", source)
        self.assertNotIn("公開する", source)
        self.assertNotIn("投稿する", source)


if __name__ == "__main__":
    unittest.main()
