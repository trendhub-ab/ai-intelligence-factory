import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import editorial_eyecatch as ee
import run179_eyecatch_font_refinement as run179


ROOT = Path(__file__).resolve().parents[1]


class Run179EyecatchFontRefinementTests(unittest.TestCase):
    def test_brand_font_policy_uses_requested_weights(self):
        title_marker = object()
        with patch.object(run179, "_variable_font", return_value=title_marker) as loader:
            self.assertIs(run179.title_jp_font(64), title_marker)
            loader.assert_called_once_with(run179.NOTO_SANS_JP_PATH, 64, weight=900)

        subtitle_marker = object()
        with patch.object(run179, "_variable_font", return_value=subtitle_marker) as loader:
            self.assertIs(run179.subtitle_jp_font(27), subtitle_marker)
            loader.assert_called_once_with(run179.NOTO_SANS_JP_PATH, 27, weight=500)

        latin_marker = object()
        with patch.object(run179, "_variable_font", return_value=latin_marker) as loader:
            self.assertIs(run179.latin_ui_font(24, bold=True), latin_marker)
            loader.assert_called_once_with(run179.INTER_PATH, 24, weight=700, optical_size=24)

    def test_role_router_keeps_large_headlines_black_and_subheads_medium(self):
        with patch.object(run179, "title_jp_font", return_value="TITLE") as title_font, patch.object(
            run179, "subtitle_jp_font", return_value="SUBTITLE"
        ) as subtitle_font:
            self.assertEqual(run179._jp_font_by_role(82, True), "TITLE")
            self.assertEqual(run179._jp_font_by_role(48, True), "TITLE")
            self.assertEqual(run179._jp_font_by_role(30, True), "SUBTITLE")
            self.assertEqual(run179._jp_font_by_role(27, True), "SUBTITLE")
            title_font.assert_any_call(82)
            subtitle_font.assert_any_call(27)

    def test_google_font_sources_are_commit_pinned(self):
        self.assertEqual(len(run179.GOOGLE_FONTS_COMMIT), 40)
        for _path, url, _minimum in run179._FONT_ASSETS:
            self.assertIn(run179.GOOGLE_FONTS_COMMIT, url)
            self.assertTrue(url.startswith("https://raw.githubusercontent.com/google/fonts/"))
        self.assertIn("NotoSansJP", run179.NOTO_SANS_JP_PATH.name)
        self.assertIn("Inter", run179.INTER_PATH.name)

    def test_disabled_asset_bootstrap_never_uses_network(self):
        with patch.object(run179, "_download_font") as downloader:
            status = run179.ensure_google_font_assets(enabled=False)
        downloader.assert_not_called()
        self.assertEqual(set(status), {str(run179.NOTO_SANS_JP_PATH), str(run179.INTER_PATH)})

    def test_install_patches_only_font_resolution_contract(self):
        class FakePipeline:
            SYNTHETIC_REGRESSION_MODE = True

        original_jp = ee._jp_font
        original_latin = ee._latin_font
        fake = FakePipeline()
        try:
            run179.install(fake)
            self.assertIsNot(ee._jp_font, run179._jp_font_by_role)
            self.assertIs(ee._latin_font, run179.latin_ui_font)
            self.assertTrue(fake._RUN179_EYECATCH_FONT_REFINEMENT_INSTALLED)
            self.assertTrue(fake.RUN179_EYECATCH_JP_FONT_FAIL_CLOSED)
            self.assertEqual(fake.RUN179_EYECATCH_TITLE_FONT, "Noto Sans JP Black (wght=900)")
            self.assertEqual(fake.RUN179_EYECATCH_SUBTITLE_FONT, "Noto Sans JP Medium (wght=500)")
            self.assertEqual(fake.RUN179_EYECATCH_LATIN_FONT, "Inter Bold (wght=700)")
        finally:
            ee._jp_font = original_jp
            ee._latin_font = original_latin

    def test_production_font_resolution_fails_closed_without_japanese_assets(self):
        class FakePipeline:
            SYNTHETIC_REGRESSION_MODE = False

        original_jp = ee._jp_font
        original_latin = ee._latin_font
        fake = FakePipeline()
        try:
            with patch.object(run179, "_jp_font_assets_available", return_value=False):
                run179.install(fake)
                with self.assertRaisesRegex(RuntimeError, "Japanese eyecatch font is unavailable"):
                    ee._jp_font(64, bold=True)
        finally:
            ee._jp_font = original_jp
            ee._latin_font = original_latin

    def test_production_font_resolution_uses_noto_when_available(self):
        class FakePipeline:
            SYNTHETIC_REGRESSION_MODE = False

        original_jp = ee._jp_font
        original_latin = ee._latin_font
        fake = FakePipeline()
        marker = object()
        try:
            with patch.object(run179, "_jp_font_assets_available", return_value=True), patch.object(
                run179, "_jp_font_by_role", return_value=marker
            ) as router:
                run179.install(fake)
                self.assertIs(ee._jp_font(64, bold=True), marker)
                router.assert_called_once_with(64, bold=True)
        finally:
            ee._jp_font = original_jp
            ee._latin_font = original_latin

    def test_renderer_contract_remains_1280x670_rgb_without_network(self):
        class FakePipeline:
            SYNTHETIC_REGRESSION_MODE = True

        original_jp = ee._jp_font
        original_latin = ee._latin_font
        fake = FakePipeline()
        try:
            run179.install(fake)
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "run179.png")
                result = ee.generate_note_editorial_eyecatch(
                    "AIは重要。でも正直、もう追いきれない。",
                    "仕事に必要な変化だけを短時間で理解する。",
                    path,
                    category="AI & TECH",
                    date_label="2026.09",
                )
                self.assertEqual(result, path)
                with Image.open(path) as image:
                    self.assertEqual(image.size, (1280, 670))
                    self.assertEqual(image.mode, "RGB")
        finally:
            ee._jp_font = original_jp
            ee._latin_font = original_latin

    def test_production_japanese_font_ready_accepts_downloaded_noto(self):
        with patch.object(run179, "_valid_font_file", return_value=True), \
             patch.object(Path, "is_file", return_value=False):
            self.assertTrue(run179.production_japanese_font_ready())

    def test_production_japanese_font_ready_accepts_system_noto(self):
        with patch.object(run179, "_valid_font_file", return_value=False), \
             patch.object(Path, "is_file", return_value=True), \
             patch.object(Path, "stat") as stat:
            stat.return_value.st_size = 2_000_000
            self.assertTrue(run179.production_japanese_font_ready())

    def test_require_production_japanese_font_fails_closed_without_japanese_font(self):
        with patch.object(run179, "production_japanese_font_ready", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Japanese eyecatch font is unavailable"):
                run179.require_production_japanese_font()

    def test_production_entrypoint_requires_japanese_font_after_bootstrap(self):
        source = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        bootstrap = source.index("run179_eyecatch_font_refinement.ensure_google_font_assets(")
        require = source.index("run179_eyecatch_font_refinement.require_production_japanese_font()")
        self.assertLess(bootstrap, require)
        nearby = source[bootstrap:require + 200]
        self.assertIn('if not bool(getattr(pipeline, "SYNTHETIC_REGRESSION_MODE", False)):', nearby)

    def test_production_entrypoint_installs_run179_after_run178(self):
        runtime_source = (ROOT / "runtime_layers.py").read_text(encoding="utf-8")
        entrypoint_source = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        run178_pos = runtime_source.index("run178_eyecatch_editorial_layout_optimizer.install")
        run179_pos = runtime_source.index("run179_eyecatch_font_refinement.install")
        self.assertLess(run178_pos, run179_pos)
        self.assertIn("ensure_google_font_assets(", entrypoint_source)
        self.assertIn("SYNTHETIC_REGRESSION_MODE", entrypoint_source)


if __name__ == "__main__":
    unittest.main()
