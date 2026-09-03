from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Run200RepositoryLayoutTests(unittest.TestCase):
    def test_active_production_runtime_layers_are_preserved(self) -> None:
        production = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        for module in (
            "run203_runtime_state_channel",
            "gemini_timeout_rpd_fail_closed",
            "gemini_transient_recovery",
            "run172_production_reliability",
            "run173_operational_yield",
            "run174_monthly_digest_integrity",
            "run175_semantic_fact_precision",
            "run176_scope_fidelity",
            "run177_paid_funnel_alignment",
            "run178_eyecatch_editorial_layout_optimizer",
            "run179_eyecatch_font_refinement",
            "run180_eyecatch_semantic_layout",
            "run181_eyecatch_visual_balance",
            "run182_eyecatch_conclusion_emphasis",
            "run183_eyecatch_emphasis_scale",
            "reader_value_review_bridge",
            "run208_reader_value_repair",
            "run194_publication_contract",
        ):
            self.assertIn(f"import {module}", production)
            self.assertTrue((ROOT / f"{module}.py").is_file())

    def test_active_note_safety_stack_is_preserved(self) -> None:
        workflow = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
        for module in (
            "run199_note_vm_preflight.py",
            "run194_note_persistent_cloud.py",
            "run194_note_current_contract.py",
            "run194_publication_contract.py",
        ):
            self.assertIn(module, workflow)
            self.assertTrue((ROOT / module).is_file())

    def test_note_workflow_keeps_preflight_vm_gate_and_pinned_sync_id(self) -> None:
        workflow = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
        self.assertIn("preflight:", workflow)
        self.assertIn("needs.preflight.outputs.has_candidate == 'true'", workflow)
        self.assertIn("AIIF_NOTE_TARGET_SYNC_ID", workflow)
        self.assertIn("note-publication-preflight", workflow)
        self.assertIn("note-publication-report", workflow)

    def test_operational_state_and_published_assets_are_preserved(self) -> None:
        for path in (
            ".runtime",
            "observed_history",
            "source_roi_history",
            "deferred_deep_dive",
            "eyecatch_images",
            "assets",
        ):
            self.assertTrue((ROOT / path).exists(), path)

    def test_archived_run_documents_are_retained(self) -> None:
        archive = ROOT / "docs/archive"
        self.assertTrue(archive.is_dir())
        run_docs = list(archive.rglob("RUN*.md"))
        self.assertGreater(len(run_docs), 0)

    def test_historical_run_markdown_is_not_left_at_repository_root(self) -> None:
        root_run_docs = [p for p in ROOT.glob("RUN*.md") if p.is_file()]
        self.assertEqual(root_run_docs, [])

    def test_current_spec_tracks_live_baseline_and_old_spec_is_preserved(self) -> None:
        current = (ROOT / "AI_Intelligence_Factory_最終仕様書.md").read_text(encoding="utf-8")
        self.assertIn("現行Functional Baseline: **Run209", current)
        self.assertIn("Documentation Governance Baseline: **Run210", current)
        self.assertIn("Production Source of Truth: **`main`**", current)

        historical_path = (
            ROOT
            / "docs/archive/specifications/AI_Intelligence_Factory_仕様書_through_Run129_2026-08-25.md"
        )
        self.assertTrue(historical_path.is_file())
        historical = historical_path.read_text(encoding="utf-8")
        self.assertIn("本パッケージコード基準: **Run 122", historical)
        self.assertIn("Run129 Conversational Warmth", historical)

    def test_readme_declares_current_baseline_and_cleanup_safety(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Current functional baseline:** Run209", readme)
        self.assertIn("Current documentation governance baseline:** Run210", readme)
        self.assertIn("Current repository organization baseline:** Run201", readme)
        self.assertIn("repository garbage cleanup without intended runtime behavior change", readme)
        self.assertIn("Daily:** PAUSED", readme)

        # Keep the semantic repository-safety contract while allowing the
        # operator README to use either the original glob wording or a clearer
        # human-readable equivalent.
        self.assertTrue(
            "Historical `RUN*.md`" in readme
            or "Historical Run implementation notes" in readme
        )
        self.assertIn("do **not** bulk-delete", readme.lower())
        self.assertRegex(readme, re.compile(r"docs/archive/"))


if __name__ == "__main__":
    unittest.main()
