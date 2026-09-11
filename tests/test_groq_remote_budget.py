import unittest
from groq_remote_budget import reserve_state
from ai_provider import ProviderError


class RemoteBudgetTests(unittest.TestCase):
    def test_replay_blocked_forever_and_state_not_mutated(self):
        original = {"version": 1, "attempts": []}
        state = reserve_state(original, "first", 1000, 100000)
        self.assertEqual(original["attempts"], [])
        for now in (100100, 300000):
            with self.assertRaisesRegex(ProviderError, "already_reserved"):
                reserve_state(state, "first", 1000, now)

    def test_caps_and_recovery(self):
        state = {"version": 1, "attempts": []}
        for index in range(3):
            state = reserve_state(state, str(index), 8000, 100000 + index * 100)
        with self.assertRaisesRegex(ProviderError, "persistent_validation_budget"):
            reserve_state(state, "fourth", 1000, 100500)
        self.assertEqual(len(reserve_state(state, "fourth", 1000, 200000)["attempts"]), 4)

    def test_pacing_and_corrupt_state(self):
        state = reserve_state({"version": 1, "attempts": []}, "first", 1000, 100000)
        with self.assertRaisesRegex(ProviderError, "pacing"):
            reserve_state(state, "second", 1000, 100010)
        with self.assertRaisesRegex(ProviderError, "invalid_remote_ledger"):
            reserve_state({"version": 1, "attempts": [{}]}, "second", 1000, 100100)
