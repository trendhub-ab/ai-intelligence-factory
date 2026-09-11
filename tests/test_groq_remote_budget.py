import unittest
from groq_remote_budget import reserve_state
from groq_rate_policy import SAFE_RPD, SAFE_RPM, SAFE_TPD, SAFE_TPM
from ai_provider import ProviderError


class RemoteBudgetTests(unittest.TestCase):
    def test_replay_blocked_forever_and_state_not_mutated(self):
        original = {"version": 1, "attempts": []}
        state = reserve_state(original, "first", 1000, 100000)
        self.assertEqual(original["attempts"], [])
        for now in (100100, 300000):
            with self.assertRaisesRegex(ProviderError, "already_reserved"):
                reserve_state(state, "first", 1000, now)

    def test_daily_token_cap_and_recovery(self):
        now = 200000
        state = {"version": 1, "attempts": []}
        # Stay below minute cap by spacing attempts, then consume the daily token envelope.
        per_call = 6000
        calls = SAFE_TPD // per_call
        for index in range(calls):
            state = reserve_state(state, f"d{index}", per_call, now + index * 61)
        used = calls * per_call
        remaining = SAFE_TPD - used
        with self.assertRaisesRegex(ProviderError, "daily_budget"):
            reserve_state(state, "daily-over", remaining + 1, now + calls * 61)
        recovered_now = now + 86400 + calls * 61
        self.assertGreater(len(reserve_state(state, "after-day", 1000, recovered_now)["attempts"]), calls)

    def test_minute_token_cap(self):
        state = reserve_state({"version": 1, "attempts": []}, "first", 4000, 100000)
        with self.assertRaisesRegex(ProviderError, "minute_budget"):
            reserve_state(state, "second", SAFE_TPM - 3999, 100010)
        state = reserve_state(state, "second-ok", 3000, 100010)
        self.assertEqual(len(state["attempts"]), 2)

    def test_request_caps_are_defined_below_provider_limits(self):
        self.assertLess(SAFE_RPM, 30)
        self.assertLess(SAFE_RPD, 1000)
        self.assertLess(SAFE_TPM, 8000)
        self.assertLess(SAFE_TPD, 200000)

    def test_corrupt_state_rejected(self):
        with self.assertRaisesRegex(ProviderError, "invalid_remote_ledger"):
            reserve_state({"version": 1, "attempts": [{}]}, "second", 1000, 100100)
