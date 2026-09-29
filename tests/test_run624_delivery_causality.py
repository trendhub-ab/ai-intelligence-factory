from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path

import note_ready_sync


ROOT = Path(__file__).resolve().parents[1]
ONE_SHOT = ROOT / ".github" / "workflows" / "daily-one-shot.yml"
NOTE_READY = ROOT / ".github" / "workflows" / "note-ready-sync.yml"


class Run624DeliveryCausalityTests(unittest.TestCase):
    def _gate_history(self, root: Path, candidates: list[dict]) -> Path:
        path = root / "deep_dive_gate_history.json"
        path.write_text(
            json.dumps(
                {
                    "generated_at": "2026-09-28T15:52:22+09:00",
                    "funnel": {"ready_count": sum(1 for row in candidates if row.get("final_status") == "Ready")},
                    "candidates": candidates,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def test_full_mode_must_gate_and_pin_private_draft_to_current_run_candidate(self) -> None:
        source = ONE_SHOT.read_text(encoding="utf-8")
        self.assertIn("run624_delivery_causality.py", source)
        self.assertIn('dispatch_all_current_run_ready "$ready_count" "$create_private_draft"', source)
        self.assertIn('target_sync_ids_b64', source)
        self.assertIn('for target_sync_id in "${target_sync_ids[@]}"', source)
        self.assertIn('-f target_sync_id="$target_sync_id"', source)

    def test_note_ready_workflow_accepts_exact_sync_id_before_preflight(self) -> None:
        source = NOTE_READY.read_text(encoding="utf-8")
        self.assertIn("target_sync_id:", source)
        self.assertIn("TARGET_SYNC_ID", source)
        self.assertIn("steps.sync.outputs.resolved_sync_id", source)

    def test_zero_ready_disables_private_draft_but_keeps_reconciliation(self) -> None:
        mod = importlib.import_module("run624_delivery_causality")
        with tempfile.TemporaryDirectory() as td:
            path = self._gate_history(
                Path(td),
                [{
                    "candidate_rank": 1,
                    "name": "a",
                    "url": "https://example.com/a",
                    "final_status": "Pending Retry",
                    "article_saved": False,
                }],
            )
            decision = mod.delivery_decision(path)
        self.assertEqual(decision["ready_count"], 0)
        self.assertFalse(decision["create_private_draft"])
        self.assertTrue(decision["run_note_reconciliation"])
        self.assertEqual(decision["target_sync_id"], "")
        self.assertEqual(decision["target_sync_ids"], [])
        self.assertEqual(decision["target_source_url"], "")
        self.assertEqual(decision["target_source_urls"], [])

    def test_current_run_ready_pins_lowest_rank_ready_source_url(self) -> None:
        mod = importlib.import_module("run624_delivery_causality")
        with tempfile.TemporaryDirectory() as td:
            path = self._gate_history(
                Path(td),
                [
                    {
                        "candidate_rank": 4,
                        "name": "later",
                        "url": "https://example.com/later",
                        "sync_id": "b" * 32,
                        "final_status": "Ready",
                        "article_saved": True,
                    },
                    {
                        "candidate_rank": 2,
                        "name": "first-ready",
                        "url": "https://example.com/first-ready",
                        "sync_id": "a" * 32,
                        "final_status": "Ready",
                        "article_saved": True,
                    },
                    {
                        "candidate_rank": 1,
                        "name": "failed",
                        "url": "https://example.com/failed",
                        "final_status": "Pending Retry",
                        "article_saved": False,
                    },
                ],
            )
            decision = mod.delivery_decision(path)
        self.assertEqual(decision["ready_count"], 2)
        self.assertTrue(decision["create_private_draft"])
        self.assertEqual(decision["target_sync_id"], "a" * 32)
        self.assertEqual(decision["target_sync_ids"], ["a" * 32, "b" * 32])
        self.assertEqual(decision["target_source_url"], "https://example.com/first-ready")
        self.assertEqual(
            decision["target_source_urls"],
            ["https://example.com/first-ready", "https://example.com/later"],
        )

    def test_missing_or_invalid_gate_history_fails_closed_for_draft(self) -> None:
        mod = importlib.import_module("run624_delivery_causality")
        with tempfile.TemporaryDirectory() as td:
            missing = mod.delivery_decision(Path(td) / "missing.json")
            broken_path = Path(td) / "broken.json"
            broken_path.write_text("{", encoding="utf-8")
            broken = mod.delivery_decision(broken_path)
        for decision in (missing, broken):
            self.assertFalse(decision["create_private_draft"])
            self.assertTrue(decision["run_note_reconciliation"])
            self.assertEqual(decision["target_sync_id"], "")
            self.assertEqual(decision["target_sync_ids"], [])
            self.assertEqual(decision["target_source_url"], "")
            self.assertEqual(decision["target_source_urls"], [])
            self.assertFalse(decision["audit_valid"])

    def test_github_output_carries_all_ready_ids_and_urls_losslessly(self) -> None:
        import base64

        mod = importlib.import_module("run624_delivery_causality")
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "out"
            result = {
                "audit_valid": True,
                "ready_count": 2,
                "create_private_draft": True,
                "target_sync_id": "a" * 32,
                "target_sync_ids": ["a" * 32, "b" * 32],
                "target_source_url": "https://example.com/a?x=1,2",
                "target_source_urls": [
                    "https://example.com/a?x=1,2",
                    "https://example.com/b#frag",
                ],
            }
            mod._write_github_output(str(output), result)
            values = dict(
                line.split("=", 1)
                for line in output.read_text(encoding="utf-8").splitlines()
                if "=" in line
            )
            decoded_ids = json.loads(base64.b64decode(values["target_sync_ids_b64"]).decode("utf-8"))
            decoded_urls = json.loads(base64.b64decode(values["target_source_urls_b64"]).decode("utf-8"))
        self.assertEqual(decoded_ids, result["target_sync_ids"])
        self.assertEqual(decoded_urls, result["target_source_urls"])

    def test_ready_without_persisted_sync_id_fails_closed(self) -> None:
        mod = importlib.import_module("run624_delivery_causality")
        with tempfile.TemporaryDirectory() as td:
            path = self._gate_history(
                Path(td),
                [{
                    "candidate_rank": 1,
                    "name": "ready-but-unbound",
                    "url": "https://example.com/a",
                    "final_status": "Ready",
                    "article_saved": True,
                }],
            )
            decision = mod.delivery_decision(path)
        self.assertFalse(decision["audit_valid"])
        self.assertFalse(decision["create_private_draft"])
        self.assertIn("persisted sync_id", decision["reason"])

    def test_source_url_resolution_is_exact_and_ambiguous_matches_fail_closed(self) -> None:
        states = [
            {"sync_id": "a" * 32, "original_url": "https://example.com/a", "primary_url": "https://vendor.example/a"},
            {"sync_id": "b" * 32, "original_url": "https://example.com/b", "primary_url": "https://vendor.example/b"},
        ]
        self.assertEqual(
            note_ready_sync.select_exact_sync_id_for_source_url(states, "https://example.com/b"),
            "b" * 32,
        )
        with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
            note_ready_sync.select_exact_sync_id_for_source_url(states, "https://example.com/missing")
        with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
            note_ready_sync.select_exact_sync_id_for_source_url(
                states + [{"sync_id": "c" * 32, "original_url": "https://example.com/b", "primary_url": ""}],
                "https://example.com/b",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
