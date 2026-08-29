"""Run165 supersedes Run161's presentation-only contract.

Internal Notion databases now use Japanese physical property names as the
production write contract.  Existing Japanese formula/display aliases remain
presentation helpers and must not collide with the physical backend fields.
"""

import unittest

import decision_intelligence as di


class Run165InternalDbJapaneseSchemaContractTests(unittest.TestCase):
    def test_backend_contract_uses_japanese_physical_properties(self):
        expected = {
            "技術・プロジェクト名",
            "採用スコア（内部）",
            "採用判断（内部）",
            "根拠信頼度（内部）",
            "実用準備度（内部）",
            "主リスク（内部）",
            "向いている用途（内部）",
            "向いていない用途（内部）",
            "判断理由（内部）",
            "分野（内部）",
            "初回発見日（内部）",
            "最終レビュー日（内部）",
            "スコア変化",
            "公式URL",
            "関連記事（内部）",
            "一次情報URL（内部）",
        }
        self.assertTrue(expected.issubset(di.TECH_REQUIRED_PROPERTY_TYPES))

    def test_old_english_canonical_names_are_no_longer_required(self):
        old_english = {
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
        self.assertTrue(old_english.isdisjoint(di.TECH_REQUIRED_PROPERTY_TYPES))

    def test_display_aliases_remain_distinct_from_backend_fields(self):
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
