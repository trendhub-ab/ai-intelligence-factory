from __future__ import annotations

import types
import unittest

import run406_approved_second_reader_repair as run406


class Run406ApprovedSecondReaderRepairTests(unittest.TestCase):
    def _pipeline(self, base_reason="run360_reader_repair_already_spent"):
        p = types.SimpleNamespace()
        p.EVIDENCE_SUFFICIENT = "SUFFICIENT"
        p.GATE_SEVERITY_HARD = "HARD"
        p.calls = []

        def base(rows, evidence, origin="new"):
            p.calls.append((list(rows or []), evidence, origin))
            return False, base_reason

        p.should_attempt_dynamic_retry = base
        return p

    def _safe_evidence(self):
        return {"state": "SUFFICIENT", "decision_scope_safe": True}

    def _multi_axis_rows(self):
        return [{
            "severity": "REVIEW",
            "message": "reader_value_review:multi_axis_reader_weakness (accessibility/reader_enjoyment/information_budget/reader_temperature_rhythm)",
        }]

    def test_approved_lane_gets_exactly_one_extra_reader_only_repair(self):
        p = self._pipeline()
        run406.install(p)
        allowed, reason = p.should_attempt_dynamic_retry(
            self._multi_axis_rows(), self._safe_evidence(), "approved_article_apply"
        )
        self.assertTrue(allowed)
        self.assertEqual(run406.SECOND_REPAIR_REASON, reason)

        allowed2, reason2 = p.should_attempt_dynamic_retry(
            self._multi_axis_rows(), self._safe_evidence(), "approved_article_apply"
        )
        self.assertFalse(allowed2)
        self.assertEqual("run406_second_reader_repair_already_spent", reason2)

    def test_normal_origins_keep_run360_ceiling(self):
        p = self._pipeline()
        run406.install(p)
        for origin in ("new", "article_revalidation", "pending_retry"):
            allowed, reason = p.should_attempt_dynamic_retry(
                self._multi_axis_rows(), self._safe_evidence(), origin
            )
            self.assertFalse(allowed)
            self.assertEqual("run360_reader_repair_already_spent", reason)

    def test_non_reader_or_hard_rows_never_get_extra_repair(self):
        p = self._pipeline()
        run406.install(p)
        cases = [
            [{"severity": "REVIEW", "message": "score_narrative_mismatch"}],
            [{"severity": "HARD", "message": "reader_value_review:multi_axis_reader_weakness"}],
            [{"severity": "REVIEW", "message": "reader_value_review:dense_report_cluster"}],
        ]
        for rows in cases:
            allowed, reason = p.should_attempt_dynamic_retry(rows, self._safe_evidence(), "approved_article_apply")
            self.assertFalse(allowed)
            self.assertEqual("run360_reader_repair_already_spent", reason)

    def test_unsafe_evidence_never_gets_extra_repair(self):
        p = self._pipeline()
        run406.install(p)
        for evidence in (
            {"state": "INSUFFICIENT", "decision_scope_safe": True},
            {"state": "SUFFICIENT", "decision_scope_safe": False},
            None,
        ):
            allowed, reason = p.should_attempt_dynamic_retry(
                self._multi_axis_rows(), evidence, "approved_article_apply"
            )
            self.assertFalse(allowed)
            self.assertEqual("run360_reader_repair_already_spent", reason)

    def test_other_base_reason_is_not_overridden(self):
        p = self._pipeline(base_reason="some_other_reason")
        run406.install(p)
        allowed, reason = p.should_attempt_dynamic_retry(
            self._multi_axis_rows(), self._safe_evidence(), "approved_article_apply"
        )
        self.assertFalse(allowed)
        self.assertEqual("some_other_reason", reason)


if __name__ == "__main__":
    unittest.main()
