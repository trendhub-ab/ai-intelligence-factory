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

    def test_production_e2e_validation_is_authorized(self):
        result = chatops.authorize_event(event(body="/aiif run production_e2e_validation"))
        self.assertTrue(result["authorized"])
        self.assertEqual(result["mode"], "production_e2e_validation")

    def test_full_is_authorized(self):
        result = chatops.authorize_event(event(body="/aiif run full"))
        self.assertTrue(result["authorized"])
        self.assertEqual(result["mode"], "full")

    def test_x_discovery_stage2_is_authorized(self):
        result = chatops.authorize_event(event(body="/aiif run x_discovery_stage2"))
        self.assertTrue(result["authorized"])
        self.assertEqual(result["mode"], "x_discovery_stage2")

    def test_zero_api_portfolio_audit_is_authorized(self):
        result = chatops.authorize_event(event(body="/aiif run stale_ready_portfolio_audit"))
        self.assertEqual(result, {"authorized": True, "mode": "stale_ready_portfolio_audit", "reason": "authorized"})

    def test_retired_recovery_commands_fail_closed(self):
        for body in (
            "/aiif run current_policy_ready_recovery",
            "/aiif run ready_metadata_rebase",
        ):
            with self.subTest(body=body):
                self.assertFalse(chatops.authorize_event(event(body=body))["authorized"])

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
            "/aiif run x_discovery_stage2 ",
            "/aiif run x_discovery",
            "/aiif run current_policy_ready_recovery ",
            "/aiif run current_policy_ready",
            "/aiif run ready_metadata_rebase ",
            "/aiif run ready_metadata",
            "/aiif run FULL",
            "RUN_ONCE",
            "RECOVER_ONE_READY",
            "REBASE_GENREC_READY",
        ):
            with self.subTest(body=body):
                self.assertFalse(chatops.authorize_event(event(body=body))["authorized"])

    def test_missing_shapes_fail_closed(self):
        for payload in ({}, {"issue": {}}, {"comment": {}}, {"issue": {"number": "x"}, "comment": {}}):
            with self.subTest(payload=payload):
                self.assertFalse(chatops.authorize_event(payload)["authorized"])


class Run202ChatOpsWorkflowContractTests(unittest.TestCase):
    def test_workflow_is_narrow_and_dispatches_only_active_manual_workflows(self):
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
        self.assertIn("/aiif run production_e2e_validation", text)
        self.assertIn("/aiif run full", text)
        self.assertIn("/aiif run x_discovery_stage2", text)
        self.assertNotIn("/aiif run current_policy_ready_recovery", text)
        self.assertNotIn("/aiif run ready_metadata_rebase", text)
        self.assertIn("daily-one-shot.yml", text)
        self.assertIn("x-discovery-stage2-smoke.yml", text)
        self.assertNotIn("current-policy-ready-recovery.yml", text)
        self.assertNotIn("current-ready-metadata-rebase.yml", text)
        self.assertIn('"ref":"main"', text)
        self.assertIn('"confirm":"RUN_ONCE"', text)
        self.assertIn("payload='{\"ref\":\"main\"}'", text)
        self.assertNotIn('"confirm":"RECOVER_ONE_READY"', text)
        self.assertNotIn('"confirm":"REBASE_GENREC_READY"', text)
        self.assertNotIn("production_pipeline.py", text)
        self.assertNotIn("pending_retry_validation.py", text)
        self.assertNotIn("note-create-draft.yml", text)
        self.assertNotIn("run194_note_persistent_cloud.py", text)
        self.assertNotIn("playwright", text)

    def test_dispatch_uses_chainable_pat_and_fails_closed_without_it(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("GH_TOKEN: ${{ secrets.GH_PAT }}", text)
        self.assertNotIn("GH_TOKEN: ${{ github.token }}", text)
        self.assertIn('if [ -z "${GH_TOKEN:-}" ]; then', text)
        self.assertIn("GH_PAT is required for ChatOps ONE-SHOT dispatch", text)

    def test_x_stage2_dispatch_does_not_pass_production_or_model_credentials(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("x_discovery_stage2)", text)
        self.assertIn("target='x-discovery-stage2-smoke.yml'", text)
        self.assertNotIn("GEMINI_API_KEY:", text)
        self.assertNotIn("NOTION_API_KEY:", text)
        self.assertNotIn("GOOGLE_API_KEY:", text)


    def test_zero_api_portfolio_audit_dispatches_read_only_workflow(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("/aiif run stale_ready_portfolio_audit", text)
        self.assertIn("target='stale-ready-retirement-audit.yml'", text)
        self.assertNotIn("GEMINI_API_KEY:", text)


if __name__ == "__main__":
    unittest.main()
