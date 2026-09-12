import unittest
from types import SimpleNamespace
from unittest.mock import patch

import decision_intelligence as di


class DecisionCommentPreservationTests(unittest.TestCase):
    def _existing_page(self):
        return {
            "id": "page-1",
            "properties": {
                di.TECH_PROP_MAIN_RISK: di._rt("既存の主リスク"),
                di.TECH_PROP_BEST_FOR: di._rt(""),
                di.TECH_PROP_AVOID_FOR: di._rt("既存の向いていない用途"),
                di.TECH_PROP_SHORT_RATIONALE: di._rt("既存の判断理由"),
            },
        }

    def test_wrapper_preserves_non_empty_and_allows_owned_blank_fill(self):
        assessment = {
            "main_risk": "新しい主リスク候補",
            "best_for": "新しい向いている用途候補",
            "avoid_for": "新しい向いていない用途候補",
            "short_rationale": "新しい判断理由候補",
        }
        resolution = SimpleNamespace(status="RESOLVED", entity_id="entity-1")
        captured = {}

        def fake_core(protected_assessment, _resolution):
            captured.update(protected_assessment)
            return {"saved": True}

        with (
            patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True),
            patch.object(di, "get_technology_record_by_entity_id", return_value=self._existing_page()),
            patch.object(di, "_RUN257_UPSERT_TECHNOLOGY_INTELLIGENCE_CORE", side_effect=fake_core),
        ):
            result = di.upsert_technology_intelligence(assessment, resolution)

        self.assertEqual({"saved": True}, result)
        self.assertEqual("既存の主リスク", captured["main_risk"])
        self.assertEqual("新しい向いている用途候補", captured["best_for"])
        self.assertEqual("既存の向いていない用途", captured["avoid_for"])
        self.assertEqual("既存の判断理由", captured["short_rationale"])
        self.assertEqual("新しい主リスク候補", assessment["main_risk"])

    def test_new_record_passes_candidates_through_without_network_write(self):
        assessment = {
            "main_risk": "risk",
            "best_for": "best",
            "avoid_for": "avoid",
            "short_rationale": "reason",
        }
        resolution = SimpleNamespace(status="RESOLVED", entity_id="entity-new")

        with (
            patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True),
            patch.object(di, "get_technology_record_by_entity_id", return_value=None),
            patch.object(
                di,
                "_RUN257_UPSERT_TECHNOLOGY_INTELLIGENCE_CORE",
                side_effect=lambda protected, _resolution: protected,
            ),
        ):
            result = di.upsert_technology_intelligence(assessment, resolution)

        self.assertEqual(assessment, result)

    def test_disabled_path_does_not_add_guard_lookup(self):
        resolution = SimpleNamespace(status="RESOLVED", entity_id="entity-disabled")
        with (
            patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", False),
            patch.object(di, "get_technology_record_by_entity_id") as lookup,
            patch.object(
                di,
                "_RUN257_UPSERT_TECHNOLOGY_INTELLIGENCE_CORE",
                return_value={"enabled": False},
            ) as core,
        ):
            result = di.upsert_technology_intelligence({}, resolution)

        self.assertEqual({"enabled": False}, result)
        lookup.assert_not_called()
        core.assert_called_once()


if __name__ == "__main__":
    unittest.main()
