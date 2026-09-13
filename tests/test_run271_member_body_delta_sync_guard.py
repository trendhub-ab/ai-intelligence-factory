from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
import unittest

import run271_member_body_delta_sync_guard as guard


class MemberBodyDeltaSyncGuardTests(unittest.TestCase):
    def _copy_contract(self, root: Path) -> None:
        for relative in (guard.BODY, guard.CHECKPOINT, guard.WORKFLOW, guard.SUBSCRIBER_WORKFLOW):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(guard.ROOT / relative, target)

    def test_current_repository_contract_passes(self):
        self.assertEqual([], guard.collect_errors(guard.ROOT))

    def test_missing_full_fallback_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            checkpoint = root / guard.CHECKPOINT
            checkpoint.write_text(
                checkpoint.read_text(encoding="utf-8").replace('"fallback_if_missing": "full_scan"', '"fallback_if_missing": "skip"', 1),
                encoding="utf-8",
            )
            self.assertIn('checkpoint_missing:"fallback_if_missing": "full_scan"', guard.collect_errors(root))

    def test_missing_sentinel_fallback_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            body = root / guard.BODY
            body.write_text(body.read_text(encoding="utf-8").replace("def _sentinel_requires_full", "def _sentinel_removed", 1), encoding="utf-8")
            self.assertIn("member_body_missing:def _sentinel_requires_full", guard.collect_errors(root))

    def test_retry_must_force_full_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            workflow = root / guard.WORKFLOW
            workflow.write_text(workflow.read_text(encoding="utf-8").replace("github.run_attempt > 1", "github.run_attempt > 99", 1), encoding="utf-8")
            self.assertIn("member_workflow_missing:github.run_attempt > 1", guard.collect_errors(root))

    def test_member_database_creation_must_remain_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            workflow = root / guard.WORKFLOW
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace("MEMBER_PRESENTATION_ALLOW_CREATE: 'false'", "MEMBER_PRESENTATION_ALLOW_CREATE: 'true'", 1),
                encoding="utf-8",
            )
            self.assertIn(
                "member_destination_missing:MEMBER_PRESENTATION_ALLOW_CREATE: 'false'",
                guard.collect_errors(root),
            )

    def test_member_sync_must_remain_zero_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            workflow = root / guard.WORKFLOW
            workflow.write_text(workflow.read_text(encoding="utf-8") + "\n# GEMINI_API_KEY\n", encoding="utf-8")
            self.assertIn("member_execution_forbidden:GEMINI_API_KEY", guard.collect_errors(root))

    def test_inventory_plan_must_not_fan_out_into_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            workflow = root / guard.SUBSCRIBER_WORKFLOW
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "contains(github.event.workflow_run.display_title, '[apply]')",
                    "true",
                    1,
                ),
                encoding="utf-8",
            )
            self.assertIn(
                "subscriber_execution_missing:contains(github.event.workflow_run.display_title, '[apply]')",
                guard.collect_errors(root),
            )

    def test_member_presentation_must_not_race_inventory_directly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            workflow = root / guard.WORKFLOW
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "- Subscriber Decision Brief Sync",
                    "- Subscriber Decision Brief Sync\n      - Subscriber Inventory Bootstrap",
                    1,
                ),
                encoding="utf-8",
            )
            self.assertIn(
                "member_execution_forbidden_direct_trigger:Subscriber Inventory Bootstrap",
                guard.collect_errors(root),
            )

    def test_subscriber_sync_must_not_passively_subscribe_to_one_shot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            workflow = root / guard.SUBSCRIBER_WORKFLOW
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "- Subscriber Inventory Bootstrap",
                    "- Subscriber Inventory Bootstrap\n      - Daily Intelligence & Content Pipeline [ONE-SHOT]",
                    1,
                ),
                encoding="utf-8",
            )
            self.assertIn(
                "subscriber_execution_forbidden:Daily Intelligence & Content Pipeline [ONE-SHOT]",
                guard.collect_errors(root),
            )


if __name__ == "__main__":
    unittest.main()
