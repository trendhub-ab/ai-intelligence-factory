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

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import pipeline


class Run106EyecatchHorizontalCenteringTests(unittest.TestCase):
    def test_centered_pair_boxes_match_card_center(self):
        card = (60, 78, 770, 592)
        left_box, right_box = pipeline._eyecatch_centered_pair_boxes(card, 385, 538, box_width=314, gap=18)
        pair_center = (left_box[0] + right_box[2]) / 2
        card_center = (card[0] + card[2]) / 2
        self.assertEqual(314, left_box[2] - left_box[0])
        self.assertEqual(314, right_box[2] - right_box[0])
        self.assertEqual(18, right_box[0] - left_box[2])
        self.assertEqual(pair_center, card_center)
        self.assertEqual(left_box[0] - card[0], card[2] - right_box[2])

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
