import unittest

from ai_provider import ProviderError
from groq_rate_policy import COMPOUND_MINI, GPT_OSS_120B
from groq_remote_budget import reconcile_state, reserve_state


class GroqBudgetReconciliationTests(unittest.TestCase):
    def base_state(self):
        return {"version": 1, "attempts": []}

    def test_reconcile_increases_existing_reservation_without_new_request(self):
        state = reserve_state(
            self.base_state(),
            "article-v4",
            12000,
            1000.0,
            COMPOUND_MINI.name,
        )
        updated = reconcile_state(
            state,
            "article-v4",
            15000,
            1001.0,
            COMPOUND_MINI.name,
        )
        self.assertEqual(len(updated["attempts"]), 1)
        row = updated["attempts"][0]
        self.assertEqual(row["tokens"], 15000)
        self.assertEqual(row["actual_tokens"], 15000)
        self.assertTrue(row["reconciled"])

    def test_reconcile_never_reduces_reserved_usage(self):
        state = reserve_state(
            self.base_state(),
            "article-v4",
            12000,
            1000.0,
            COMPOUND_MINI.name,
        )
        updated = reconcile_state(
            state,
            "article-v4",
            9000,
            1001.0,
            COMPOUND_MINI.name,
        )
        row = updated["attempts"][0]
        self.assertEqual(row["tokens"], 12000)
        self.assertEqual(row["actual_tokens"], 9000)
        self.assertTrue(row["reconciled"])

    def test_reconcile_unknown_experiment_fails_closed(self):
        state = reserve_state(
            self.base_state(),
            "article-v4",
            12000,
            1000.0,
            COMPOUND_MINI.name,
        )
        with self.assertRaisesRegex(ProviderError, "reconciliation_experiment_not_unique"):
            reconcile_state(state, "missing", 15000, 1001.0, COMPOUND_MINI.name)

    def test_reconcile_profile_mismatch_fails_closed(self):
        state = reserve_state(
            self.base_state(),
            "article-v4",
            12000,
            1000.0,
            COMPOUND_MINI.name,
        )
        with self.assertRaisesRegex(ProviderError, "reconciliation_profile_mismatch"):
            reconcile_state(state, "article-v4", 15000, 1001.0, GPT_OSS_120B.name)


if __name__ == "__main__":
    unittest.main()
