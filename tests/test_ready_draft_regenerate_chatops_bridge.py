from __future__ import annotations

import unittest
from pathlib import Path

import run202_chatops_control as chatops


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "chatops-one-shot.yml"
REGEN_WORKFLOW = ROOT / ".github" / "workflows" / "ready-draft-regenerate-once.yml"


def event(body: str):
    return {
        "issue": {"number": 71},
        "comment": {"user": {"login": "trendhub-ab"}, "body": body},
    }


class ReadyDraftRegenerateChatOpsBridgeTests(unittest.TestCase):
    def test_exact_ready_draft_regenerate_command_is_authorized(self):
        sync_id = "3f6479ffdca981ccb538c67969b8021a"
        result = chatops.authorize_event(event(f"/aiif note regenerate {sync_id}"))
        self.assertEqual(result["mode"], "ready_draft_regenerate")
        self.assertEqual(result["target_sync_id"], sync_id)
        self.assertTrue(result["authorized"])

    def test_exact_ready_draft_resume_command_is_authorized(self):
        sync_id = "3f6479ffdca981ccb538c67969b8021a"
        result = chatops.authorize_event(event(f"/aiif note regenerate_resume {sync_id}"))
        self.assertEqual(result["mode"], "ready_draft_regenerate_resume")
        self.assertEqual(result["target_sync_id"], sync_id)
        self.assertTrue(result["authorized"])

    def test_ready_draft_regenerate_rejects_malformed_target_or_extra_text(self):
        for body in (
            "/aiif note regenerate 3f6479ff-dca9-81cc-b538-c67969b8021a",
            "/aiif note regenerate 3f6479ffdca981ccb538c67969b8021a ",
            "/aiif note regenerate 3f6479ffdca981ccb538c67969b8021a please",
            "/aiif note regenerate ../../etc/passwd",
            "/aiif note regenerate_resume 3f6479ff-dca9-81cc-b538-c67969b8021a",
            "/aiif note regenerate_resume 3f6479ffdca981ccb538c67969b8021a please",
        ):
            with self.subTest(body=body):
                self.assertFalse(chatops.authorize_event(event(body))["authorized"])

    def test_workflow_dispatches_exact_regeneration_to_reviewed_one_shot(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("startsWith(github.event.comment.body, '/aiif note regenerate ')", text)
        self.assertIn("ready_draft_regenerate)", text)
        self.assertIn("target='ready-draft-regenerate-once.yml'", text)
        self.assertIn(
            'payload="$(printf \'{"ref":"main","inputs":{"sync_id":"%s","confirm":"RUN_ONCE"}}\' "$TARGET_SYNC_ID")"',
            text,
        )

    def test_resume_dispatches_same_reviewed_one_shot_with_zero_provider_operation(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        regen = REGEN_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("startsWith(github.event.comment.body, '/aiif note regenerate_resume ')", text)
        self.assertIn("ready_draft_regenerate_resume)", text)
        self.assertIn('"operation":"resume_persisted"', text)
        self.assertIn("resume_persisted", regen)
        self.assertIn("--resume-persisted", regen)


if __name__ == "__main__":
    unittest.main()
