from __future__ import annotations

import types
import unittest
from unittest import mock

import note_ready_sync as note_sync
import run285_operational_accounting as run285


class _Logger:
    def __init__(self):
        self.rows = []

    def info(self, *args):
        self.rows.append(args)


def _rt(value: str) -> dict:
    return {"rich_text": [{"plain_text": value, "text": {"content": value}}]}


def _title(value: str) -> dict:
    return {"title": [{"plain_text": value, "text": {"content": value}}]}


def _ready_page(page_id: str, *, source: str = "GitHub", title: str = "article") -> dict:
    return {
        "id": page_id,
        "url": f"https://www.notion.so/{page_id}",
        "properties": {
            "記事状態": {"select": {"name": "Ready"}},
            "記事名": _title(title) if title else {"title": []},
            "情報源": {"select": {"name": source}},
            "元情報URL": {"url": "https://example.com/source"},
            "一次情報URL": _rt("https://example.com/primary"),
            "アイキャッチ": {"files": []},
        },
    }


class Run285AccountingTests(unittest.TestCase):
    def test_note_ready_classification_is_mutually_exclusive(self):
        allowed = {"GitHub", "HackerNews", "ArXiv", "OfficialVendor"}
        self.assertEqual(
            "unsupported_source",
            run285.classify_note_ready_source_row("ProductHunt", None, allowed),
        )
        self.assertEqual(
            "invalid_source_state",
            run285.classify_note_ready_source_row("GitHub", None, allowed),
        )
        self.assertEqual(
            "state_available",
            run285.classify_note_ready_source_row("HackerNews", {"sync_id": "abc"}, allowed),
        )

    def test_note_ready_sync_accounts_for_every_ready_source_row(self):
        source_pages = [
            _ready_page("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", source="GitHub", title="stale"),
            _ready_page("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", source="GitHub", title=""),
            _ready_page("cccccccccccccccccccccccccccccccc", source="ProductHunt", title="retired"),
        ]
        with mock.patch.object(note_sync, "NOTION_API_KEY", "token"), \
             mock.patch.object(note_sync, "SOURCE_DATA_SOURCE_ID", "source"), \
             mock.patch.object(note_sync, "DEST_DATA_SOURCE_ID", "dest"), \
             mock.patch.object(note_sync, "_validate_destination_schema"), \
             mock.patch.object(note_sync, "_query_db", side_effect=[source_pages, []]), \
             mock.patch.object(note_sync, "_source_current_ready_manuscript", return_value=""):
            result = note_sync.sync_note_ready_db()

        self.assertEqual(result["source_ready_status_rows"], 3)
        self.assertEqual(result["source_ready"], 0)
        self.assertEqual(result["stale_publication_contract"], 1)
        self.assertEqual(result["unsupported_source"], 1)
        self.assertEqual(result["invalid_source_state"], 1)
        classified = (
            result["source_ready"]
            + result["stale_publication_contract"]
            + result["incomplete_publication_assets"]
            + result["unsupported_source"]
            + result["invalid_source_state"]
        )
        self.assertEqual(classified, result["source_ready_status_rows"])

    def test_persisted_status_counter_does_not_infer_generation(self):
        counts = {}
        self.assertEqual("Pending Retry", run285.increment_status_count(counts, "Pending Retry"))
        self.assertEqual("UNKNOWN", run285.increment_status_count(counts, None))
        self.assertEqual({"Pending Retry": 1, "UNKNOWN": 1}, counts)

    def test_evidence_audit_wraps_existing_call_exactly_once_and_preserves_identity(self):
        calls = []
        logger = _Logger()
        expected = {
            "source": "HackerNews",
            "context": "source context",
            "context_length": 14,
            "verification_context": "primary evidence",
            "verification_context_length": 16,
            "evidence_documents": [{"url": "https://example.com/official"}],
            "grounding_method": "SOURCE_NATIVE",
            "primary_material_retrieved": True,
            "primary_url": "https://example.com/article",
        }

        def prepare(repo):
            calls.append(repo)
            return expected

        pipeline = types.SimpleNamespace(prepare_source_context=prepare, logger=logger)
        run285.install_recovery_evidence_audit(pipeline)
        repo = {"source": "HackerNews", "primaryUrl": "https://example.com/article"}
        actual = pipeline.prepare_source_context(repo)

        self.assertIs(actual, expected)
        self.assertEqual(calls, [repo])
        self.assertEqual(len(logger.rows), 1)
        self.assertIn("[RUN285 EVIDENCE AUDIT]", logger.rows[0][0])

    def test_evidence_audit_is_idempotent_and_adds_no_call_when_prepare_is_absent(self):
        pipeline = types.SimpleNamespace(logger=_Logger())
        run285.install_recovery_evidence_audit(pipeline)
        self.assertTrue(getattr(pipeline, "_run285_recovery_evidence_audit_installed"))
        run285.install_recovery_evidence_audit(pipeline)
        self.assertFalse(hasattr(pipeline, "prepare_source_context"))

        calls = []
        pipeline2 = types.SimpleNamespace(
            prepare_source_context=lambda repo: calls.append(repo) or {"context": "x"},
            logger=_Logger(),
        )
        run285.install_recovery_evidence_audit(pipeline2)
        wrapped = pipeline2.prepare_source_context
        run285.install_recovery_evidence_audit(pipeline2)
        self.assertIs(wrapped, pipeline2.prepare_source_context)
        pipeline2.prepare_source_context({"source": "GitHub"})
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
