from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import publication_contract as contract


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "note-ready-sync.yml"


def rt(value: str) -> dict:
    return {"rich_text": [{"type": "text", "plain_text": value, "text": {"content": value}}]}


def destination(page_id: str, sync_id: str, posting: str, quality: str = "Ready") -> dict:
    return {
        "id": page_id,
        "properties": {
            "同期ID": rt(sync_id),
            "投稿状態": {"select": {"name": posting}},
            "品質状態": {"select": {"name": quality}},
        },
    }


class Run197NoteReadyPolicyReconciliationTests(unittest.TestCase):
    def test_every_publication_policy_file_triggers_main_queue_reconciliation(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("push:\n", source)
        self.assertIn("branches: [main]", source)
        self.assertIn("github.event_name == 'push'", source)
        for relative in contract.PUBLICATION_POLICY_FILES:
            self.assertIn(
                f"- '{relative}'",
                source,
                msg=f"publication policy change would leave Note Ready queue stale: {relative}",
            )
        for operational in (
            "note_ready_sync.py",
            ".github/workflows/note-ready-sync.yml",
            "tests/test_run197_note_ready_policy_reconciliation.py",
        ):
            self.assertIn(f"- '{operational}'", source)

    def test_policy_change_reconciliation_remains_zero_model_and_never_opens_note_browser(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("GEMINI_API_KEY", source)
        self.assertNotIn("run194_note_persistent_cloud.py", source)
        self.assertNotIn("note_draft_automation.py", source)
        self.assertNotIn("NOTE_STORAGE_STATE_B64", source)
        self.assertNotIn("xvfb-run", source)
        self.assertNotIn("playwright", source.lower())
        self.assertNotIn("google-chrome", source.lower())
        self.assertIn("run: python note_ready_sync.py", source)

    def test_reconciliation_revokes_unmatched_waiting_rows_but_preserves_posted_state(self) -> None:
        # Import the live sync module only inside the integration-capable test. The repository-wide
        # static guard intentionally runs without third-party dependencies such as requests.
        import note_ready_sync as sync

        waiting = destination("waiting-page", "old-waiting", "投稿待ち")
        posted = destination("posted-page", "old-posted", "投稿済み")
        response = MagicMock(status_code=200, text="")

        old = (
            sync.NOTION_API_KEY,
            sync.SOURCE_DATABASE_ID,
            sync.SOURCE_DATA_SOURCE_ID,
            sync.DEST_DATABASE_ID,
            sync.DEST_DATA_SOURCE_ID,
        )
        sync.NOTION_API_KEY = "test-token"
        sync.SOURCE_DATABASE_ID = "source-db"
        sync.SOURCE_DATA_SOURCE_ID = ""
        sync.DEST_DATABASE_ID = "dest-db"
        sync.DEST_DATA_SOURCE_ID = ""
        try:
            with (
                patch.object(sync, "_validate_destination_schema"),
                patch.object(sync, "_query_db", side_effect=[[], [waiting, posted]]),
                patch.object(sync, "_request", return_value=response) as request,
                patch.object(sync.time, "sleep"),
            ):
                result = sync.sync_note_ready_db()
        finally:
            (
                sync.NOTION_API_KEY,
                sync.SOURCE_DATABASE_ID,
                sync.SOURCE_DATA_SOURCE_ID,
                sync.DEST_DATABASE_ID,
                sync.DEST_DATA_SOURCE_ID,
            ) = old

        self.assertEqual(result["source_ready"], 0)
        self.assertEqual(result["revoked"], 2)
        patch_calls = [call for call in request.call_args_list if call.args and call.args[0] == "PATCH"]
        self.assertEqual(len(patch_calls), 2)

        by_url = {call.args[1]: call.kwargs["json"]["properties"] for call in patch_calls}
        waiting_props = by_url["https://api.notion.com/v1/pages/waiting-page"]
        posted_props = by_url["https://api.notion.com/v1/pages/posted-page"]

        self.assertEqual(waiting_props["品質状態"]["select"]["name"], "Ready取消")
        self.assertEqual(waiting_props["投稿状態"]["select"]["name"], "取下げ")
        self.assertEqual(posted_props["品質状態"]["select"]["name"], "Ready取消")
        self.assertNotIn("投稿状態", posted_props)


if __name__ == "__main__":
    unittest.main(verbosity=2)
