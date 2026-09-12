import unittest

from groq_screening_shadow_run46 import _select_threshold_near, _to_prompt_items


class GroqScreeningShadowRun46Test(unittest.TestCase):
    def test_threshold_selection_is_deterministic(self):
        items = [
            {"id": "a", "raw_screening_score": 54},
            {"id": "b", "raw_screening_score": 56},
            {"id": "c", "raw_screening_score": 40},
        ]
        selected = _select_threshold_near(items, 2)
        self.assertEqual([row["id"] for row in selected], ["a", "b"])

    def test_missing_description_is_not_invented(self):
        rows = [{
            "id": "B1", "source": "HackerNews", "name": "Example",
            "engagement": 1, "published_at": "2026-09-12T00:00:00Z",
            "url": "https://example.com", "raw_screening_score": 55,
        }]
        prompt_items = _to_prompt_items(rows)
        self.assertEqual(prompt_items[0]["repo"]["description"], "")
        self.assertEqual(prompt_items[0]["screening_id"], "B1")


if __name__ == "__main__":
    unittest.main()
