from __future__ import annotations

import unittest

from member_body_delta_checkpoint import select_previous_successful_start


class Run2711MemberBodyCheckpointTests(unittest.TestCase):
    def test_selects_newest_successful_main_run(self) -> None:
        payload = {
            "workflow_runs": [
                {
                    "id": 30,
                    "conclusion": "failure",
                    "head_branch": "main",
                    "created_at": "2026-09-07T03:00:00Z",
                    "run_started_at": "2026-09-07T03:00:01Z",
                },
                {
                    "id": 20,
                    "conclusion": "success",
                    "head_branch": "main",
                    "created_at": "2026-09-07T02:00:00Z",
                    "run_started_at": "2026-09-07T02:00:01Z",
                },
                {
                    "id": 10,
                    "conclusion": "success",
                    "head_branch": "main",
                    "created_at": "2026-09-07T01:00:00Z",
                    "run_started_at": "2026-09-07T01:00:01Z",
                },
            ]
        }
        self.assertEqual(
            select_previous_successful_start(payload),
            "2026-09-07T02:00:01Z",
        )

    def test_current_run_and_non_main_are_excluded(self) -> None:
        payload = {
            "workflow_runs": [
                {
                    "id": 20,
                    "conclusion": "success",
                    "head_branch": "main",
                    "created_at": "2026-09-07T02:00:00Z",
                    "run_started_at": "2026-09-07T02:00:01Z",
                },
                {
                    "id": 19,
                    "conclusion": "success",
                    "head_branch": "feature",
                    "created_at": "2026-09-07T01:30:00Z",
                    "run_started_at": "2026-09-07T01:30:01Z",
                },
                {
                    "id": 18,
                    "conclusion": "success",
                    "head_branch": "main",
                    "created_at": "2026-09-07T01:00:00Z",
                    "run_started_at": "2026-09-07T01:00:01Z",
                },
            ]
        }
        self.assertEqual(
            select_previous_successful_start(payload, current_run_id=20),
            "2026-09-07T01:00:01Z",
        )

    def test_no_successful_checkpoint_returns_empty_for_full_fallback(self) -> None:
        payload = {
            "workflow_runs": [
                {
                    "id": 1,
                    "conclusion": "failure",
                    "head_branch": "main",
                    "run_started_at": "2026-09-07T01:00:01Z",
                }
            ]
        }
        self.assertEqual(select_previous_successful_start(payload), "")


if __name__ == "__main__":
    unittest.main()
