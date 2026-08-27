import tempfile
import unittest

from x_intelligence import build_free_chip_post, extract_core_conclusion, generate_batch


class XGroundedConclusionTests(unittest.TestCase):
    def _item(self, **overrides):
        item = {
            "Name": "The New MCP Roadmap",
            "URL": "https://example.com/mcp",
            "Screening Score": 80,
            "Decision Score": 82,
            "Source Summary": "MCPをAIと外部サービスをつなぐ共通規格として、より安定して使える方向へ整備していく。",
            "Reason": "標準化の進展がAIエージェント実装へ影響する。",
        }
        item.update(overrides)
        return item

    def test_explicit_core_conclusion_has_priority(self):
        conclusion, source = extract_core_conclusion(
            self._item(core_conclusion="AIと外部サービスをつなぐ共通基盤の整備が進む。")
        )
        self.assertEqual(conclusion, "AIと外部サービスをつなぐ共通基盤の整備が進む")
        self.assertEqual(source, "core_conclusion")

    def test_free_post_always_contains_grounded_conclusion(self):
        item = self._item()
        draft = build_free_chip_post(item)
        self.assertTrue(draft["grounded_conclusion"])
        self.assertEqual(draft["core_conclusion_source"], "Source Summary")
        self.assertIn(draft["core_conclusion"], draft["post"])
        self.assertLessEqual(draft["characters"], 280)
        self.assertEqual(draft["gemini_calls"], 0)
        self.assertEqual(draft["x_api_calls"], 0)

    def test_title_alone_is_not_accepted_as_conclusion(self):
        with self.assertRaisesRegex(ValueError, "grounded core conclusion"):
            build_free_chip_post(
                {
                    "Name": "日本語タイトルだけの候補",
                    "URL": "https://example.com/title-only",
                    "Screening Score": 90,
                    "Decision Score": 90,
                }
            )

    def test_batch_skips_candidate_without_grounded_conclusion(self):
        good = self._item(Name="good", URL="https://example.com/good")
        bad = {
            "Name": "結論なし",
            "URL": "https://example.com/bad",
            "Screening Score": 95,
            "Decision Score": 95,
        }
        with tempfile.TemporaryDirectory() as tmp:
            manifest = generate_batch([bad, good], output_dir=tmp, max_items=5)
        self.assertEqual(manifest["selected_records"], 2)
        self.assertEqual(manifest["generated_candidates"], 1)
        self.assertEqual(manifest["skipped_candidates"], 1)
        self.assertEqual(manifest["skipped"][0]["reason"], "missing_grounded_core_conclusion")
        self.assertTrue(manifest["core_conclusion_required"])


if __name__ == "__main__":
    unittest.main()
