from __future__ import annotations

import ast
import inspect
import pathlib
import re
import types
import unicodedata
import unittest

import source_normalization as extracted


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _pipeline_tree() -> ast.Module:
    return ast.parse((ROOT / "pipeline.py").read_text(encoding="utf-8"))


def _historical_function_nodes() -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    wanted = set(extracted._EXPORTED_NAMES)
    return {
        node.name: node
        for node in _pipeline_tree().body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted
    }


def _load_historical_functions() -> dict[str, object]:
    """Execute only Stage3A's historical pure defs without importing the monolith."""
    nodes = _historical_function_nodes()
    wanted = set(extracted._EXPORTED_NAMES)
    if set(nodes) != wanted:
        return {}
    module = ast.Module(body=list(nodes.values()), type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"re": re, "unicodedata": unicodedata}
    exec(compile(module, str(ROOT / "pipeline.py"), "exec"), namespace)
    return {name: namespace[name] for name in extracted._EXPORTED_NAMES}


def _stage3b_imported_names() -> set[str]:
    names: set[str] = set()
    for node in _pipeline_tree().body:
        if isinstance(node, ast.ImportFrom) and node.module == "source_normalization":
            names.update(alias.asname or alias.name for alias in node.names)
    return names


class Run235SourceNormalizationModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.legacy = _load_historical_functions()

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

    def test_stage3a_parity_or_stage3b_single_source_contract(self):
        """During migration prove parity; after deletion prove canonical alias ownership."""
        wanted = set(extracted._EXPORTED_NAMES)
        nodes = _historical_function_nodes()
        if nodes:
            self.assertEqual(set(nodes), wanted)
            self.assertEqual(set(self.legacy), wanted)
        else:
            self.assertEqual(_stage3b_imported_names() & wanted, wanted)

    def test_language_detection_contract_and_stage3a_parity(self):
        expected = {
            "日本語タイトル": "ja",
            "GoRules": "en",
            "电商出图吧": "zh-CN",
            "한글 제목": "ko",
            "Пример заголовка": "ru",
            "12345": "und",
            "ＡＩ tool": "en",
            "漢字かな": "ja",
        }
        for value, language in expected.items():
            with self.subTest(value=value):
                self.assertEqual(extracted._detect_title_language(value), language)
                if self.legacy:
                    self.assertEqual(
                        extracted._detect_title_language(value),
                        self.legacy["_detect_title_language"](value),
                    )

    def test_descriptor_contract_and_stage3a_parity(self):
        samples = (
            ("AI product image generator for e-commerce listings", "ProductHunt", "EC商品画像生成ツール"),
            ("photo generator", "ProductHunt", "AI画像生成ツール"),
            ("video generation platform", "ProductHunt", "AI動画生成ツール"),
            ("multi-agent orchestration", "ProductHunt", "AIエージェントツール"),
            ("developer tool for API coding", "ProductHunt", "開発支援ツール"),
            ("analytics dashboard", "ProductHunt", "データ分析ツール"),
            ("text-to-speech voice app", "ProductHunt", "音声AIツール"),
            ("unclassified thing", "ProductHunt", "海外プロダクト"),
            ("unclassified thing", "HackerNews", "海外技術情報"),
        )
        for description, source, label in samples:
            with self.subTest(description=description, source=source):
                self.assertEqual(extracted._japanese_product_descriptor(description, source), label)
                if self.legacy:
                    self.assertEqual(
                        extracted._japanese_product_descriptor(description, source),
                        self.legacy["_japanese_product_descriptor"](description, source),
                    )

    def test_display_and_source_summary_contract(self):
        display, lang = extracted._multilingual_display_name(
            "电商出图吧", "AI product image generator for e-commerce listings", "ProductHunt"
        )
        self.assertEqual(display, "EC商品画像生成ツール「电商出图吧」")
        self.assertEqual(lang, "zh-CN")
        repo = {
            "nameWithOwner": "电商出图吧",
            "originalTitle": "电商出图吧",
            "displayName": display,
            "sourceLanguage": lang,
        }
        self.assertEqual(extracted._notion_display_name(repo), display)
        summary = extracted._source_summary_with_original(repo, "AI image generator")
        self.assertIn("Original Title: 电商出图吧", summary)
        self.assertIn("Language: zh-CN", summary)
        if self.legacy:
            self.assertEqual(
                extracted._multilingual_display_name(
                    "电商出图吧", "AI product image generator for e-commerce listings", "ProductHunt"
                ),
                self.legacy["_multilingual_display_name"](
                    "电商出图吧", "AI product image generator for e-commerce listings", "ProductHunt"
                ),
            )
            self.assertEqual(
                extracted._source_summary_with_original(repo, "AI image generator"),
                self.legacy["_source_summary_with_original"](repo, "AI image generator"),
            )

    def test_normalize_item_exact_contract_and_stage3a_parity(self):
        kwargs = dict(
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
        )
        expected = {
            "source": "ProductHunt",
            "nameWithOwner": "电商出图吧",
            "originalTitle": "电商出图吧",
            "displayName": "EC商品画像生成ツール「电商出图吧」",
            "sourceLanguage": "zh-CN",
            "url": "https://example.com/product",
            "description": "AI product image generator for e-commerce listings",
            "stargazerCount": 10,
            "licenseInfo": {"spdxId": "MIT"},
            "publishedAt": "2026-09-01T00:00:00Z",
            "sourceContext": "context",
            "primaryUrl": "https://example.com/primary",
            "sourceDetails": {"kind": "product"},
        }
        self.assertEqual(extracted.normalize_item(**kwargs), expected)
        if self.legacy:
            self.assertEqual(extracted.normalize_item(**kwargs), self.legacy["normalize_item"](**kwargs))

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
        self.assertFalse((ROOT / ".github/workflows/run231-stage2-surgical-migration.yml").exists())


if __name__ == "__main__":
    unittest.main()
