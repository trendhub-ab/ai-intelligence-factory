from __future__ import annotations

import unittest
from pathlib import Path

import run202_chatops_control as chatops


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "chatops-one-shot.yml"


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

    def test_ready_draft_regenerate_rejects_malformed_target_or_extra_text(self):
        for body in (
            "/aiif note regenerate 3f6479ff-dca9-81cc-b538-c67969b8021a",
            "/aiif note regenerate 3f6479ffdca981ccb538c67969b8021a ",
            "/aiif note regenerate 3f6479ffdca981ccb538c67969b8021a please",
            "/aiif note regenerate ../../etc/passwd",
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


if __name__ == "__main__":
    unittest.main()
