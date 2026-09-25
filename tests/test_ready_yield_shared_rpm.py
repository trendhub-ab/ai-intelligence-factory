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
