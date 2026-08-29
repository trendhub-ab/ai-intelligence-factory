import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Run160PublicEyecatchUnificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        marker = "# Run160: public note delivery"
        cls.publication = cls.source.split(marker, 1)[1].split("        analyzed_at = _analyzed_at_now_iso()", 1)[0]

    def test_editorial_is_single_public_image_source(self):
        self.assertIn("generate_note_editorial_eyecatch(", self.publication)
        self.assertIn(
            "eyecatch_url = upload_eyecatch_to_github(note_eyecatch_path, eyecatch_filename)",
            self.publication,
        )
        self.assertIn("[PUBLIC EDITORIAL EYECATCH]", self.publication)

    def test_legacy_decision_card_is_not_called_by_publication_path(self):
        self.assertNotIn("generate_eyecatch_image(", self.publication)
        self.assertNotIn("_extract_eyecatch_score_components", self.publication)
        self.assertNotIn("generated_path =", self.publication)

    def test_no_fallback_to_internal_score_card(self):
        self.assertGreaterEqual(self.publication.count("旧Decision Cardへフォールバック"), 3)
        self.assertIn("if not note_eyecatch_path:", self.publication)

    def test_legacy_renderer_is_retained_only_for_internal_compatibility(self):
        self.assertIn("def generate_eyecatch_image(", self.source)
        self.assertIn("legacy/internal 1280x670 Decision Score card", self.source)
        self.assertIn("publication path must use ``generate_note_editorial_eyecatch``", self.source)

    def test_notion_persistence_consumes_the_editorial_upload_url(self):
        after = self.source.split("        analyzed_at = _analyzed_at_now_iso()", 1)[1]
        self.assertIn("parsed[\"title_text\"], eyecatch_url", after)
        self.assertIn("title_text, eyecatch_url", self.source)


if __name__ == "__main__":
    unittest.main()
