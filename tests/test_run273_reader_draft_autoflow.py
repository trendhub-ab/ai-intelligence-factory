from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

import reader_value_review_bridge as bridge


ROOT = Path(__file__).resolve().parents[1]
READY_WORKFLOW = ROOT / ".github" / "workflows" / "note-ready-sync.yml"
DRAFT_WORKFLOW = ROOT / ".github" / "workflows" / "note-create-draft.yml"


class Run273ReaderRetryTests(unittest.TestCase):
    def _pipeline(self):
        return SimpleNamespace(
            GATE_SEVERITY_HARD="HARD",
            GATE_SEVERITY_REVIEW="REVIEW",
            REASON_CODE_PUB_SCORE_NARRATIVE_MISMATCH="pub_score_narrative_mismatch",
            REASON_CODE_APPEAL_DECISION_VOICE_LOSS="appeal_decision_voice_loss",
            validate_human_appeal_gate=lambda parsed, peer_articles=None: ("ACCEPTABLE", []),
            should_attempt_dynamic_retry=lambda rows, evidence, origin="new": (True, "base_retry"),
            build_decision_prompt=lambda *args, **kwargs: "BASE PROMPT",
            build_dynamic_retry_instruction=lambda rows: ("BASE RETRY", []),
            _reader_experience_signals=lambda article: {},
        )

    def test_reader_only_failure_still_spends_zero_extra_retry(self) -> None:
        pipeline = self._pipeline()
        bridge.install(pipeline)
        result = pipeline.should_attempt_dynamic_retry(
            [
                {
                    "severity": "REVIEW",
                    "message": "reader_value_review:multi_axis_reader_weakness",
                }
            ],
            None,
            "new",
        )
        self.assertEqual(result, (False, "reader_value_review_no_retry"))

    def test_existing_quality_retry_carries_reader_value_repair_guidance(self) -> None:
        pipeline = self._pipeline()
        bridge.install(pipeline)
        rows = [
            {
                "severity": "HARD",
                "reason_code": "pub_score_narrative_mismatch",
                "message": "score_narrative_mismatch",
            },
            {
                "severity": "REVIEW",
                "message": "reader_value_review:multi_axis_reader_weakness",
            },
            {
                "severity": "REVIEW",
                "message": "reader_value_review:non_engineer_access_failure",
            },
        ]

        retry, reason = pipeline.should_attempt_dynamic_retry(rows, None, "new")
        self.assertTrue(retry)
        self.assertEqual(reason, "base_retry")

        instruction, _sections = pipeline.build_dynamic_retry_instruction(rows)
        self.assertIn("Decision整合修正", instruction)
        self.assertIn("Reader Value修正", instruction)
        self.assertIn("非専門読者", instruction)
        self.assertIn("新しい比喩事実・使用経験・因果・数値は追加しない", instruction)


class Run273PrivateDraftAutoflowTests(unittest.TestCase):
    def test_ready_sync_manual_route_can_chain_to_private_draft(self) -> None:
        source = READY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("create_private_draft:", source)
        self.assertIn("default: true", source)
        self.assertIn("github.event_name == 'workflow_dispatch'", source)
        self.assertIn("inputs.create_private_draft == true", source)
        self.assertIn("gh workflow run note-create-draft.yml --ref main", source)
        self.assertIn("confirm=CREATE_NOTE_DRAFT", source)
        self.assertIn("prepare_only=false", source)

    def test_push_policy_reconciliation_cannot_enter_private_draft_dispatch_step(self) -> None:
        source = READY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("push:\n", source)
        dispatch_step = source.index("- name: Dispatch private note draft flow after explicit Ready sync")
        condition = source.index("if: ${{ github.event_name == 'workflow_dispatch'", dispatch_step)
        command = source.index("gh workflow run note-create-draft.yml", condition)
        self.assertLess(dispatch_step, condition)
        self.assertLess(condition, command)
        self.assertNotIn("workflow_run:", source)

    def test_target_workflow_keeps_zero_vm_preflight_and_human_only_publication_boundary(self) -> None:
        source = DRAFT_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Validate exact publish-safe candidate before any VM start", source)
        self.assertIn("needs.preflight.outputs.should_start_vm == 'true'", source)
        self.assertIn("Create one private note draft", source)
        self.assertIn("NOTE_DRAFT_CONFIRM", source)
        self.assertNotIn("public release", source.lower().replace("no public release", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
