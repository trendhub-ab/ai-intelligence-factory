from __future__ import annotations

import ast
import inspect
import tempfile
import types
import unittest
from pathlib import Path

from PIL import Image

import legacy_eyecatch_renderer as legacy


ROOT = Path(__file__).resolve().parents[1]


class _Logger:
    def __init__(self):
        self.info_rows = []
        self.warning_rows = []

    def info(self, message, *args, **kwargs):
        self.info_rows.append(str(message))

    def warning(self, message, *args, **kwargs):
        self.warning_rows.append(str(message))


class Run231Stage2LegacyEyecatchModuleTests(unittest.TestCase):
    def _pipeline(self, background_dir: str):
        live_editorial = lambda *args, **kwargs: "editorial-live"
        p = types.SimpleNamespace(
            logger=_Logger(),
            EYECATCH_BACKGROUND_DIR=background_dir,
            SOURCE_BACKGROUND_IMAGE={
                "GitHub": "github.png",
                "HackerNews": "hackernews.png",
                "ArXiv": "arxiv.png",
                "ProductHunt": "producthunt.png",
            },
            EYECATCH_BACKGROUND_DEFAULT="default.png",
            generate_note_editorial_eyecatch=live_editorial,
            generate_eyecatch_image=lambda *args, **kwargs: "legacy-original",
        )
        return p, live_editorial

    def test_module_is_provider_and_persistence_free(self):
        source = (ROOT / "legacy_eyecatch_renderer.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse({"requests", "google", "notion_client"} & imported)
        self.assertNotIn("genai.", source)
        self.assertNotIn("api.notion.com", source)
        self.assertNotIn("api.github.com", source)
        self.assertNotIn("GEMINI_API_KEY", source)

    def test_score_contract_matches_historical_boundaries(self):
        self.assertEqual((100, 116, 139), legacy.score_color(None))
        self.assertEqual((100, 116, 139), legacy.score_color(59))
        self.assertEqual((34, 211, 238), legacy.score_color(60))
        self.assertEqual((34, 211, 238), legacy.score_color(69))
        self.assertEqual((59, 130, 246), legacy.score_color(70))
        self.assertEqual((59, 130, 246), legacy.score_color(79))
        self.assertEqual((139, 92, 246), legacy.score_color(80))
        self.assertEqual((139, 92, 246), legacy.score_color(89))
        self.assertEqual((245, 185, 66), legacy.score_color(90))
        self.assertEqual((245, 185, 66), legacy.score_color(100))
        self.assertEqual((245, 185, 66), legacy.score_color(999))

    def test_score_component_parser_never_recomputes_or_accepts_out_of_range(self):
        self.assertEqual(
            (23, 17),
            legacy.extract_score_components("Technical Impact: 23/25; Urgency: 17/20"),
        )
        self.assertEqual(
            (None, None),
            legacy.extract_score_components("Technical Impact: 26/25; Urgency: 21/20"),
        )
        self.assertEqual((None, None), legacy.extract_score_components("no approved rubric values"))

    def test_geometric_helpers_preserve_center_contract(self):
        self.assertEqual(0, legacy.vertical_center_shift((0, 100), (20, 80)))
        self.assertEqual(10, legacy.vertical_center_shift((0, 100), (10, 70)))
        left, right = legacy.centered_pair_boxes((60, 78, 770, 592), 395, 548, 314, 18)
        self.assertEqual(18, right[0] - left[2])
        container_center = (60 + 770) / 2
        pair_center = (left[0] + right[2]) / 2
        self.assertEqual(container_center, pair_center)

    def test_background_cover_returns_exact_target_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "github.png"
            Image.new("RGB", (1600, 900), (20, 30, 40)).save(src)
            logger = _Logger()
            image = legacy.load_background(
                "GitHub",
                1280,
                670,
                background_dir=tmp,
                source_background_image={"GitHub": "github.png"},
                default_filename="default.png",
                logger=logger,
            )
            self.assertIsNotNone(image)
            self.assertEqual((1280, 670), image.size)
            self.assertEqual([], logger.warning_rows)

    def test_install_preserves_live_editorial_identity_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, live_editorial = self._pipeline(tmp)
            legacy.install(p)
            first_legacy = p.generate_eyecatch_image
            self.assertIs(live_editorial, p.generate_note_editorial_eyecatch)
            self.assertTrue(getattr(first_legacy, "__run231_stage2_legacy_eyecatch__", False))

            legacy.install(p)
            self.assertIs(first_legacy, p.generate_eyecatch_image)
            self.assertIs(live_editorial, p.generate_note_editorial_eyecatch)

    def test_installed_signature_matches_historical_public_legacy_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, _ = self._pipeline(tmp)
            original_signature = inspect.signature(p.generate_eyecatch_image)
            # Fake original is variadic; install must expose the explicit historical contract.
            legacy.install(p)
            params = list(inspect.signature(p.generate_eyecatch_image).parameters)
            self.assertEqual(
                [
                    "title_text",
                    "output_path",
                    "source",
                    "decision_score",
                    "technical_impact",
                    "urgency",
                    "article_ready",
                ],
                params,
            )
            self.assertNotEqual(original_signature, inspect.signature(p.generate_eyecatch_image))

    def test_not_ready_is_fail_safe_and_does_not_write_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, _ = self._pipeline(tmp)
            legacy.install(p)
            output = Path(tmp) / "skip.png"
            result = p.generate_eyecatch_image("title", str(output), article_ready=False)
            self.assertIsNone(result)
            self.assertFalse(output.exists())
            self.assertTrue(any("EYECATCH SKIP" in row for row in p.logger.info_rows))

    def test_ready_generates_png_with_historical_dimensions_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, _ = self._pipeline(tmp)
            legacy.install(p)
            output = Path(tmp) / "ready.png"
            result = p.generate_eyecatch_image(
                "unused historical title",
                str(output),
                source="GitHub",
                decision_score=78,
                technical_impact=20,
                urgency=15,
                article_ready=True,
            )
            self.assertEqual(str(output), result)
            self.assertTrue(output.exists())
            with Image.open(output) as image:
                self.assertEqual((1280, 670), image.size)
                self.assertEqual("PNG", image.format)


if __name__ == "__main__":
    unittest.main()
