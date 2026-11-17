"""Offline adversarial tests for the v0.4 owner-only ChatOps inspect exception."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import run_v04_chatops_control as control

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/v04-owner-chatops-inspect.yml"
TARGET = ROOT / ".github/workflows/v04-single-note-draft-bridge.yml"

ENV = {
    "repository": control.REPOSITORY,
    "event_name": "issue_comment",
    "ref": "refs/heads/main",
    "actor": control.OWNER,
    "run_attempt": "1",
}


def event():
    return {
        "action": "created",
        "repository": {"full_name": control.REPOSITORY},
        "issue": {
            "number": 71, "title": "AIIF ChatOps Control",
            "state": "open", "user": {"login": control.OWNER},
        },
        "comment": {
            "id": 987654321, "body": control.COMMAND,
            "user": {"login": control.OWNER},
            "author_association": "OWNER",
        },
        "sender": {"login": control.OWNER},
    }


class V04ChatOpsControlTests(unittest.TestCase):
    def test_only_exact_owner_command_is_accepted(self):
        self.assertEqual(
            control.authorize_event(event(), **ENV),
            {"authorized": True, "operation": "inspect", "comment_id": 987654321},
        )

    def test_wrong_event_envelope_fails_closed(self):
        for key, value in (
            ("repository", "another/repo"), ("event_name", "issues"),
            ("ref", "refs/heads/branch"), ("actor", "another-user"),
            ("run_attempt", "2"), ("run_attempt", ""),
        ):
            with self.subTest(key=key, value=value):
                env = {**ENV, key: value}
                self.assertFalse(control.authorize_event(event(), **env)["authorized"])

    def test_owner_and_identity_must_match_every_layer(self):
        for field, changes in (
            ("repository", {"full_name": "other/repo"}),
            ("issue", {"number": 72}),
            ("issue", {"number": True}),
            ("issue", {"title": "Another Issue"}),
            ("issue", {"state": "closed"}),
            ("issue", {"user": {"login": "other"}}),
            ("issue", {"pull_request": {"url": "https://github.com/x/pull/1"}}),
            ("comment", {"user": {"login": "other"}}),
            ("comment", {"author_association": "MEMBER"}),
            ("comment", {"id": -1}),
            ("comment", {"id": "987654321"}),
            ("sender", {"login": "other"}),
        ):
            with self.subTest(field=field, changes=changes):
                sample = event()
                sample[field].update(changes)
                self.assertFalse(control.authorize_event(sample, **ENV)["authorized"])

    def test_only_exact_read_only_operation_can_be_invoked(self):
        for command in (
            "/aiif v04 create 204", "/aiif note draft",
            "/aiif run full", "/aiif v04 inspect",
            "/aiif v04 inspect 205",
            "/aiif v04 inspect 204 ",
            " /aiif v04 inspect 204",
            "/aiif v04 inspect 204\n",
            "/aiif v04 inspect 204 && echo hacked",
            "/aiif v04 publish 204",
        ):
            with self.subTest(command=command):
                sample = event()
                sample["comment"]["body"] = command
                self.assertFalse(control.authorize_event(sample, **ENV)["authorized"])

    def test_event_shape_and_action_rejected(self):
        for bad in (None, {}, {"action": "created"}, 10, []):
            with self.subTest(sample=repr(bad)):
                self.assertFalse(control.authorize_event(bad, **ENV)["authorized"])
        for action in ("edited", "deleted", None):
            sample = event()
            sample["action"] = action
            self.assertFalse(control.authorize_event(sample, **ENV)["authorized"])

    def test_main_returns_safe_output_for_exact_event_only(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            input_path = folder / "event.json"
            output_path = folder / "output.txt"
            input_path.write_text(json.dumps(event()), encoding="utf-8")
            with patch.dict(os.environ, {
                "GITHUB_EVENT_PATH": str(input_path),
                "GITHUB_OUTPUT": str(output_path),
                "GITHUB_REPOSITORY": control.REPOSITORY,
                "GITHUB_EVENT_NAME": "issue_comment",
                "GITHUB_REF": "refs/heads/main",
                "GITHUB_ACTOR": control.OWNER,
                "GITHUB_RUN_ATTEMPT": "1",
            }):
                self.assertEqual(control.main(), 0)
                self.assertEqual(output_path.read_text(encoding="utf-8"),
                                 "authorized=true\noperation=inspect\ncomment_id=987654321\n")
                output_path.unlink()
                bad = event()
                bad["comment"]["body"] = "/aiif v04 create 204"
                input_path.write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaisesRegex(SystemExit, "V04_CHATOPS_UNAUTHORIZED"):
                    control.main()
                self.assertFalse(output_path.exists())

    def test_workflow_is_exact_one_off_dispatch_only(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        expected_sha = "1f39788f6c1c9dc9e9ca93af5c260e0c396374f76b5dc33c3ece0def3cffb690"
        self.assertIn("issue_comment:", text)
        self.assertIn("types: [created]", text)
        self.assertIn("github.event.issue.number == 71", text)
        self.assertIn("github.event.comment.user.login == 'trendhub-ab'", text)
        self.assertIn("github.actor == 'trendhub-ab'", text)
        self.assertIn("github.run_attempt == 1", text)
        self.assertIn("github.event.comment.body == '/aiif v04 inspect 204'", text)
        self.assertIn("python run_v04_chatops_control.py", text)
        self.assertIn("python -m unittest tests.test_run_v04_chatops_control -v", text)
        self.assertIn("GH_TOKEN: ${{ secrets.GH_PAT }}", text)
        self.assertIn("GH_TOKEN: ${{ github.token }}", text)
        self.assertIn("issues: write", text)
        self.assertIn("actions: write", text)
        self.assertIn("content=eyes", text)
        self.assertIn("steps.claim.outputs.dispatch == 'true'", text)
        self.assertIn("v04-single-note-draft-bridge.yml/dispatches", text)
        self.assertIn('"operation":"inspect"', text)
        self.assertIn('"source_issue_number":"204"', text)
        self.assertIn(expected_sha, text)
        self.assertNotIn('"operation":"create"', text)
        self.assertNotIn("daily-one-shot.yml/dispatches", text)
        self.assertNotIn("note-create-draft.yml/dispatches", text)
        self.assertLess(text.index("id: claim"), text.index("v04-single-note-draft-bridge.yml/dispatches"))

    def test_target_still_prevents_duplicate_or_unapproved_write(self):
        text = TARGET.read_text(encoding="utf-8")
        self.assertIn("github.actor == 'trendhub-ab'", text)
        self.assertIn("inputs.operation == 'inspect'", text)
        self.assertIn("inputs.operation == 'create'", text)
        self.assertIn("github.run_attempt == 1", text)
        self.assertIn("note-draft-create-v2", text)
        self.assertIn("stop-note-vm:", text)

    def test_retired_v1_chatops_remain_disabled(self):
        for filename in ("chatops-note.yml", "chatops-one-shot.yml", "chatops-note-audit.yml"):
            text = (ROOT / ".github/workflows" / filename).read_text(encoding="utf-8")
            self.assertIn("if: ${{ false }}", text)


if __name__ == "__main__":
    unittest.main()
