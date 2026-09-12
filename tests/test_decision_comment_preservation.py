import unittest
from types import SimpleNamespace

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

    def _assessment(self):
        return {
            "technology_name": "Example",
            "adoption_score": 70,
            "adoption_status": "TEST",
            "evidence_confidence": "HIGH",
            "production_readiness": "MEDIUM",
            "main_risk": "新しい主リスク候補",
            "best_for": "新しい向いている用途候補",
            "avoid_for": "新しい向いていない用途候補",
            "short_rationale": "新しい判断理由候補",
            "sources": [],
            "evidence_urls": [],
        }

    def _resolution(self):
        return SimpleNamespace(
            entity_id="entity-1",
            status="RESOLVED",
            primary_url="https://example.com",
            aliases=(),
        )

    def test_current_state_carries_all_protected_comment_fields_from_same_page(self):
        current = di._current_state(self._existing_page())
        self.assertEqual("既存の主リスク", current["main_risk"])
        self.assertEqual("", current["best_for"])
        self.assertEqual("既存の向いていない用途", current["avoid_for"])
        self.assertEqual("既存の判断理由", current["short_rationale"])

    def test_property_builder_preserves_non_empty_and_allows_owned_blank_fill(self):
        assessment = self._assessment()
        original = dict(assessment)
        current = di._current_state(self._existing_page())

        props = di._build_technology_properties(assessment, self._resolution(), current)

        self.assertEqual("既存の主リスク", di._rich_text_value(props[di.TECH_PROP_MAIN_RISK]))
        self.assertEqual("新しい向いている用途候補", di._rich_text_value(props[di.TECH_PROP_BEST_FOR]))
        self.assertEqual("既存の向いていない用途", di._rich_text_value(props[di.TECH_PROP_AVOID_FOR]))
        self.assertEqual("既存の判断理由", di._rich_text_value(props[di.TECH_PROP_SHORT_RATIONALE]))
        self.assertEqual(original, assessment)

    def test_new_record_passes_all_candidates_through(self):
        assessment = self._assessment()
        props = di._build_technology_properties(assessment, self._resolution(), {})

        self.assertEqual("新しい主リスク候補", di._rich_text_value(props[di.TECH_PROP_MAIN_RISK]))
        self.assertEqual("新しい向いている用途候補", di._rich_text_value(props[di.TECH_PROP_BEST_FOR]))
        self.assertEqual("新しい向いていない用途候補", di._rich_text_value(props[di.TECH_PROP_AVOID_FOR]))
        self.assertEqual("新しい判断理由候補", di._rich_text_value(props[di.TECH_PROP_SHORT_RATIONALE]))

    def test_protection_helper_never_requires_a_notion_lookup(self):
        assessment = self._assessment()
        current = {
            "main_risk": "既存risk",
            "best_for": "",
            "avoid_for": "既存avoid",
            "short_rationale": "既存reason",
        }
        protected = di._run257_protect_comment_fields(assessment, current)
        self.assertEqual("既存risk", protected["main_risk"])
        self.assertEqual("新しい向いている用途候補", protected["best_for"])
        self.assertEqual("既存avoid", protected["avoid_for"])
        self.assertEqual("既存reason", protected["short_rationale"])


if __name__ == "__main__":
    unittest.main()
