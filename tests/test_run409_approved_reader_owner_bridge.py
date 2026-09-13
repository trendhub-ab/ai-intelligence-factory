from __future__ import annotations

import types
import unittest

import run208_reader_value_repair as canonical_reader
import run409_approved_reader_owner_bridge as run409


class Run409ApprovedReaderOwnerBridgeTests(unittest.TestCase):
    def _pipeline(self, base_reason=run409.MASKED_REASON):
        p = types.SimpleNamespace()
        p.EVIDENCE_SUFFICIENT = "SUFFICIENT"
        p.GATE_SEVERITY_HARD = "HARD"
        setattr(p, canonical_reader._READER_REPAIR_SPENT_ATTR, False)
        p.calls = []

        def base(rows, evidence, origin="new"):
            p.calls.append((list(rows or []), evidence, origin))
            return False, base_reason

        p.should_attempt_dynamic_retry = base
        return p

    def _safe_evidence(self):
        return {"state": "SUFFICIENT", "decision_scope_safe": True}

    def _real_run11_reader_rows(self):
        return [
            {"severity": "REVIEW", "message": "reader_value_review:dense_report_cluster (Reader Enjoyment/Narrative Pull/Information Budget/Reader Temperature Rhythm)"},
            {"severity": "REVIEW", "message": "reader_value_review:multi_axis_reader_weakness (accessibility/reader_enjoyment/narrative_pull/jargon_translation/non_engineer_core_clarity/information_budget/reader_temperature_rhythm)"},
            {"severity": "REVIEW", "message": "reader_value_review:non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity)"},
            {"severity": "REVIEW", "message": "reader_value_review:final_surface_summary_jargon_cluster (何が出た？/結論は？)"},
        ]

    def test_real_run11_bundle_claims_existing_reader_repair_owner_once(self):
        p = self._pipeline()
        run409.install(p)
        allowed, reason = p.should_attempt_dynamic_retry(
            self._real_run11_reader_rows(), self._safe_evidence(), "approved_article_apply"
        )
        self.assertTrue(allowed)
        self.assertEqual(run409.READER_REPAIR_REASON, reason)
        self.assertTrue(getattr(p, canonical_reader._READER_REPAIR_SPENT_ATTR))

        allowed2, reason2 = p.should_attempt_dynamic_retry(
            self._real_run11_reader_rows(), self._safe_evidence(), "approved_article_apply"
        )
        self.assertFalse(allowed2)
        self.assertEqual("run360_reader_repair_already_spent", reason2)

    def test_normal_origins_keep_base_retry_exhaustion(self):
        p = self._pipeline()
        run409.install(p)
        for origin in ("new", "article_revalidation", "pending_retry"):
            allowed, reason = p.should_attempt_dynamic_retry(
                self._real_run11_reader_rows(), self._safe_evidence(), origin
            )
            self.assertFalse(allowed)
            self.assertEqual(run409.MASKED_REASON, reason)

    def test_non_reader_hard_or_unsafe_never_claims_reader_owner(self):
        cases = [
            ([{"severity": "REVIEW", "message": "FACT_UNSUPPORTED_CLAIM"}], self._safe_evidence()),
            ([{"severity": "HARD", "message": "reader_value_review:multi_axis_reader_weakness"}], self._safe_evidence()),
            (self._real_run11_reader_rows(), {"state": "INSUFFICIENT", "decision_scope_safe": True}),
            (self._real_run11_reader_rows(), {"state": "SUFFICIENT", "decision_scope_safe": False}),
            (self._real_run11_reader_rows(), None),
        ]
        for rows, evidence in cases:
            p = self._pipeline()
            run409.install(p)
            allowed, reason = p.should_attempt_dynamic_retry(rows, evidence, "approved_article_apply")
            self.assertFalse(allowed)
            self.assertEqual(run409.MASKED_REASON, reason)
            self.assertFalse(getattr(p, canonical_reader._READER_REPAIR_SPENT_ATTR))

    def test_other_base_reason_is_not_overridden(self):
        p = self._pipeline(base_reason="reader_value_review_no_retry")
        run409.install(p)
        allowed, reason = p.should_attempt_dynamic_retry(
            self._real_run11_reader_rows(), self._safe_evidence(), "approved_article_apply"
        )
        self.assertFalse(allowed)
        self.assertEqual("reader_value_review_no_retry", reason)

    def test_install_is_idempotent_and_missing_policy_fails_closed(self):
        p = self._pipeline()
        run409.install(p)
        first = p.should_attempt_dynamic_retry
        run409.install(p)
        self.assertIs(first, p.should_attempt_dynamic_retry)

        with self.assertRaises(RuntimeError):
            run409.install(types.SimpleNamespace())


if __name__ == "__main__":
    unittest.main()
