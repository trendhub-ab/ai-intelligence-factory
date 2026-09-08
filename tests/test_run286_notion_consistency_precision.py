from __future__ import annotations

import types
import unittest
from pathlib import Path

import run286_notion_consistency_precision as run286

ROOT = Path(__file__).resolve().parents[1]
CURRENT_RECOVERY = ROOT / "current_policy_ready_recovery.py"
RECOVERY_WORKFLOW = ROOT / ".github" / "workflows" / "current-policy-ready-recovery.yml"


class _Logger:
    def __init__(self):
        self.rows = []

    def info(self, *args, **kwargs):
        self.rows.append(args)


class Run286LiveStatusGuardTests(unittest.TestCase):
    def _fixture(self, live_status="Ready", selected=None):
        selected = selected if selected is not None else [{"notion_page_id": "page-1", "repo": {"nameWithOwner": "x/y"}}]
        calls = {"select": 0, "status": 0}

        def select(pipeline, limit=1, scan_limit=100):
            calls["select"] += 1
            return selected

        def read_status(pipeline, page_id):
            calls["status"] += 1
            self.assertEqual(page_id, "page-1")
            return live_status

        recovery = types.SimpleNamespace(
            select_stale_ready_items=select,
            _read_article_status=read_status,
        )
        pipeline = types.SimpleNamespace(ARTICLE_STATUS_READY="Ready", logger=_Logger())
        return recovery, pipeline, calls

    def test_ready_direct_read_preserves_selected_candidate(self):
        recovery, pipeline, calls = self._fixture("Ready")
        run286.install_recovery_live_status_guard(recovery)
        result = recovery.select_stale_ready_items(pipeline, limit=1, scan_limit=100)
        self.assertEqual([row["notion_page_id"] for row in result], ["page-1"])
        self.assertEqual(calls, {"select": 1, "status": 1})

    def test_stale_query_pending_retry_is_skipped_before_model_lane(self):
        recovery, pipeline, calls = self._fixture("Pending Retry")
        run286.install_recovery_live_status_guard(recovery)
        self.assertEqual(recovery.select_stale_ready_items(pipeline), [])
        self.assertEqual(calls, {"select": 1, "status": 1})
        self.assertTrue(any("RUN286 RECOVERY LIVE STATUS SKIP" in row[0] for row in pipeline.logger.rows))

    def test_failed_or_empty_direct_read_fails_closed(self):
        for live_status in (None, ""):
            with self.subTest(live_status=live_status):
                recovery, pipeline, calls = self._fixture(live_status)
                run286.install_recovery_live_status_guard(recovery)
                self.assertEqual(recovery.select_stale_ready_items(pipeline), [])
                self.assertEqual(calls["status"], 1)

    def test_no_selected_candidate_adds_no_direct_status_read(self):
        recovery, pipeline, calls = self._fixture("Ready", selected=[])
        run286.install_recovery_live_status_guard(recovery)
        self.assertEqual(recovery.select_stale_ready_items(pipeline), [])
        self.assertEqual(calls, {"select": 1, "status": 0})

    def test_install_is_idempotent(self):
        recovery, pipeline, calls = self._fixture("Ready")
        run286.install_recovery_live_status_guard(recovery)
        wrapped = recovery.select_stale_ready_items
        run286.install_recovery_live_status_guard(recovery)
        self.assertIs(wrapped, recovery.select_stale_ready_items)
        recovery.select_stale_ready_items(pipeline)
        self.assertEqual(calls, {"select": 1, "status": 1})

    def test_pure_filter_performs_no_io_beyond_supplied_status_reader(self):
        calls = []
        pipeline = types.SimpleNamespace(ARTICLE_STATUS_READY="Ready", logger=_Logger())
        items = [{"notion_page_id": "page-1"}]
        result = run286.filter_live_ready_items(
            pipeline,
            items,
            lambda page_id: calls.append(page_id) or "Ready",
        )
        self.assertEqual(result, items)
        self.assertEqual(calls, ["page-1"])


class Run286RepositoryContractTests(unittest.TestCase):
    def test_recovery_controller_filters_live_status_before_generator(self):
        text = CURRENT_RECOVERY.read_text(encoding="utf-8")
        self.assertIn("ENABLE_RUN286_NOTION_LIVE_STATUS_GUARD", text)
        guard_at = text.index("items = filter_live_ready_items")
        model_at = text.index("generated = pipeline.generate_intelligence_report")
        self.assertLess(guard_at, model_at)

    def test_recovery_workflow_tests_run286_before_model_path_and_stabilizes_notion_read(self):
        text = RECOVERY_WORKFLOW.read_text(encoding="utf-8")
        test_at = text.index("tests.test_run286_notion_consistency_precision")
        model_at = text.index("run: python production_pipeline.py")
        self.assertLess(test_at, model_at)
        self.assertIn("ENABLE_RUN286_NOTION_LIVE_STATUS_GUARD: 'true'", text)
        self.assertIn("time.sleep(2)", text)
        self.assertIn("RUN286_NOTION_CONSISTENCY_PROBE", text)
        self.assertIn("python note_ready_sync.py | tee /tmp/run282-note-ready.txt", text)
        self.assertNotIn("note-create-draft.yml", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
