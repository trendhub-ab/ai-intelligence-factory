from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "docs/archive/repository-cleanup-2026-09-02"


class Run201RepositoryGarbageCleanupTests(unittest.TestCase):
    def test_generated_preview_and_inventory_placeholder_are_not_source(self) -> None:
        self.assertFalse((ROOT / "docs/archive/EYECATCH_FINAL_PREVIEW_81.png").exists())
        self.assertFalse((ROOT / "inventory_bootstrap_artifacts/README.md").exists())
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("inventory_bootstrap_artifacts/", gitignore)
        self.assertNotIn("!inventory_bootstrap_artifacts/README.md", gitignore)

    def test_completed_migration_workflows_are_retired_but_preserved(self) -> None:
        active = ROOT / ".github/workflows"
        retired = ARCHIVE / "retired-workflows"
        names = [
            "decision-intelligence-migration.yml",
            "japanese-display-label-migration.yml",
        ]
        for name in names:
            self.assertFalse((active / name).exists(), name)
            self.assertTrue((retired / name).is_file(), name)

    def test_phase1_operator_guide_is_archived_not_root_canonical(self) -> None:
        self.assertFalse((ROOT / "DECISION_INTELLIGENCE_SETUP.md").exists())
        self.assertTrue(
            (
                ARCHIVE
                / "legacy-operator-docs/DECISION_INTELLIGENCE_SETUP_PHASE1_2026-08-21.md"
            ).is_file()
        )

    def test_external_review_workflow_has_no_stale_default(self) -> None:
        workflow = (ROOT / ".github/workflows/external-review-import.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("input_path:", workflow)
        self.assertIn("required: true", workflow)
        self.assertNotIn("external_reviews/run153_backfill.json", workflow)

    def test_historical_external_review_inputs_are_out_of_active_root(self) -> None:
        self.assertFalse((ROOT / "external_reviews").exists())
        self.assertFalse((ROOT / "run156_targets.json").exists())
        archived = ARCHIVE / "external-review-history"
        expected = [
            "run156_targets.json",
            "run156_pilot.json",
            "run156_remaining68.json",
            "run156_whisper_fix.json",
            "run164_batch1.json",
            "run164_batch12.json",
            "run164_batch12_fix8.json",
        ]
        missing = [name for name in expected if not (archived / name).is_file()]
        self.assertEqual([], missing)

    def test_one_time_run153_catalog_generator_is_retired(self) -> None:
        self.assertFalse((ROOT / "run153_backfill_catalog.py").exists())
        self.assertFalse((ROOT / "tests/test_run153_backfill_catalog.py").exists())
        self.assertTrue((ARCHIVE / "retired-tools/run153_backfill_catalog.py").is_file())
        self.assertTrue(
            (ARCHIVE / "retired-tests/test_run153_backfill_catalog.py").is_file()
        )

    def test_protected_runtime_surfaces_still_exist(self) -> None:
        protected = [
            "pipeline.py",
            "production_pipeline.py",
            "decision_intelligence.py",
            "note_draft_automation.py",
            "run172_production_reliability.py",
            "run183_eyecatch_emphasis_scale.py",
            "run194_publication_contract.py",
            "run199_note_vm_preflight.py",
            ".runtime",
            "observed_history",
            "source_roi_history",
            "deferred_deep_dive",
            "eyecatch_images",
            "assets",
        ]
        missing = [name for name in protected if not (ROOT / name).exists()]
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
