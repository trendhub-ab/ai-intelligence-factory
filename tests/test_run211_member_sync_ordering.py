from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class Run211MemberSyncOrderingTests(unittest.TestCase):
    def _text(self, name: str) -> str:
        return (WORKFLOWS / name).read_text(encoding="utf-8")

    def test_inventory_run_exposes_apply_vs_plan_without_changing_plan_contract(self) -> None:
        text = self._text("inventory-bootstrap.yml")
        self.assertIn("run-name: Subscriber Inventory Bootstrap [${{ inputs.mode }}]", text)
        self.assertIn('description: "plan=0 API/read-only, apply=Product Review only"', text)
        self.assertIn('if [ "${{ inputs.mode }}" = "plan" ]', text)

    def test_subscriber_brief_follows_all_authoritative_source_mutators(self) -> None:
        text = self._text("subscriber-decision-brief.yml")
        self.assertIn("- Daily Intelligence & Content Pipeline", text)
        self.assertIn("- Daily Intelligence & Content Pipeline [ONE-SHOT]", text)
        self.assertIn("- Subscriber Inventory Bootstrap", text)

    def test_inventory_plan_cannot_fan_out_into_member_writes(self) -> None:
        text = self._text("subscriber-decision-brief.yml")
        self.assertIn("github.event.workflow_run.name != 'Subscriber Inventory Bootstrap'", text)
        self.assertIn("contains(github.event.workflow_run.display_title, '[apply]')", text)

    def test_presentation_is_downstream_of_subscriber_brief_not_parallel_with_source(self) -> None:
        text = self._text("member-presentation-sync.yml")
        workflow_run = text.split("workflow_run:", 1)[1].split("types: [completed]", 1)[0]
        self.assertIn("Subscriber Decision Brief Sync", workflow_run)
        self.assertNotIn("Daily Intelligence & Content Pipeline", workflow_run)
        self.assertNotIn("Subscriber Inventory Bootstrap", workflow_run)

    def test_member_derived_writers_remain_serialized(self) -> None:
        brief = self._text("subscriber-decision-brief.yml")
        presentation = self._text("member-presentation-sync.yml")
        marker = "group: member-derived-notion-writes"
        self.assertIn(marker, brief)
        self.assertIn(marker, presentation)
        self.assertIn("cancel-in-progress: false", brief)
        self.assertIn("cancel-in-progress: false", presentation)

    def test_derived_member_syncs_are_zero_gemini(self) -> None:
        brief = self._text("subscriber-decision-brief.yml")
        presentation = self._text("member-presentation-sync.yml")
        self.assertNotIn("GEMINI_API_KEY", brief)
        self.assertNotIn("GEMINI_API_KEY", presentation)
        self.assertNotIn("google.generative", brief)
        self.assertNotIn("google.generative", presentation)


if __name__ == "__main__":
    unittest.main()
