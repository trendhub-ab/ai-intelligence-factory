import json
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from x_discovery.stock_deep_dive_handoff import StockHandoffError, run


ROOT = Path("x_discovery")
def load(path): return json.loads((ROOT / path).read_text())


class HandoffTests(unittest.TestCase):
    def test_real_persisted_stock_enters_selector_without_generation(self):
        calls = []
        def select(items):
            calls.append(items)
            return [row for row in items if row["score"] >= 60 and row.get("notion_page_id")]
        result = run(NS(_select_stocked_deep_dive_candidates=select),
                     load("fixtures/defense_factory_boundary_20260911.json"),
                     load("observations/defense_factory_calibration_20260911.json"),
                     load("observations/defense_factory_stock_20260911.json"))
        self.assertEqual(result["status"], "DEEP_DIVE_SELECTION_READY")
        self.assertTrue(result["deep_dive_selected"])
        self.assertEqual(result["model_calls"], 0)
        self.assertFalse(result["generation_executed"])
        self.assertEqual(len(calls), 1)

    def test_missing_persistence_fails_closed(self):
        stock = load("observations/defense_factory_stock_20260911.json")
        stock["notion_page_id"] = None
        with self.assertRaises(StockHandoffError):
            run(NS(_select_stocked_deep_dive_candidates=lambda items: items),
                load("fixtures/defense_factory_boundary_20260911.json"),
                load("observations/defense_factory_calibration_20260911.json"), stock)


if __name__ == "__main__": unittest.main()
