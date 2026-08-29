import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from editorial_eyecatch import (
    balanced_headline_lines,
    editorial_hook_from_title,
    editorial_subheadline,
    generate_note_editorial_eyecatch,
    infer_editorial_category,
)

ROOT = Path(__file__).resolve().parents[1]


class Run150EditorialEyecatchTests(unittest.TestCase):
    def test_category_is_topic_based_not_source_based(self):
        self.assertEqual(infer_editorial_category("AIエージェント同士が仕事を分担", "", "GitHub"), "AI AGENTS")
        self.assertEqual(infer_editorial_category("新しい脆弱性への対策", "security update", "ArXiv"), "SECURITY")
        self.assertEqual(infer_editorial_category("GPU推論を高速化", "serving latency", "HackerNews"), "MODELS")
        self.assertNotEqual(infer_editorial_category("AIエージェント同士が仕事を分担", "", "GitHub"), "GitHub")
        # Discovery source alone must never become a public editorial category.
        self.assertEqual(infer_editorial_category("新しい利用体験", "日常作業をもっと簡単にする", "GitHub"), "AI & TECH")

    def test_balanced_headline_prefers_natural_japanese_break(self):
        self.assertEqual(
            balanced_headline_lines("AIに“同僚”ができ始めた。"),
            ["AIに“同僚”が", "でき始めた。"],
        )

    def test_public_copy_does_not_surface_internal_decision_metrics(self):
        hook = editorial_hook_from_title("【Decision Score: 88】AIに“同僚”ができ始めた。 WATCH")
        sub = editorial_subheadline("Technical Impact: 22 緊急度: 18 エージェント同士が仕事を分担します。", hook)
        combined = hook + sub
        self.assertNotIn("Decision Score", combined)
        self.assertNotIn("Technical Impact", combined)
        self.assertNotIn("WATCH", combined)
        self.assertNotIn("緊急度", combined)
        self.assertIn("AI", hook)

    def test_renderer_produces_note_standard_1280x670(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "editorial.png")
            result = generate_note_editorial_eyecatch(
                "AIに“同僚”ができ始めた。",
                "エージェント同士が、勝手に仕事を分担する時代へ。",
                path,
                category="AI AGENTS",
                date_label="2026.08",
            )
            self.assertEqual(result, path)
            self.assertTrue(os.path.isfile(path))
            with Image.open(path) as image:
                self.assertEqual(image.size, (1280, 670))
                self.assertEqual(image.mode, "RGB")

    def test_pipeline_keeps_notion_decision_card_and_uses_editorial_for_audit(self):
        source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        self.assertIn("from editorial_eyecatch import", source)
        self.assertIn("generate_note_editorial_eyecatch(", source)
        # Existing Decision Card generation/upload remains the Notion-facing image path.
        self.assertIn("generated_path = generate_eyecatch_image(", source)
        self.assertIn("eyecatch_url = upload_eyecatch_to_github(eyecatch_path, eyecatch_filename)", source)
        # Human audit / note delivery must receive the editorial image instead of the score card.
        self.assertGreaterEqual(source.count("eyecatch_path=note_eyecatch_path"), 2)
        # Fresh/fixed real-article regression stores the editorial image inside its existing artifact tree.
        self.assertIn("os.path.join(REGEN_TEST_OUTPUT_DIR, \"eyecatch\")", source)


if __name__ == "__main__":
    unittest.main()
