from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Run200RepositoryLayoutTests(unittest.TestCase):
    def test_historical_run_markdown_is_not_left_at_repository_root(self) -> None:
        leftovers = sorted(path.name for path in ROOT.glob("RUN*.md"))
        self.assertEqual([], leftovers)

    def test_active_production_runtime_layers_are_preserved(self) -> None:
        active = [
            "run172_production_reliability.py",
            "run173_operational_yield.py",
            "run174_monthly_digest_integrity.py",
            "run175_semantic_fact_precision.py",
            "run176_scope_fidelity.py",
            "run177_paid_funnel_alignment.py",
            "run178_eyecatch_editorial_layout_optimizer.py",
            "run179_eyecatch_font_refinement.py",
            "run180_eyecatch_semantic_layout.py",
            "run181_eyecatch_visual_balance.py",
            "run182_eyecatch_conclusion_emphasis.py",
            "run183_eyecatch_emphasis_scale.py",
            "reader_value_review_bridge.py",
            "run194_publication_contract.py",
        ]
        missing = [name for name in active if not (ROOT / name).is_file()]
        self.assertEqual([], missing)

        production_entrypoint = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        for name in active[:-2]:
            module = name.removesuffix(".py")
            self.assertIn(f"import {module}", production_entrypoint)
        self.assertIn("reader_value_review_bridge", production_entrypoint)
        self.assertIn("run194_publication_contract", production_entrypoint)

    def test_active_note_safety_stack_is_preserved(self) -> None:
        active = [
            "note_draft_automation.py",
            "run185_note_ready_legacy_skip.py",
            "run186_note_header_image_resilience.py",
            "run187_note_editor_readiness.py",
            "run188_note_header_upload_fallback.py",
            "run189_note_editor_route_gate.py",
            "run190_note_persistent_cloud.py",
            "run191_note_crop_dialog_resilience.py",
            "run193_note_official_header_upload.py",
            "run194_note_current_contract.py",
            "run194_note_persistent_cloud.py",
            "run194_publication_contract.py",
            "run199_note_vm_preflight.py",
        ]
        missing = [name for name in active if not (ROOT / name).is_file()]
        self.assertEqual([], missing)

    def test_note_workflow_keeps_preflight_vm_gate_and_pinned_sync_id(self) -> None:
        workflow = (ROOT / ".github/workflows/note-create-draft.yml").read_text(encoding="utf-8")
        self.assertIn("run199_note_vm_preflight.py", workflow)
        self.assertIn("should_start_vm", workflow)
        self.assertIn("selected_sync_id", workflow)
        self.assertIn("run194_note_persistent_cloud.py", workflow)
        self.assertIn("needs: preflight", workflow)

    def test_operational_state_and_published_assets_are_preserved(self) -> None:
        protected = [
            ".runtime",
            "observed_history",
            "source_roi_history",
            "deferred_deep_dive",
            "eyecatch_images",
            "assets",
        ]
        missing = [name for name in protected if not (ROOT / name).exists()]
        self.assertEqual([], missing)

    def test_archived_run_documents_are_retained(self) -> None:
        archive = ROOT / "docs/archive/repository-cleanup-2026-09-02/root-run-docs"
        expected = [
            "RUN177_PAID_FUNNEL_ALIGNMENT.md",
            "RUN178_EYECATCH_EDITORIAL_LAYOUT_OPTIMIZER.md",
            "RUN179_EYECATCH_FONT_REFINEMENT.md",
            "RUN180_EYECATCH_SEMANTIC_LAYOUT.md",
            "RUN184_NOTE_DRAFT_AUTOMATION.md",
            "RUN184_NOTE_LOGIN_METHOD.md",
            "RUN190_NOTE_PERSISTENT_CLOUD.md",
            "RUN196_NOTION_RATE_LIMIT_AUDIT.md",
        ]
        missing = [name for name in expected if not (archive / name).is_file()]
        self.assertEqual([], missing)

    def test_current_spec_is_run199_and_old_spec_is_preserved(self) -> None:
        current = (ROOT / "AI_Intelligence_Factory_最終仕様書.md").read_text(encoding="utf-8")
        self.assertIn("現行Functional Baseline: **Run199", current)
        self.assertIn("Production Source of Truth: **`main`**", current)
        self.assertNotIn("本パッケージコード基準: **Run 122", current)

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
        self.assertIn("Current functional baseline:** Run199", readme)
        self.assertIn("repository consolidation with no intended runtime behavior change", readme)
        self.assertIn("Daily:** PAUSED", readme)
        self.assertIn("Historical `RUN*.md`", readme)
        self.assertIn("do **not** bulk-delete", readme)


if __name__ == "__main__":
    unittest.main()
