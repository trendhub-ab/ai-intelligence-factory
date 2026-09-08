from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

import publication_contract as contract
import run289_genrec_queue_reactivation as run289

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "current-ready-metadata-rebase.yml"
MODULE = ROOT / "run289_genrec_queue_reactivation.py"


def rt(value: str) -> dict:
    return {"rich_text": [{"plain_text": value, "text": {"content": value}}]}


def title(value: str) -> dict:
    return {"title": [{"plain_text": value, "text": {"content": value}}]}


def destination(*, posting="取下げ", quality="Ready", public_url="", posted_date="") -> dict:
    return {
        "id": "dest-page",
        "properties": {
            "同期ID": rt(run289.TARGET_SYNC_ID),
            "記事タイトル": title("Netflixが推薦の舞台裏をLLMネイティブへ舵を切った理由。"),
            "投稿状態": {"select": {"name": posting}},
            "品質状態": {"select": {"name": quality}},
            "note公開URL": {"url": public_url or None},
            "投稿日": {"date": {"start": posted_date}} if posted_date else {"date": None},
            "投稿予定日": {"date": None},
        },
    }


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return copy.deepcopy(self._payload)


class Run289ExecutionTests(unittest.TestCase):
    def _source_fixture(self):
        state = {
            "sync_id": run289.TARGET_SYNC_ID,
            "title": "Netflixが推薦の舞台裏をLLMネイティブへ舵を切った理由。",
            "source": run289.TARGET_SOURCE,
            "primary_url": "https://netflixtechblog.com/genrec-towards-llm-native-recommendation-at-netflix-f20be6f643e3?gi=x",
            "eyecatch_url": "https://example.invalid/genrec.png",
        }
        manuscript = (
            "# Netflixが推薦の舞台裏をLLMネイティブへ舵を切った理由。\n\n"
            "### 元情報\n"
            "- **主一次情報**: [GenRec](https://netflixtechblog.com/genrec-towards-llm-native-recommendation-at-netflix-f20be6f643e3?gi=x)\n"
            "- **発見経路**: Hacker News\n"
            f"{run289.EXPECTED_PROVENANCE_LINE}\n\n"
            + "本文" * 150
        )
        return state, manuscript

    def test_exact_auto_revoked_row_is_reactivated_and_nothing_else_is_written(self):
        state, manuscript = self._source_fixture()
        before = destination()
        after = destination(posting=run289.RESTORED_POSTING_STATUS)
        calls = []

        def request(method, url, json=None):
            calls.append((method, url, json))
            if method == "PATCH":
                return FakeResponse(200)
            if method == "GET" and url.endswith("dest-page"):
                return FakeResponse(200, after)
            raise AssertionError((method, url))

        with patch.object(run289.sync, "NOTION_API_KEY", "token"), \
             patch.object(run289.sync, "SOURCE_DATA_SOURCE_ID", "source"), \
             patch.object(run289.sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(run289.contract, "policy_sha256", return_value=run289.TARGET_POLICY_SHA256), \
             patch.object(run289, "_source_page", return_value=({}, state, manuscript)), \
             patch.object(run289, "_exact_destination_page", return_value=before), \
             patch.object(run289.sync, "_request", side_effect=request):
            result = run289.reactivate_genrec_queue()

        self.assertEqual(result["status"], "reactivated")
        self.assertEqual(result["posting_status_before"], "取下げ")
        self.assertEqual(result["posting_status_after"], "投稿待ち")
        self.assertEqual(result["gemini_calls"], 0)
        self.assertEqual(result["browser_calls"], 0)
        self.assertFalse(result["private_draft"])
        self.assertFalse(result["public_release"])
        patch_calls = [item for item in calls if item[0] == "PATCH"]
        self.assertEqual(len(patch_calls), 1)
        self.assertEqual(
            patch_calls[0][2],
            {"properties": {"投稿状態": {"select": {"name": "投稿待ち"}}}},
        )

    def test_already_waiting_is_idempotent_and_performs_no_write(self):
        state, manuscript = self._source_fixture()
        with patch.object(run289.sync, "NOTION_API_KEY", "token"), \
             patch.object(run289.sync, "SOURCE_DATA_SOURCE_ID", "source"), \
             patch.object(run289.sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(run289.contract, "policy_sha256", return_value=run289.TARGET_POLICY_SHA256), \
             patch.object(run289, "_source_page", return_value=({}, state, manuscript)), \
             patch.object(run289, "_exact_destination_page", return_value=destination(posting="投稿待ち")), \
             patch.object(run289.sync, "_request") as request:
            result = run289.reactivate_genrec_queue()
        self.assertEqual(result["status"], "already_reactivated")
        request.assert_not_called()

    def test_unexpected_human_or_publication_state_fails_closed(self):
        state, manuscript = self._source_fixture()
        cases = (
            destination(posting="保留"),
            destination(quality="Ready取消"),
            destination(public_url="https://note.com/example/n/abc"),
            destination(posted_date="2026-09-08"),
        )
        for row in cases:
            with self.subTest(row=row["properties"]):
                with patch.object(run289.sync, "NOTION_API_KEY", "token"), \
                     patch.object(run289.sync, "SOURCE_DATA_SOURCE_ID", "source"), \
                     patch.object(run289.sync, "DEST_DATA_SOURCE_ID", "dest"), \
                     patch.object(run289.contract, "policy_sha256", return_value=run289.TARGET_POLICY_SHA256), \
                     patch.object(run289, "_source_page", return_value=({}, state, manuscript)), \
                     patch.object(run289, "_exact_destination_page", return_value=row), \
                     patch.object(run289.sync, "_request") as request:
                    with self.assertRaises(RuntimeError):
                        run289.reactivate_genrec_queue()
                    request.assert_not_called()

    def test_future_policy_change_disables_one_shot_migration(self):
        with patch.object(run289.sync, "NOTION_API_KEY", "token"), \
             patch.object(run289.sync, "SOURCE_DATA_SOURCE_ID", "source"), \
             patch.object(run289.sync, "DEST_DATA_SOURCE_ID", "dest"), \
             patch.object(run289.contract, "policy_sha256", return_value="0" * 64):
            with self.assertRaises(RuntimeError):
                run289.reactivate_genrec_queue()


class Run289SourceAndDestinationTests(unittest.TestCase):
    def test_source_requires_exact_current_genrec_and_run287_line(self):
        page = {"id": run289.TARGET_SYNC_ID, "properties": {}}
        state = {
            "sync_id": run289.TARGET_SYNC_ID,
            "title": "Netflixが推薦の舞台裏をLLMネイティブへ舵を切った理由。",
            "source": run289.TARGET_SOURCE,
            "primary_url": f"https://{run289.TARGET_URL_SLUG}?gi=x",
            "eyecatch_url": "https://example.invalid/a.png",
        }
        manuscript = run289.EXPECTED_PROVENANCE_LINE + "\n" + "本文" * 150
        with patch.object(run289.sync, "_request", return_value=FakeResponse(200, page)), \
             patch.object(run289.sync, "_source_state", return_value=state), \
             patch.object(run289.sync, "_source_current_ready_manuscript", return_value=manuscript):
            _, actual_state, actual_body = run289._source_page()
        self.assertEqual(actual_state, state)
        self.assertEqual(actual_body, manuscript)

        bad = manuscript.replace(run289.EXPECTED_PROVENANCE_LINE, run289.FORBIDDEN_OLD_PROVENANCE_LINE)
        with patch.object(run289.sync, "_request", return_value=FakeResponse(200, page)), \
             patch.object(run289.sync, "_source_state", return_value=state), \
             patch.object(run289.sync, "_source_current_ready_manuscript", return_value=bad):
            with self.assertRaises(RuntimeError):
                run289._source_page()

    def test_destination_query_is_exactly_pinned_to_sync_id(self):
        row = destination()
        with patch.object(run289.sync, "_query_db", return_value=[row]) as query:
            self.assertEqual(run289._exact_destination_page(), row)
        payload = query.call_args.kwargs["payload"]
        self.assertEqual(payload["filter"]["property"], "同期ID")
        self.assertEqual(payload["filter"]["rich_text"]["equals"], run289.TARGET_SYNC_ID)


class Run289RepositoryContractTests(unittest.TestCase):
    def test_module_is_zero_model_zero_browser_and_policy_pinned(self):
        text = MODULE.read_text(encoding="utf-8")
        self.assertIn(run289.TARGET_SYNC_ID, text)
        self.assertIn(run289.TARGET_POLICY_SHA256, text)
        self.assertIn(run289.TARGET_URL_SLUG, text)
        for forbidden in (
            "google.genai", "GEMINI_API_KEY", "generate_content", "generateContent",
            "playwright", "NOTE_STORAGE_STATE_B64", "note.com/new",
        ):
            self.assertNotIn(forbidden, text)

    def test_existing_rebase_workflow_runs_reactivation_and_pinned_zero_vm_preflight(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python -m unittest tests.test_run289_genrec_queue_reactivation -v", text)
        self.assertIn("python run289_genrec_queue_reactivation.py", text)
        self.assertIn(f"NOTE_TARGET_SYNC_ID: '{run289.TARGET_SYNC_ID}'", text)
        self.assertIn("python run199_note_vm_preflight.py", text)
        self.assertIn("eligible_ready", text)
        self.assertIn("should_start_vm", text)
        self.assertNotIn("GEMINI_API_KEY", text)
        self.assertNotIn("note-create-draft.yml", text)
        self.assertNotIn("playwright", text.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
