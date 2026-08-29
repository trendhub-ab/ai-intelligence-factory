"""Run161 regression: internal Notion DB Japanese display is presentation-only.

The production write contract must keep using the existing English properties.
Japanese columns are Notion formula/view aliases and therefore must never become
required write properties or trigger row rewrites / model calls.
"""

import unittest

import decision_intelligence as di


class Run161InternalDbJapaneseDisplayContractTests(unittest.TestCase):
    def test_backend_contract_keeps_canonical_english_properties(self):
        # Only assert fields that are part of the established required schema.
        # Plain Summary / Topic Trigger are enrichment fields and intentionally
        # are not required by TECH_REQUIRED_PROPERTY_TYPES.
        expected = {
            "Technology / Project Name",
            "Adoption Score",
            "Adoption Status",
            "Evidence Confidence",
            "Production Readiness",
            "Main Risk",
            "Best For",
            "Avoid For",
            "Short Rationale",
            "Category",
            "First Seen",
            "Last Reviewed",
            "Score Change",
            "Primary URL",
            "Related Article",
            "Primary Evidence URLs",
        }
        self.assertTrue(expected.issubset(di.TECH_REQUIRED_PROPERTY_TYPES))

    def test_japanese_display_aliases_are_not_required_write_properties(self):
        display_only = {
            "AI・技術名",
            "判断スコア",
            "判断",
            "根拠の確かさ",
            "実用度",
            "主なリスク",
            "向いている用途",
            "向いていない用途",
            "判断理由",
            "分野",
            "これは何？",
            "今回の話題",
            "見つけた日",
            "最終確認日",
            "今月の変化",
            "元情報",
            "関連記事",
            "一次情報",
        }
        self.assertTrue(display_only.isdisjoint(di.TECH_REQUIRED_PROPERTY_TYPES))

    def test_schema_validator_allows_formula_display_extras(self):
        properties = {
            name: {"type": expected_type}
            for name, expected_type in di.TECH_REQUIRED_PROPERTY_TYPES.items()
        }
        properties.update(
            {
                "AI・技術名": {"type": "formula"},
                "判断スコア": {"type": "formula"},
                "判断": {"type": "formula"},
            }
        )
        di._validate_schema(properties, di.TECH_REQUIRED_PROPERTY_TYPES, "Technology Intelligence DB")


if __name__ == "__main__":
    unittest.main()
