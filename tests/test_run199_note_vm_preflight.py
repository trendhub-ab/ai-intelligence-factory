from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import note_draft_automation as base
import run194_note_current_contract as run194
import run199_note_vm_preflight as run199


class Run199NoteVmPreflightTests(unittest.TestCase):
    def test_automatic_empty_safe_queue_does_not_start_vm(self) -> None:
        with patch.object(
            run194,
            "_prepare_article",
            side_effect=base.NoteDraftError("No eligible Ready / 投稿待ち article is available"),
        ):
            result = run199.preflight("")
        self.assertEqual("no_eligible_ready", result["status"])
        self.assertFalse(result["should_start_vm"])
        self.assertEqual("", result["selected_sync_id"])
        self.assertTrue(result["zero_gemini_calls"])

    def test_eligible_candidate_starts_vm_and_pins_sync_id(self) -> None:
        sid = "a" * 32
        prepared = {
            "sync_id": sid,
            "publication_contract": "contract",
            "publication_policy_sha256": "policy",
            "manuscript_sha256": "body",
        }
        with patch.object(run194, "_prepare_article", return_value=prepared):
            result = run199.preflight("")
        self.assertEqual("eligible_ready", result["status"])
        self.assertTrue(result["should_start_vm"])
        self.assertEqual(sid, result["selected_sync_id"])

    def test_explicit_missing_sync_id_remains_fail_closed(self) -> None:
        sid = "b" * 32
        with patch.object(
            run194,
            "_prepare_article",
            side_effect=base.NoteDraftError("Requested sync_id is not exactly one Ready / 投稿待ち article"),
        ):
            with self.assertRaises(base.NoteDraftError):
                run199.preflight(sid)

    def test_unrelated_notion_failure_remains_fail_closed(self) -> None:
        with patch.object(
            run194,
            "_prepare_article",
            side_effect=base.NoteDraftError("Notion API key is not configured"),
        ):
            with self.assertRaises(base.NoteDraftError):
                run199.preflight("")

    def test_invalid_selected_sync_id_is_fail_closed(self) -> None:
        with patch.object(run194, "_prepare_article", return_value={"sync_id": "short"}):
            with self.assertRaises(base.NoteDraftError):
                run199.preflight("")

    def test_preflight_has_no_browser_model_or_vm_start_imports(self) -> None:
        source = inspect.getsource(run199).lower()
        forbidden = [
            "import play" + "wright",
            "from play" + "wright",
            "genai.client(",
            "_generate_via_chat(",
            "gcloud " + "compute",
        ]
        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
