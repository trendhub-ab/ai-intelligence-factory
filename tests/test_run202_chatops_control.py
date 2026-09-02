from __future__ import annotations

import unittest
from pathlib import Path

import run202_chatops_control as chatops


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "chatops-one-shot.yml"


def event(*, issue=71, login="trendhub-ab", body="/aiif run article_validation", pull_request=None):
    issue_payload = {"number": issue}
    if pull_request is not None:
        issue_payload["pull_request"] = pull_request
    return {
        "issue": issue_payload,
        "comment": {"user": {"login": login}, "body": body},
    }


class Run202ChatOpsAuthorizationTests(unittest.TestCase):
    def test_article_validation_is_authorized(self):
        result = chatops.authorize_event(event())
        self.assertTrue(result["authorized"])
        self.assertEqual(result["mode"], "article_validation")

    def test_pending_retry_validation_is_authorized(self):
        result = chatops.authorize_event(event(body="/aiif run pending_retry_validation"))
        self.assertTrue(result["authorized"])
        self.assertEqual(result["mode"], "pending_retry_validation")

    def test_full_is_authorized(self):
        result = chatops.authorize_event(event(body="/aiif run full"))
        self.assertTrue(result["authorized"])
        self.assertEqual(result["mode"], "full")

    def test_wrong_issue_fails_closed(self):
        self.assertFalse(chatops.authorize_event(event(issue=72))["authorized"])

    def test_wrong_actor_fails_closed(self):
        self.assertFalse(chatops.authorize_event(event(login="someone-else"))["authorized"])

    def test_pull_request_comment_fails_closed(self):
        self.assertFalse(chatops.authorize_event(event(pull_request={"url": "x"}))["authorized"])

    def test_whitespace_or_extra_text_is_rejected(self):
        for body in (
            "/aiif run article_validation ",
            " /aiif run article_validation",
            "/aiif run article_validation\n",
            "/aiif run article_validation please",
            "/aiif run pending_retry_validation ",
            "/aiif run pending_retry",
            "/aiif run FULL",
            "RUN_ONCE",
        ):
            with self.subTest(body=body):
                self.assertFalse(chatops.authorize_event(event(body=body))["authorized"])

    def test_missing_shapes_fail_closed(self):
        for payload in ({}, {"issue": {}}, {"comment": {}}, {"issue": {"number": "x"}, "comment": {}}):
            with self.subTest(payload=payload):
                self.assertFalse(chatops.authorize_event(payload)["authorized"])


class Run202ChatOpsWorkflowContractTests(unittest.TestCase):
    def test_workflow_is_narrow_and_dispatches_only_existing_one_shot(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("issue_comment:", text)
        self.assertIn("types: [created]", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("push:", text)
        self.assertIn("actions: write", text)
        self.assertIn("contents: read", text)
        self.assertNotIn("contents: write", text)
        self.assertIn("github.run_attempt == 1", text)
        self.assertIn("github.event.issue.number == 71", text)
        self.assertIn("github.event.comment.user.login == 'trendhub-ab'", text)
        self.assertIn("github.actor == 'trendhub-ab'", text)
        self.assertIn("/aiif run article_validation", text)
        self.assertIn("/aiif run pending_retry_validation", text)
        self.assertIn("/aiif run full", text)
        self.assertIn("daily-one-shot.yml/dispatches", text)
        self.assertIn('"ref":"main"', text)
        self.assertIn('"confirm":"RUN_ONCE"', text)
        self.assertNotIn("production_pipeline.py", text)
        self.assertNotIn("pending_retry_validation.py", text)
        self.assertNotIn("note-create-draft.yml", text)
        self.assertNotIn("run194_note_persistent_cloud.py", text)
        self.assertNotIn("playwright", text)


if __name__ == "__main__":
    unittest.main()
