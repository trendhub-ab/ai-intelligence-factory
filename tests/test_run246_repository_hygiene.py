from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "docs" / "archive" / "repository-cleanup-2026-09-05"


class Run246RepositoryHygieneTests(unittest.TestCase):
    def test_verified_garbage_is_not_active(self):
        self.assertFalse((ROOT / ".github" / "workflows" / "run130-portfolio-test.yml").exists())

    def test_retired_workflow_is_preserved_in_archive(self):
        path = ARCHIVE / "retired-workflows" / "run130-portfolio-test.yml"
        self.assertTrue(path.is_file())
        self.assertGreater(path.stat().st_size, 20)

    def test_portfolio_regression_coverage_survives_workflow_retirement(self):
        workflow = (ROOT / ".github" / "workflows" / "integration-reconciliation-ci.yml").read_text(encoding="utf-8")
        self.assertIn("test_run131_profit_aligned_portfolio.py", workflow)
        self.assertIn("test_run132_context_first_decision_intelligence.py", workflow)
        self.assertIn("test_inventory_bootstrap.py", workflow)
        self.assertIn("Run full pytest regression", workflow)
        self.assertIn("Run synthetic smoke through current production stack", workflow)

    def test_migration_tools_rejected_by_full_regression_remain_active(self):
        self.assertTrue((ROOT / "migrate_decision_intelligence.py").is_file())
        self.assertTrue((ROOT / "migrate_japanese_display_label.py").is_file())
        decision_test = (ROOT / "tests" / "test_decision_intelligence.py").read_text(encoding="utf-8")
        label_test = (ROOT / "tests" / "test_run120_japanese_display_label.py").read_text(encoding="utf-8")
        self.assertIn("import migrate_decision_intelligence as migration", decision_test)
        self.assertIn("migrate_japanese_display_label as migration", label_test)

    def test_current_policy_and_operator_surfaces_are_not_misclassified_as_garbage(self):
        protected = (
            "run156_decision_review_import.py",
            "run164_ai_relevance_calibration.py",
            "portfolio_inventory_bootstrap.py",
            "migrate_decision_intelligence.py",
            "migrate_japanese_display_label.py",
            ".github/workflows/inventory-bootstrap.yml",
            ".github/workflows/regression.yml",
            ".github/workflows/regression-test.yml",
            "run235_stage3b_source_normalization_migration.py",
            "run237_product_delivery_maintenance_migration.py",
            "run238_deep_dive_portfolio_migration.py",
            "run239_reader_experience_migration.py",
            "run240_editorial_naturalness_migration.py",
            "run241_batched_modularization_migration.py",
            "run242_notional_source_deferred_migration.py",
            "run243_content_generation_protocol_migration.py",
            "run244_decision_product_protocol_migration.py",
            "run245_fact_validation_migration.py",
            ".runtime",
            "observed_history",
            "source_roi_history",
            "deferred_deep_dive",
            "eyecatch_images",
            "assets",
        )
        for rel in protected:
            with self.subTest(path=rel):
                self.assertTrue((ROOT / rel).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
