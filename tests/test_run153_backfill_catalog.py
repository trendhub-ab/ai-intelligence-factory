import unittest
from collections import Counter

import pipeline
import run153_backfill_catalog as catalog


class Run153BackfillCatalogTests(unittest.TestCase):
    def test_catalog_has_expected_size_and_primary_mix(self):
        rows = catalog.build_rows()
        self.assertEqual(len(rows), 94)
        first = rows[:74]
        self.assertEqual(
            Counter(row["review"]["category"] for row in first),
            Counter({
                "MODEL": 12,
                "AGENT": 18,
                "PRODUCT": 14,
                "INFRA": 19,
                "MULTIMODAL": 11,
            }),
        )

    def test_every_row_uses_explicit_github_identity(self):
        rows = catalog.build_rows()
        names = set()
        urls = set()
        for row in rows:
            self.assertEqual(row["source"], "GitHub")
            self.assertRegex(row["name"], r"^[^/\s]+/[^/\s]+$")
            self.assertEqual(row["url"], f"https://github.com/{row['name']}")
            self.assertEqual(row["primary_url"], row["url"])
            self.assertNotIn(row["name"].lower(), names)
            self.assertNotIn(row["url"].lower(), urls)
            names.add(row["name"].lower())
            urls.add(row["url"].lower())

    def test_every_review_passes_exact_production_schema_validator(self):
        for row in catalog.build_rows():
            parsed = pipeline._parse_product_review_response(row["review"])
            self.assertEqual(parsed["category"], row["review"]["category"])
            self.assertEqual(parsed["adoption_score"], row["review"]["adoption_score"])

    def test_score_is_exact_component_sum(self):
        for row in catalog.build_rows():
            review = row["review"]
            self.assertEqual(review["adoption_score"], sum(review["components"].values()))

    def test_adopt_never_violates_high_high_rule(self):
        for row in catalog.build_rows():
            review = row["review"]
            if review["adoption_status"] == "ADOPT":
                self.assertEqual(review["evidence_confidence"], "HIGH")
                self.assertEqual(review["production_readiness"], "HIGH")

    def test_no_catalog_generation_needs_provider_call(self):
        with self.subTest("catalog is deterministic local data"):
            rows1 = catalog.build_rows()
            rows2 = catalog.build_rows()
            self.assertEqual(rows1, rows2)
            self.assertGreater(len(rows1), 74)


if __name__ == "__main__":
    unittest.main()
