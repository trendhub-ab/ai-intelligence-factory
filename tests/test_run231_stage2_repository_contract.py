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

    def test_production_installs_legacy_renderer_after_font_before_telemetry_and_main(self):
        source = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        font = source.index("run179_eyecatch_font_refinement.ensure_google_font_assets(")
        legacy = source.index("install_legacy_eyecatch_renderer(pipeline)")
        telemetry = source.index("install_performance_telemetry(pipeline)")
        main = source.index("pipeline.main()")
        self.assertLess(font, legacy)
        self.assertLess(legacy, telemetry)
        self.assertLess(telemetry, main)

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
