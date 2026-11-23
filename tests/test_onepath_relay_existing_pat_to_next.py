"""Offline owner Issue and safe GitHub PAT transfer contract; no network/credentials."""
from pathlib import Path
from unittest.mock import patch
import unittest

import onepath_relay_existing_pat_to_next as relay

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/onepath-old-pat-next-secret-relay.yml"
PAT = "fake-token-never-use-123456"
ENV = {
    "GITHUB_EVENT_NAME": "issues",
    "GITHUB_REPOSITORY": relay.OLD,
    "GITHUB_ACTOR": relay.OWNER,
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_RUN_ATTEMPT": "1",
    "GITHUB_RUN_ID": "45187982493",
    "OLD_OWNER_PAT": PAT,
    "OLD_OWNER_PAT_PRESENT": "true",
}
EVENT = {
    "action": "opened",
    "issue": {"title": relay.TITLE, "body": relay.BODY,
              "user": {"login": relay.OWNER}},
    "sender": {"login": relay.OWNER},
    "repository": {"full_name": relay.OLD, "private": False},
}


class FakeGitHub:
    def __init__(self, preexisting=False, reject_at=None):
        self.exists = preexisting
        self.at = 0
        self.reject_at = reject_at
        self.calls = []
        self.sealed = None

    def __call__(self, method, path, pat, payload=None):
        assert pat == PAT
        self.calls.append((method, path))
        self.at += 1
        if self.reject_at == self.at:
            raise relay.RelayStopped("RELAY_HTTP_UNKNOWN_STOP")
        if method == "GET" and path == relay.TARGET:
            return (200, {"name": "GH_PAT"}) if self.exists else (404, {})
        if method == "GET" and path == relay.GITHUB_PUBLIC_KEY:
            return 200, {"key": "mock-public-base64", "key_id": "mock-key-id"}
        if method == "PUT" and path == relay.TARGET:
            assert not self.exists
            assert set(payload) == {"key_id", "encrypted_value"}
            self.sealed = payload["encrypted_value"]
            self.exists = True
            return 201, {}
        raise AssertionError((method, path))


class OwnerPatRelayTests(unittest.TestCase):
    def test_owner_issue_requires_exact_identity_and_initial_attempt(self):
        relay.require_owner(EVENT, ENV)
        for event, env in (
            (EVENT, {**ENV, "GITHUB_ACTOR": "other"}),
            (EVENT, {**ENV, "GITHUB_RUN_ATTEMPT": "2"}),
            (EVENT, {**ENV, "GITHUB_REF": "refs/heads/feature"}),
            (EVENT, {**ENV, "OLD_OWNER_PAT_PRESENT": "false"}),
            ({**EVENT, "action": "edited"}, ENV),
            ({**EVENT, "repository": {**EVENT["repository"], "private": True}}, ENV),
            ({**EVENT, "issue": {**EVENT["issue"], "body": "anything else"}}, ENV),
        ):
            with self.subTest(event=event, env=env):
                with self.assertRaises(relay.RelayStopped):
                    relay.require_owner(event, env)

    def test_preexisting_next_pat_blocks_without_write(self):
        gh = FakeGitHub(preexisting=True)
        with self.assertRaisesRegex(relay.RelayStopped, "ALREADY_EXISTS"):
            relay.transfer_once(EVENT, ENV, gh)
        self.assertEqual(gh.calls, [("GET", relay.TARGET)])

    def test_transfer_one_encrypted_write_and_verify(self):
        gh = FakeGitHub()
        with patch.object(relay, "sealed_pat", side_effect=lambda token, pk: "only-encrypted-data"):
            report = relay.transfer_once(EVENT, ENV, gh)
        self.assertEqual(gh.calls, [
            ("GET", relay.TARGET), ("GET", relay.GITHUB_PUBLIC_KEY),
            ("PUT", relay.TARGET), ("GET", relay.TARGET),
        ])
        self.assertEqual(gh.sealed, "only-encrypted-data")
        self.assertEqual(report["status"], "NEXT_GH_PAT_METADATA_VERIFIED")
        self.assertEqual(report["secret_write_attempts"], 1)
        self.assertNotIn(PAT, str(report))
        self.assertEqual(report["model_calls"], 0)
        self.assertEqual(report["note_writes"], 0)
        self.assertEqual(report["vm_starts"], 0)

    def test_unknown_write_stops_and_next_issue_replay_does_not_overwrite(self):
        gh = FakeGitHub(reject_at=4)
        with patch.object(relay, "sealed_pat", return_value="sealed"):
            with self.assertRaises(relay.RelayStopped):
                relay.transfer_once(EVENT, ENV, gh)
            gh.reject_at = None
            with self.assertRaisesRegex(relay.RelayStopped, "ALREADY_EXISTS"):
                relay.transfer_once(EVENT, ENV, gh)
        self.assertEqual([a for a in gh.calls if a[0] == "PUT"],
                         [("PUT", relay.TARGET)])

    def test_fail_closed_on_unavailable_public_key(self):
        gh = FakeGitHub(reject_at=2)
        with self.assertRaises(relay.RelayStopped):
            relay.transfer_once(EVENT, ENV, gh)
        self.assertNotIn(("PUT", relay.TARGET), gh.calls)

    def test_workflow_has_explicit_owner_issue_and_no_other_services(self):
        y = WORKFLOW.read_text()
        for s in (
            "issues:\n    types: [opened]",
            "github.actor == 'trendhub-ab'",
            "github.event.issue.user.login == 'trendhub-ab'",
            "github.event.issue.title == 'AIIF OLD: APPROVE ONEPATH RELAY EXISTING PAT TO NEXT'",
            "github.event.issue.body == 'OWNER_APPROVES_ENCRYPTED_EXISTING_GH_PAT_RELAY_V1'",
            "github.run_attempt == 1",
            "secrets.GH_PAT",
            "PyNaCl==1.5.0",
            "contents: read",
        ):
            self.assertIn(s, y)
        for forbidden in (
            "schedule:", "workflow_dispatch:", "pull_request_target:",
            "id-token: write", "contents: write", "actions: write",
            "NOTION_API_KEY", "NOTE_STORAGE_STATE_B64", "GCP_",
            "gemini", "note.com", "gh secret set",
        ):
            self.assertNotIn(forbidden, y)


if __name__ == "__main__":
    unittest.main()
