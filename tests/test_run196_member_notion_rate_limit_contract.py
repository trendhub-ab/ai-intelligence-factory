from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class Run196MemberNotionRateLimitContractTests(unittest.TestCase):
    def test_member_writers_share_one_cross_workflow_lock(self):
        member = (WORKFLOWS / "member-presentation-sync.yml").read_text(encoding="utf-8")
        brief = (WORKFLOWS / "subscriber-decision-brief.yml").read_text(encoding="utf-8")
        expected = "group: member-derived-notion-writes"
        self.assertIn(expected, member)
        self.assertIn(expected, brief)
        self.assertIn("cancel-in-progress: false", member)
        self.assertIn("cancel-in-progress: false", brief)

    def test_decision_brief_workflow_has_bounded_rate_limit_recovery_budget(self):
        brief = (WORKFLOWS / "subscriber-decision-brief.yml").read_text(encoding="utf-8")
        self.assertIn("timeout-minutes: 30", brief)
        self.assertIn('SUBSCRIBER_DECISION_BRIEF_PACING_SECONDS: "0.40"', brief)
        self.assertIn('SUBSCRIBER_DECISION_BRIEF_REQUEST_MAX_ATTEMPTS: "8"', brief)
        self.assertIn('SUBSCRIBER_DECISION_BRIEF_RETRY_AFTER_MAX_SECONDS: "120"', brief)

    def test_decision_brief_transport_is_centralized(self):
        source = (ROOT / "subscriber_decision_brief.py").read_text(encoding="utf-8")
        self.assertIn("def _response_retry_after(", source)
        self.assertIn("def _request(", source)
        for direct in ("requests.get(", "requests.post(", "requests.patch(", "requests.delete("):
            self.assertNotIn(direct, source)


if __name__ == "__main__":
    unittest.main()