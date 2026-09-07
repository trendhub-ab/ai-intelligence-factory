from __future__ import annotations

import types
import unittest

import run285_operational_accounting as run285


class _Logger:
    def __init__(self):
        self.rows = []

    def info(self, *args):
        self.rows.append(args)


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
