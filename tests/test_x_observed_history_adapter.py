import json
import tempfile
import unittest
from pathlib import Path

from x_intelligence import (
    build_x_post,
    find_latest_screening_snapshot,
    generate_from_latest_observed_history,
    select_x_candidates,
)


class XObservedHistoryAdapterTests(unittest.TestCase):
    def _snapshot_item(self, **overrides):
        item = {
            "id": "B0059",
            "source": "HackerNews",
            "name": "GPT 5.6 Sol 20% price reduction",
            "url": "https://example.com/official",
            "engagement": 65,
            "final_screening_score": 75,
            "commercial_value_score": 85,
            "screening_reason": "最新フロンティアモデルの価格改定に関する速報。",
            "stock_eligible": True,
        }
        item.update(overrides)
        return item

    def test_factory_screening_snapshot_fields_are_native_inputs(self):
        selected = select_x_candidates([self._snapshot_item()])
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["x_screening_score"], 75)
        self.assertGreater(selected[0]["x_candidate_score"], 0)
        draft = build_x_post(selected[0])
        self.assertIn("一次情報（HN）", draft["post"])
        self.assertIn("価格改定", draft["post"])
        self.assertEqual(draft["gemini_calls"], 0)
        self.assertEqual(draft["x_api_calls"], 0)

    def test_latest_snapshot_is_selected_by_factory_timestamp_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "screening_20260822T010000Z.json").write_text("{}", encoding="utf-8")
            latest = directory / "screening_20260822T020000Z.json"
            latest.write_text("{}", encoding="utf-8")
            self.assertEqual(find_latest_screening_snapshot(directory), latest)

    def test_generate_from_latest_observed_history_is_zero_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = root / "observed_history"
            output = root / "pending"
            history.mkdir()
            snapshot = history / "screening_20260822T083036Z.json"
            snapshot.write_text(json.dumps({"run_id": "test", "items": [self._snapshot_item()]}, ensure_ascii=False), encoding="utf-8")
            manifest = generate_from_latest_observed_history(observed_history_dir=history, output_dir=output)
            self.assertEqual(manifest["generated_candidates"], 1)
            self.assertEqual(manifest["free_drafts"], 1)
            self.assertEqual(manifest["generated_drafts"], 4)
            self.assertEqual(manifest["legacy_variants_per_candidate"], 3)
            self.assertEqual(manifest["input_path"], str(snapshot))
            self.assertEqual(manifest["gemini_calls"], 0)
            self.assertEqual(manifest["x_api_calls"], 0)
            self.assertFalse(manifest["auto_posted"])
            self.assertEqual(manifest["candidates"][0]["free_draft"]["composition_mode"], "free_history_aware_zero_api")
            self.assertTrue((output / "manifest.json").exists())
            self.assertEqual(len(list(output.glob("*-COMPARE.md"))), 1)


if __name__ == "__main__":
    unittest.main()
