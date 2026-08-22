import inspect
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GH_PAT", "test-token")
os.environ.setdefault("GEMINI_QUOTA_PROJECT_ID", "test-project")

try:
    from google import genai  # noqa: F401
except ImportError:
    google_mod = sys.modules.get("google") or types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")
    class APIError(Exception):
        pass
    class Client:
        def __init__(self, **_kwargs):
            self.chats = types.SimpleNamespace(create=lambda **_kw: None)
    genai_mod.Client = Client
    errors_mod.APIError = APIError
    google_mod.genai = genai_mod
    sys.modules.update({"google": google_mod, "google.genai": genai_mod, "google.genai.errors": errors_mod})

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import pipeline


class Run105EyecatchVerticalCenteringTests(unittest.TestCase):
    @staticmethod
    def _jp_font(size):
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
        return ImageFont.load_default()

    @staticmethod
    def _num_font(size):
        candidates = [
            "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
            "/usr/share/fonts/truetype/lato/Lato-Heavy.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
        return ImageFont.load_default()

    def test_outer_content_shift_uses_visual_bounds(self):
        # Current approved geometry: CJK title visible top is y=142 and lower card
        # bottom is y=548 inside outer y=78..592.  Correct optical shift is -10px.
        self.assertEqual(-10, pipeline._eyecatch_vertical_center_shift((78, 592), (142, 548)))

    def test_lower_text_stack_is_visually_centered(self):
        image = Image.new("RGBA", (400, 240), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        box = (20, 30, 334, 183)
        bounds = pipeline._draw_eyecatch_text_stack_centered(
            draw,
            box,
            [
                ("技術的破壊力", self._jp_font(29), (255, 255, 255, 255)),
                ("(Technical Impact)", self._jp_font(19), (235, 241, 250, 255)),
                ("20/25", self._num_font(50), (255, 255, 255, 255)),
            ],
            gaps=(8, 16),
        )
        box_center = (box[1] + box[3]) / 2
        text_center = (bounds[1] + bounds[3]) / 2
        self.assertLessEqual(abs(box_center - text_center), 1.0)

    def test_metric_cards_no_longer_use_fixed_text_y_coordinates(self):
        src = inspect.getsource(pipeline.generate_eyecatch_image)
        self.assertIn("_draw_eyecatch_text_stack_centered", src)
        self.assertIn("content_shift_y", src)
        self.assertNotIn('centered("技術的破壊力", 255, 416', src)
        self.assertNotIn('centered("緊急度", 587, 416', src)

    def test_generated_preview_remains_1280_by_670(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "preview.png"
            result = pipeline.generate_eyecatch_image(
                "The New MCP Roadmap",
                str(output),
                "HackerNews",
                decision_score=75,
                technical_impact=20,
                urgency=12,
                article_ready=True,
            )
            self.assertEqual(str(output), result)
            with Image.open(output) as image:
                self.assertEqual((1280, 670), image.size)


if __name__ == "__main__":
    unittest.main()
