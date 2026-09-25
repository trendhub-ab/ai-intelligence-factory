"""Two-run contention checks for the remote RPM reservation ledger."""
import unittest

from experiments.ready_yield_shared_rpm import SharedRPM, RPMConflict, RPMUnavailable, GitHubRPMStore
from unittest.mock import patch
from types import SimpleNamespace


class MemoryStore:
    def __init__(self):
        self.data = {"scope": "project", "attempts": [], "campaigns": {}}
        self.version = 0
        self.inject_conflict = False

    def read(self):
        return self.data.copy(), str(self.version)

    def write(self, data, sha):
        if self.inject_conflict:
            self.inject_conflict = False
            self.data = {"scope": "project", "attempts": [{"model": "gemini-3.5-flash", "at": 0}], "campaigns": {}}
            self.version += 1
        if sha != str(self.version):
            raise RPMConflict("stale SHA")
        self.data = data
        self.version += 1


class SharedRPMTests(unittest.TestCase):
    def test_remote_store_requires_runtime_state_branch_and_credentials(self):
        with self.assertRaises(RPMUnavailable):
            GitHubRPMStore("owner/repo", "token", branch="main")
        with self.assertRaises(RPMUnavailable):
            GitHubRPMStore("owner/repo", "", branch="runtime-state")

    def test_remote_cas_conflict_is_not_treated_as_success(self):
        store = GitHubRPMStore("owner/repo", "dummy", branch="runtime-state")
        with patch("experiments.ready_yield_shared_rpm.requests.put",
                   return_value=SimpleNamespace(status_code=409, text="conflict")):
            with self.assertRaises(RPMConflict):
                store.write({"scope": "project", "attempts": []}, "old-sha")

    def test_rolling_limit_and_cross_model_spacing(self):
        store = MemoryStore()
        guard = SharedRPM(store, "project")
        self.assertEqual(guard.reserve("gemini-3.6-flash", 0), 0)
        self.assertEqual(guard.reserve("gemini-3.5-flash", 10), 15)
        self.assertEqual(guard.reserve("gemini-3.5-flash", 25), 0)
        self.assertEqual(guard.reserve("gemini-3.6-flash", 50), 0)
        self.assertEqual(guard.reserve("gemini-3.6-flash", 75), 0)
        self.assertEqual(len(store.data["attempts"]), 3)

    def test_cas_conflict_rereads_and_respects_other_run(self):
        store = MemoryStore()
        store.inject_conflict = True
        guard = SharedRPM(store, "project")
        self.assertEqual(guard.reserve("gemini-3.6-flash", 10), 15)
        self.assertEqual(len(store.data["attempts"]), 1)

    def test_scope_mismatch_and_unrecognized_model_fail_closed(self):
        store = MemoryStore()
        store.data = {"scope": "different", "attempts": []}
        with self.assertRaises(RPMUnavailable):
            SharedRPM(store, "project").reserve("gemini-3.6-flash", 100)
        with self.assertRaises(RPMUnavailable):
            SharedRPM(MemoryStore(), "project").reserve("gemini-3.7-flash", 0)

    def test_corrupt_timestamp_fails_closed(self):
        store = MemoryStore()
        store.data = {"scope": "project", "attempts": [{"model": "gemini-3.5-flash", "at": "bad"}]}
        with self.assertRaises(RPMUnavailable):
            SharedRPM(store, "project").reserve("gemini-3.6-flash", 100)

    def test_campaign_claim_is_durable_and_single_use(self):
        store = MemoryStore()
        store.data = {"scope": "project", "attempts": [], "campaigns": {}}
        guard = SharedRPM(store, "project", campaign_id="fixed-evidence-20260925", run_id="123")
        guard.claim_campaign()
        self.assertEqual(guard.reserve("gemini-3.6-flash", 100), 0)
        self.assertEqual(store.data["campaigns"]["fixed-evidence-20260925"]["used"], 1)
        with self.assertRaises(RPMUnavailable):
            SharedRPM(store, "project", campaign_id="fixed-evidence-20260925", run_id="456").claim_campaign()
        with self.assertRaises(RPMUnavailable):
            guard.claim_campaign()

    def test_campaign_persistent_four_attempt_limit(self):
        store = MemoryStore()
        store.data = {"scope": "project", "attempts": [], "campaigns": {}}
        guard = SharedRPM(store, "project", campaign_id="fixed-evidence-20260925", run_id="123")
        guard.claim_campaign()
        for index in range(4):
            self.assertEqual(guard.reserve("gemini-3.6-flash", 100 + index * 25), 0)
        with self.assertRaises(RPMUnavailable):
            guard.reserve("gemini-3.6-flash", 200)

    def test_missing_ledger_fails_closed(self):
        store = GitHubRPMStore("owner/repo", "dummy", branch="runtime-state")
        with patch("experiments.ready_yield_shared_rpm.requests.get",
                   return_value=SimpleNamespace(status_code=404)):
            with self.assertRaises(RPMUnavailable):
                store.read()

    def test_continuation_uses_only_campaign_remaining_slots(self):
        store = MemoryStore()
        store.data["campaigns"]["ready-yield-fixed-evidence-20260925"] = {
            "run_id": "old", "used": 1}
        guard = SharedRPM(store, "project", campaign_id="ready-yield-fixed-evidence-20260925-continuation",
                          run_id="new")
        guard.claim_campaign()
        for index in range(3):
            self.assertEqual(guard.reserve("gemini-3.5-flash", 100 + index * 25), 0)
        with self.assertRaises(RPMUnavailable):
            guard.reserve("gemini-3.5-flash", 200)

    def test_second_continuation_cannot_claim_after_four_reserved_slots(self):
        store = MemoryStore()
        store.data["campaigns"]["old"] = {"run_id": "old", "used": 4}
        with self.assertRaises(RPMUnavailable):
            SharedRPM(store, "project", campaign_id="new", run_id="new").claim_campaign()

    def test_recovery_campaign_adds_two_only_after_exact_prior_history(self):
        store = MemoryStore()
        old = {
            "ready-yield-fixed-evidence-20260925": {"run_id": "first", "used": 1},
            "ready-yield-fixed-evidence-20260925-continuation": {"run_id": "second", "used": 3},
        }
        store.data["campaigns"] = old.copy()
        campaign = SharedRPM(store, "project", campaign_id=SharedRPM.RECOVERY_CAMPAIGN,
                             run_id="recovery")
        campaign.claim_campaign()
        self.assertEqual(campaign.reserve("gemini-3.6-flash", 100), 0)
        self.assertEqual(campaign.reserve("gemini-3.5-flash", 125), 0)
        self.assertEqual({k: store.data["campaigns"][k] for k in old}, old)
        self.assertEqual(store.data["campaigns"][SharedRPM.RECOVERY_CAMPAIGN]["used"], 2)
        with self.assertRaises(RPMUnavailable):
            campaign.reserve("gemini-3.6-flash", 150)
        with self.assertRaises(RPMUnavailable):
            SharedRPM(store, "project", campaign_id="another", run_id="x").claim_campaign()
        with self.assertRaises(RPMUnavailable):
            campaign.claim_campaign()

    def test_recovery_rejects_incorrect_prior_history(self):
        for old in ({"old": {"run_id": "x", "used": 4}},
                    {"ready-yield-fixed-evidence-20260925": {"run_id": "first", "used": 1}}):
            store = MemoryStore()
            store.data["campaigns"] = old
            with self.assertRaises(RPMUnavailable):
                SharedRPM(store, "project", campaign_id=SharedRPM.RECOVERY_CAMPAIGN,
                          run_id="recovery").claim_campaign()

    def test_0400_campaign_adds_at_most_four_after_six_historical_sends(self):
        store = MemoryStore()
        history = {
            "ready-yield-fixed-evidence-20260925": {"run_id": "first", "used": 1},
            "ready-yield-fixed-evidence-20260925-continuation": {"run_id": "second", "used": 3},
            SharedRPM.RECOVERY_CAMPAIGN: {"run_id": "third", "used": 2},
        }
        store.data["campaigns"] = history.copy()
        guard = SharedRPM(store, "project", campaign_id=SharedRPM.CAMPAIGN_0400,
                          run_id="scheduled")
        guard.claim_campaign()
        for i in range(4):
            self.assertEqual(guard.reserve("gemini-3.6-flash", 100 + i * 25), 0)
        self.assertEqual({k: store.data["campaigns"][k] for k in history}, history)
        self.assertEqual(store.data["campaigns"][SharedRPM.CAMPAIGN_0400]["used"], 4)
        with self.assertRaises(RPMUnavailable):
            guard.reserve("gemini-3.5-flash", 200)
        with self.assertRaises(RPMUnavailable):
            guard.claim_campaign()

    def test_0400_rejects_missing_or_changed_history(self):
        for used in (1, 3):
            store = MemoryStore()
            store.data["campaigns"] = {
                "ready-yield-fixed-evidence-20260925": {"run_id": "first", "used": 1},
                "ready-yield-fixed-evidence-20260925-continuation": {"run_id": "second", "used": 3},
                SharedRPM.RECOVERY_CAMPAIGN: {"run_id": "third", "used": used},
            }
            with self.assertRaises(RPMUnavailable):
                SharedRPM(store, "project", campaign_id=SharedRPM.CAMPAIGN_0400,
                          run_id="scheduled").claim_campaign()
