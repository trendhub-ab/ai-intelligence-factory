from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Run231Stage2RepositoryContractTests(unittest.TestCase):
    def test_legacy_renderer_is_provider_and_persistence_free_by_static_contract(self):
        source = (ROOT / "legacy_eyecatch_renderer.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])

        self.assertFalse({"requests", "google", "notion_client", "pipeline"} & imported_roots)
        for forbidden in (
            "genai.",
            "api.notion.com",
            "api.github.com",
            "GEMINI_API_KEY",
            "NOTION_API_KEY",
        ):
            self.assertNotIn(forbidden, source)

    def test_production_does_not_reintroduce_legacy_renderer_hard_import(self):
        source = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        self.assertNotIn("from legacy_eyecatch_renderer import", source)
        self.assertNotIn("install_legacy_eyecatch_renderer(pipeline)", source)

        font = source.index("run179_eyecatch_font_refinement.ensure_google_font_assets(")
        telemetry = source.index("install_performance_telemetry(pipeline)")
        main = source.index("pipeline.main()")
        self.assertLess(font, telemetry)
        self.assertLess(telemetry, main)

    def test_pipeline_bridge_tolerates_only_exact_missing_legacy_module(self):
        source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        self.assertIn("except ModuleNotFoundError as _run231_legacy_import_error:", source)
        self.assertIn(
            'if _run231_legacy_import_error.name != "legacy_eyecatch_renderer":',
            source,
        )
        self.assertIn("raise RuntimeError(", source)
        self.assertIn("legacy eyecatch renderer is unavailable", source)
        self.assertIn("the publication path must use generate_note_editorial_eyecatch", source)

    def test_run231_reference_declares_strangler_and_quality_invariants(self):
        reference = (ROOT / "docs/reference/RUN231_PIPELINE_MODULARIZATION.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Strangler modularization", reference)
        self.assertIn("Fact / Evidence / Decision consistency", reference)
        self.assertIn("zero Gemini/model calls", reference)
        self.assertIn("generate_note_editorial_eyecatch", reference)
        self.assertIn("full unittest", reference)
        self.assertIn("Synthetic Production", reference)


if __name__ == "__main__":
    unittest.main()
