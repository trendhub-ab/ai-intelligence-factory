from __future__ import annotations

import json
import unittest
from copy import deepcopy
from datetime import date

import member_verified_rereview_dryrun as rr


def row(
    sync_id: str,
    reviewed: str,
    *,
    source: str = "GitHub",
    status: str = "WATCH",
    score: int = 60,
    primary_url: str = "https://github.com/acme/example",
):
    return {
        "sync_id": sync_id,
        "name": f"private-{sync_id}",
        "last_reviewed": reviewed,
        "sources": [source] if source else [],
        "status": status,
        "score": score,
        "confidence": "高",
        "readiness": "高",
        "classification": "実務判断",
        "primary_url": primary_url,
        "evidence": primary_url,
    }


class Issue668ReadOnlyRereviewTests(unittest.TestCase):
    def test_only_older_than_30_days_enters_queue(self):
        states = [
            row("old", "2026-08-31"),
            row("edge", "2026-09-01"),
            row("fresh", "2026-09-20"),
        ]
        selected, stale = rr.select_diverse_stale_queue(
            states, as_of=date(2026, 10, 1), limit=5
        )
        self.assertEqual(stale, 1)
        self.assertEqual([x["sync_id"] for x in selected], ["old"])

    def test_queue_is_bounded(self):
        states = [row(str(i), "2026-01-01") for i in range(20)]
        selected, stale = rr.select_diverse_stale_queue(
            states, as_of=date(2026, 10, 1), limit=5
        )
        self.assertEqual(stale, 20)
        self.assertEqual(len(selected), 5)

    def test_queue_diversifies_acquisition_sources_before_refill(self):
        states = [
            row("g1", "2026-01-01", source="GitHub", score=99),
            row("g2", "2026-01-02", source="GitHub", score=98),
            row("a1", "2026-01-03", source="ArXiv", primary_url="https://arxiv.org/abs/1"),
            row("h1", "2026-01-04", source="HackerNews", primary_url="https://example.com/post"),
            row("o1", "2026-01-05", source="OfficialVendor", primary_url="https://vendor.example/docs"),
        ]
        selected, _ = rr.select_diverse_stale_queue(
            states, as_of=date(2026, 10, 1), limit=4
        )
        self.assertEqual(len({rr.source_bucket(x) for x in selected}), 4)

    def test_duplicate_entity_is_selected_once(self):
        states = [
            row("same", "2026-02-01"),
            row("same", "2026-01-01"),
            row("other", "2026-01-01", source="ArXiv", primary_url="https://arxiv.org/abs/2"),
        ]
        selected, stale = rr.select_diverse_stale_queue(
            states, as_of=date(2026, 10, 1), limit=5
        )
        self.assertEqual(stale, 2)
        self.assertEqual(sum(x["sync_id"] == "same" for x in selected), 1)

    def test_brief_like_adopt_test_value_outranks_long_tail_within_bucket(self):
        states = [
            row("watch-old", "2025-01-01", status="WATCH", score=50),
            row("adopt", "2026-01-01", status="ADOPT", score=95),
        ]
        selected, _ = rr.select_diverse_stale_queue(
            states, as_of=date(2026, 10, 1), limit=1
        )
        self.assertEqual(selected[0]["sync_id"], "adopt")

    def test_missing_source_is_unavailable_without_model_or_write(self):
        counts = rr.run_verification_batch(
            [row("x", "2026-01-01", source="", primary_url="")],
            lambda _: {"retrieved": False, "gate_pass": False, "result": "UNAVAILABLE"},
        )
        self.assertEqual(counts["unavailable"], 1)
        self.assertEqual(counts["model_calls"], 0)
        self.assertEqual(counts["notion_writes"], 0)

    def test_unchanged_verified_source_does_not_consume_model(self):
        counts = rr.run_verification_batch(
            [row("x", "2026-01-01")],
            lambda _: {"retrieved": True, "gate_pass": True, "result": "PASS", "changed": False},
        )
        self.assertEqual(counts["evidence_pass"], 1)
        self.assertEqual(counts["model_calls"], 0)
        self.assertEqual(counts["notion_writes"], 0)

    def test_429_isolated_as_unavailable(self):
        def fail(_):
            raise RuntimeError("HTTP 429")
        counts = rr.run_verification_batch([row("x", "2026-01-01")], fail)
        self.assertEqual(counts["unavailable"], 1)
        self.assertEqual(counts["evidence_pass"], 0)

    def test_503_isolated_as_unavailable(self):
        def fail(_):
            raise RuntimeError("HTTP 503")
        counts = rr.run_verification_batch([row("x", "2026-01-01")], fail)
        self.assertEqual(counts["unavailable"], 1)
        self.assertEqual(counts["model_calls"], 0)

    def test_transient_fetch_exception_does_not_mutate_record(self):
        original = row("x", "2026-01-01", status="TEST", score=77)
        before = deepcopy(original)
        counts = rr.run_verification_batch(
            [original],
            lambda _: (_ for _ in ()).throw(TimeoutError("transient")),
        )
        self.assertEqual(original, before)
        self.assertEqual(counts["unavailable"], 1)
        self.assertEqual(counts["notion_writes"], 0)

    def test_retrieved_but_evidence_failed_is_not_counted_as_verified(self):
        counts = rr.run_verification_batch(
            [row("x", "2026-01-01")],
            lambda _: {"retrieved": True, "gate_pass": False, "result": "EVIDENCE_FAIL"},
        )
        self.assertEqual(counts["retrieved"], 1)
        self.assertEqual(counts["evidence_fail"], 1)
        self.assertEqual(counts["evidence_pass"], 0)

    def test_changed_evidence_still_cannot_trigger_model_in_dry_run(self):
        counts = rr.run_verification_batch(
            [row("x", "2026-01-01")],
            lambda _: {"retrieved": True, "gate_pass": True, "result": "PASS", "changed": True},
        )
        self.assertEqual(counts["model_calls"], 0)
        self.assertEqual(counts["notion_writes"], 0)

    def test_protected_snapshot_detects_review_score_status_changes(self):
        state = row("x", "2026-01-01", status="TEST", score=77)
        before = rr.protected_snapshot(state)
        state["score"] = 78
        self.assertNotEqual(before, rr.protected_snapshot(state))

    def test_aggregate_has_no_paid_record_identity(self):
        private = row("secret-id", "2026-01-01")
        counts = rr.run_verification_batch(
            [private],
            lambda _: {"retrieved": False, "gate_pass": False, "result": "UNAVAILABLE"},
        )
        rendered = json.dumps(counts, sort_keys=True)
        self.assertNotIn("secret-id", rendered)
        self.assertNotIn("private-secret-id", rendered)
        self.assertNotIn("github.com/acme/example", rendered)

    def test_source_bucket_uses_primary_url_when_labels_missing(self):
        state = row("x", "2026-01-01", source="", primary_url="https://arxiv.org/abs/1234.5678")
        self.assertEqual(rr.source_bucket(state), "ArXiv")

    def test_prior_16_pass_is_never_synthesized_into_batch_result(self):
        counts = rr.run_verification_batch(
            [row("x", "2026-01-01")],
            lambda _: {"retrieved": True, "gate_pass": True, "result": "PASS"},
        )
        self.assertNotIn("prior_16_pass", counts)
        self.assertEqual(counts["evidence_pass"], 1)


if __name__ == "__main__":
    unittest.main()
