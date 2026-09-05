from __future__ import annotations

import inspect
import pathlib
import types
import unittest

import pipeline
import source_normalization as extracted


ROOT = pathlib.Path(__file__).resolve().parents[1]


class Run235SourceNormalizationModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Capture the historical pipeline functions before any install call so parity
        # compares independent implementations rather than aliases of the same function.
        cls.legacy = {
            name: getattr(pipeline, name)
            for name in extracted._EXPORTED_NAMES
        }

    def test_extracted_module_stays_pure_zero_api(self):
        source = inspect.getsource(extracted)
        forbidden = (
            "import requests",
            "from requests",
            "google.genai",
            "google.generativeai",
            "NOTION_API_KEY",
            "NOTION_DATA_SOURCE_ID",
            "GEMINI_API_KEY",
            "Decision Score",
            "Evidence Gate",
        )
        for token in forbidden:
            self.assertNotIn(token, source, token)

    def test_language_detection_exact_parity(self):
        samples = (
            "日本語タイトル",
            "GoRules",
            "电商出图吧",
            "한글 제목",
            "Пример заголовка",
            "12345",
            "ＡＩ tool",
            "漢字かな",
        )
        for value in samples:
            with self.subTest(value=value):
                self.assertEqual(
                    extracted._detect_title_language(value),
                    self.legacy["_detect_title_language"](value),
                )

    def test_descriptor_exact_parity(self):
        samples = (
            ("AI product image generator for e-commerce listings", "ProductHunt"),
            ("photo generator", "ProductHunt"),
            ("video generation platform", "ProductHunt"),
            ("multi-agent orchestration", "ProductHunt"),
            ("developer tool for API coding", "ProductHunt"),
            ("analytics dashboard", "ProductHunt"),
            ("text-to-speech voice app", "ProductHunt"),
            ("unclassified thing", "ProductHunt"),
            ("unclassified thing", "HackerNews"),
        )
        for description, source in samples:
            with self.subTest(description=description, source=source):
                self.assertEqual(
                    extracted._japanese_product_descriptor(description, source),
                    self.legacy["_japanese_product_descriptor"](description, source),
                )

    def test_display_and_source_summary_exact_parity(self):
        cases = (
            ("电商出图吧", "AI product image generator for e-commerce listings", "ProductHunt"),
            ("한국 도구", "agent platform", "ProductHunt"),
            ("Инструмент", "developer tool", "ProductHunt"),
            ("GoRules", "rules engine", "ProductHunt"),
            ("日本語タイトル", "説明", "HackerNews"),
        )
        for title, description, source in cases:
            with self.subTest(title=title):
                legacy_display = self.legacy["_multilingual_display_name"](
                    title, description, source
                )
                extracted_display = extracted._multilingual_display_name(
                    title, description, source
                )
                self.assertEqual(extracted_display, legacy_display)
                display_name, lang = extracted_display
                repo = {
                    "nameWithOwner": title,
                    "originalTitle": title,
                    "displayName": display_name,
                    "sourceLanguage": lang,
                }
                self.assertEqual(
                    extracted._notion_display_name(repo),
                    self.legacy["_notion_display_name"](repo),
                )
                summary = "x" * 2200
                self.assertEqual(
                    extracted._source_summary_with_original(repo, summary),
                    self.legacy["_source_summary_with_original"](repo, summary),
                )

    def test_normalize_item_exact_dict_parity(self):
        cases = (
            dict(
                source="ProductHunt",
                name="电商出图吧",
                url=" https://example.com/product ",
                description="AI product image generator for e-commerce listings",
                engagement=10,
                license_info={"spdxId": "MIT"},
                published_at="2026-09-01T00:00:00Z",
                source_context=" context ",
                primary_url=" https://example.com/primary ",
                source_details={"kind": "product"},
            ),
            dict(
                source="HackerNews",
                name="",
                url="",
                description="",
                engagement=0,
            ),
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                self.assertEqual(
                    extracted.normalize_item(**kwargs),
                    self.legacy["normalize_item"](**kwargs),
                )

    def test_install_binds_only_declared_surface(self):
        target = types.SimpleNamespace(sentinel=object())
        returned = extracted.install(target)
        self.assertIs(returned, target)
        for name in extracted._EXPORTED_NAMES:
            self.assertIs(getattr(target, name), getattr(extracted, name))
        self.assertTrue(hasattr(target, "sentinel"))

    def test_production_installs_normalization_before_runtime_and_telemetry_last(self):
        source = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        normalization = source.index("install_source_normalization(pipeline)")
        runtime = source.index("install_runtime_layers(pipeline)")
        telemetry = source.index("install_performance_telemetry(pipeline)")
        main_call = source.index("pipeline.main()")
        self.assertLess(normalization, runtime)
        self.assertLess(runtime, telemetry)
        self.assertLess(telemetry, main_call)

    def test_stage2_temporary_workflow_is_retired(self):
        self.assertFalse(
            (ROOT / ".github/workflows/run231-stage2-surgical-migration.yml").exists()
        )


if __name__ == "__main__":
    unittest.main()
