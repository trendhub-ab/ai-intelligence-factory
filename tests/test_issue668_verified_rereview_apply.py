from __future__ import annotations

import unittest
from copy import deepcopy

import member_verified_rereview_apply as apply


def row(sync_id: str, reviewed: str = "2026-01-01", *, score: int = 70, status: str = "WATCH"):
    return {
        "sync_id": sync_id,
        "last_reviewed": reviewed,
        "score": score,
        "status": status,
    }


class Issue668VerifiedApplyTests(unittest.TestCase):
    def test_only_evidence_pass_candidates_enter_allowlist(self):
        selected = [row("pass"), row("missing"), row("failed")]

        def verifier(state):
            return {
                "pass": {"retrieved": True, "gate_pass": True, "result": "PASS"},
                "missing": {"retrieved": False, "gate_pass": False, "result": "UNAVAILABLE"},
                "failed": {"retrieved": True, "gate_pass": False, "result": "EVIDENCE_FAIL"},
            }[state["sync_id"]]

        result = apply.build_verified_allowlist(selected, verifier, limit=2)
        self.assertEqual(result["allowlist"], ["pass"])
        self.assertEqual(result["verified"], 1)
        self.assertEqual(result["unavailable"], 1)
        self.assertEqual(result["evidence_fail"], 1)

    def test_allowlist_is_deduped_and_hard_capped(self):
        selected = [row("a"), row("a"), row("b"), row("c")]

        result = apply.build_verified_allowlist(
            selected,
            lambda _: {"retrieved": True, "gate_pass": True, "result": "PASS"},
            limit=2,
        )

        self.assertEqual(result["allowlist"], ["a", "b"])

    def test_unavailable_candidate_is_never_sent_to_product_runner(self):
        selected = [row("good"), row("bad")]
        seen = []

        def verifier(state):
            if state["sync_id"] == "good":
                return {"retrieved": True, "gate_pass": True, "result": "PASS"}
            return {"retrieved": False, "gate_pass": False, "result": "UNAVAILABLE"}

        before = deepcopy(selected)

        def runner(allowlist, max_reviews, request_budget):
            seen.extend(allowlist)
            return {"skipped": False}

        result = apply.execute_verified_apply(
            selected=selected,
            verifier=verifier,
            before_states=before,
            reread_states=lambda: deepcopy(before),
            product_runner=runner,
            max_reviews=2,
            request_budget=3,
        )

        self.assertEqual(seen, ["good"])
        self.assertEqual(result["allowlist_count"], 1)

    def test_out_of_allowlist_mutation_fails_closed(self):
        selected = [row("good")]
        before = [row("good"), row("other")]
        after = [row("good", "2026-10-02"), row("other", "2026-10-02")]

        with self.assertRaisesRegex(RuntimeError, "outside verified allowlist"):
            apply.execute_verified_apply(
                selected=selected,
                verifier=lambda _: {"retrieved": True, "gate_pass": True, "result": "PASS"},
                before_states=before,
                reread_states=lambda: after,
                product_runner=lambda *_: {"skipped": False},
                max_reviews=1,
                request_budget=1,
            )

    def test_unverified_selected_record_must_remain_unchanged(self):
        selected = [row("good"), row("bad")]
        before = deepcopy(selected)
        after = [row("good", "2026-10-02"), row("bad", "2026-10-02")]

        def verifier(state):
            return (
                {"retrieved": True, "gate_pass": True, "result": "PASS"}
                if state["sync_id"] == "good"
                else {"retrieved": False, "gate_pass": False, "result": "UNAVAILABLE"}
            )

        with self.assertRaisesRegex(RuntimeError, "unverified candidate changed"):
            apply.execute_verified_apply(
                selected=selected,
                verifier=verifier,
                before_states=before,
                reread_states=lambda: after,
                product_runner=lambda *_: {"skipped": False},
                max_reviews=1,
                request_budget=1,
            )

    def test_model_budget_above_hard_cap_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "request budget"):
            apply.validate_apply_budget(max_reviews=2, request_budget=4)

    def test_review_count_above_hard_cap_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "max reviews"):
            apply.validate_apply_budget(max_reviews=3, request_budget=3)

    def test_zero_verified_candidates_skip_product_runner(self):
        called = []
        before = [row("bad")]

        result = apply.execute_verified_apply(
            selected=before,
            verifier=lambda _: {"retrieved": False, "gate_pass": False, "result": "UNAVAILABLE"},
            before_states=before,
            reread_states=lambda: deepcopy(before),
            product_runner=lambda *_: called.append(True),
            max_reviews=2,
            request_budget=3,
        )

        self.assertEqual(called, [])
        self.assertTrue(result["skipped"])

    def test_result_is_aggregate_only(self):
        selected = [row("private-sync-id")]
        before = deepcopy(selected)

        result = apply.execute_verified_apply(
            selected=selected,
            verifier=lambda _: {"retrieved": True, "gate_pass": True, "result": "PASS"},
            before_states=before,
            reread_states=lambda: deepcopy(before),
            product_runner=lambda *_: {"skipped": False},
            max_reviews=1,
            request_budget=1,
        )

        rendered = str(result)
        self.assertNotIn("private-sync-id", rendered)


if __name__ == "__main__":
    unittest.main()
