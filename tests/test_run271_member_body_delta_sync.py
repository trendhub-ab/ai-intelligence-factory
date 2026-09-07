from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import member_ux_body_fast as fast


class Run271MemberBodyDeltaSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pages = [
            {
                "id": "old-page",
                "last_edited_time": "2026-09-06T00:00:00.000Z",
                "properties": {},
            },
            {
                "id": "new-page",
                "last_edited_time": "2026-09-07T00:00:10.000Z",
                "properties": {},
            },
        ]

    def _destination_state(self, page: dict) -> dict:
        page_id = str(page.get("id") or "")
        return {
            "page_id": page_id,
            "sync_id": page_id,
            "name": page_id,
        }

    def test_cutoff_selects_only_recent_pages(self) -> None:
        selected, scope = fast._select_delta_pages(
            self.pages,
            changed_since="2026-09-07T00:00:00Z",
            force_full=False,
        )
        self.assertEqual([page["id"] for page in selected], ["new-page"])
        self.assertEqual(scope["mode"], "delta")
        self.assertFalse(scope["force_full"])

    def test_force_full_ignores_cutoff(self) -> None:
        selected, scope = fast._select_delta_pages(
            self.pages,
            changed_since="2026-09-07T00:00:00Z",
            force_full=True,
        )
        self.assertEqual([page["id"] for page in selected], ["old-page", "new-page"])
        self.assertEqual(scope["mode"], "full_forced")
        self.assertTrue(scope["force_full"])

    def test_missing_cutoff_preserves_legacy_full_scan(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            selected, scope = fast._select_delta_pages(self.pages)
        self.assertEqual([page["id"] for page in selected], ["old-page", "new-page"])
        self.assertEqual(scope["mode"], "full_no_cutoff")

    def test_delta_sync_reads_only_changed_page_when_sentinel_matches(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    fast.CHANGED_SINCE_ENV: "2026-09-07T00:00:00Z",
                    fast.FORCE_FULL_ENV: "false",
                },
                clear=False,
            ),
            patch.object(
                fast.body.decision_intelligence,
                "NOTION_DECISION_INTELLIGENCE_API_KEY",
                "test-key",
            ),
            patch.object(fast.mps, "NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID", "ds"),
            patch.object(fast.mps, "NOTION_MEMBER_PRESENTATION_DATABASE_ID", "db"),
            patch.object(
                fast.body.decision_intelligence,
                "_query_external_db",
                return_value=self.pages,
            ),
            patch.object(fast.mps, "_destination_state", side_effect=self._destination_state),
            patch.object(fast, "_sentinel_requires_full", return_value=False) as sentinel,
            patch.object(fast.body, "_children", return_value=[]) as children,
            patch.object(fast.body, "_create_auto_callout") as create,
            patch.object(fast.body, "REQUEST_SLEEP_SECONDS", 0),
        ):
            result = fast.sync_member_page_bodies_fast()

        sentinel.assert_called_once()
        children.assert_called_once_with("new-page")
        create.assert_called_once()
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["scanned_body_pages"], 1)
        self.assertEqual(result["skipped_by_delta"], 1)
        self.assertEqual(result["created"], 1)
        self.assertFalse(result["delta_fallback_full"])

    def test_sentinel_mismatch_falls_back_to_full_scan(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    fast.CHANGED_SINCE_ENV: "2026-09-07T00:00:00Z",
                    fast.FORCE_FULL_ENV: "false",
                },
                clear=False,
            ),
            patch.object(
                fast.body.decision_intelligence,
                "NOTION_DECISION_INTELLIGENCE_API_KEY",
                "test-key",
            ),
            patch.object(fast.mps, "NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID", "ds"),
            patch.object(fast.mps, "NOTION_MEMBER_PRESENTATION_DATABASE_ID", "db"),
            patch.object(
                fast.body.decision_intelligence,
                "_query_external_db",
                return_value=self.pages,
            ),
            patch.object(fast.mps, "_destination_state", side_effect=self._destination_state),
            patch.object(fast, "_sentinel_requires_full", return_value=True),
            patch.object(fast.body, "_children", return_value=[]),
            patch.object(fast.body, "_create_auto_callout") as create,
            patch.object(fast.body, "REQUEST_SLEEP_SECONDS", 0),
        ):
            result = fast.sync_member_page_bodies_fast()

        self.assertEqual(create.call_count, 2)
        self.assertEqual(result["scanned_body_pages"], 2)
        self.assertEqual(result["skipped_by_delta"], 0)
        self.assertTrue(result["delta_fallback_full"])
        self.assertEqual(result["delta_scope"]["mode"], "full_contract_mismatch")


if __name__ == "__main__":
    unittest.main()
