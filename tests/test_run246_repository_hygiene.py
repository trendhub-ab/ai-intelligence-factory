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
        workflow = (ROOT / ".github/workflows/integration-reconciliation-ci.yml").read_text(encoding="utf-8")
        self.assertIn("python -m pytest -q tests", workflow)
        self.assertIn("SYNTHETIC_REGRESSION_MODE: 'true'", workflow)
        self.assertIn("run: python production_pipeline.py", workflow)
        # Run267: zero-api-regression is a required main-branch status context, so
        # pull_request path filters are forbidden. Full pytest itself is the coverage
        # authority; a hand-maintained tests/** trigger list is no longer required.
        pull_request_section = workflow.split("  workflow_dispatch:", 1)[0]
        self.assertNotIn("    paths:\n", pull_request_section)
        self.assertNotIn("    paths-ignore:\n", pull_request_section)

        for relative in (
            "tests/test_run131_profit_aligned_portfolio.py",
            "tests/test_run132_context_first_decision_intelligence.py",
            "tests/test_inventory_bootstrap.py",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

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

    def test_retired_provider_and_recovery_surfaces_stay_absent(self):
        retired = (
            ".github/workflows/gemini-technology-comment-shadow-judge-only.yml",
            ".github/workflows/groq-qwen-technology-comment-shadow-judge.yml",
            ".github/workflows/groq-technology-comment-shadow-live.yml",
            "gemini_technology_comment_shadow_judge.py",
            "groq_qwen_technology_comment_shadow_judge.py",
            "groq_technology_comment_shadow_live.py",
            "technology_comment_shadow.py",
            ".github/workflows/run361-byte-preserving-ready-rebase.yml",
            ".github/workflows/run361-gemini-live-validation.yml",
            ".github/workflows/run362-gemini-request-shape-validation.yml",
            ".github/workflows/run362-ready-provenance-audit.yml",
            ".github/workflows/run363-gemini38-temporal-control.yml",
            ".github/workflows/run364-historical-ready-rebase.yml",
            ".github/workflows/run365-historical-ready-rebase.yml",
            "run361_byte_preserving_ready_rebase.py",
            "run361_gemini_live_validation.py",
            "run362_gemini_request_shape_validation.py",
            "run362_gemini_request_shape_validation_test.py",
            "run362_ready_provenance_audit.py",
            "run363_gemini38_temporal_control.py",
            "run363_gemini38_temporal_control_test.py",
            "run364_historical_ready_rebase.py",
            "run365_historical_ready_rebase.py",
        )
        present = [relative for relative in retired if (ROOT / relative).exists()]
        self.assertEqual([], present, f"retired provider/recovery surfaces reappeared: {present}")

    def test_retired_groq_dependency_stays_absent(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        package_names = {
            line.split(";", 1)[0].split("==", 1)[0].split(">=", 1)[0].split("<=", 1)[0].strip().lower()
            for line in requirements
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertNotIn("groq", package_names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
