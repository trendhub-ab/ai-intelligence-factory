import tempfile
import unittest
from pathlib import Path

from x_intelligence import build_x_post, save_pending_post, select_x_candidates


def _item(**overrides):
    base = {
        "Name": "Geminiに新しいエージェント機能が追加",
        "URL": "https://example.com/official-release",
        "Screening Score": 72,
        "Decision Score": 81,
        "Engagement": 40,
        "Source Summary": "複数ステップの作業を自動で進められる機能が公開されました。",
        "Reason": "回答するAIから、仕事を実行するAIへの移行を示す更新です。",
        "Action": "既存の定型業務で置き換え可能な工程を確認する。",
    }
    base.update(overrides)
    return base


class XIntelligenceTests(unittest.TestCase):
    def test_build_x_post_is_zero_api_and_review_only(self):
        draft = build_x_post(_item())
        self.assertEqual(draft["status"], "X Pending Review")
        self.assertEqual(draft["gemini_calls"], 0)
        self.assertEqual(draft["x_api_calls"], 0)
        self.assertFalse(draft["auto_posted"])
        self.assertEqual(draft["generator_mode"], "deterministic_zero_api")

    def test_build_x_post_retains_primary_source_and_stays_within_limit(self):
        item = _item(
            **{
                "Source Summary": "長い説明です。" * 80,
                "Reason": "重要な理由です。" * 80,
                "Action": "確認すべき内容です。" * 80,
            }
        )
        draft = build_x_post(item, max_chars=280)
        self.assertLessEqual(draft["characters"], 280)
        self.assertIn(item["URL"], draft["post"])
        self.assertIn("一次情報：", draft["post"])

    def test_build_x_post_fails_closed_without_source_url(self):
        with self.assertRaisesRegex(ValueError, "primary source URL"):
            build_x_post(_item(URL=""))

    def test_selector_accepts_strong_decision_or_screening_signal(self):
        items = [
            _item(Name="decision", **{"Decision Score": 88, "Screening Score": 20}),
            _item(Name="screening", URL="https://example.com/s", **{"Decision Score": 20, "Screening Score": 90}),
            _item(Name="weak", URL="https://example.com/w", **{"Decision Score": 30, "Screening Score": 30}),
            _item(Name="no-url", URL="", **{"Decision Score": 99, "Screening Score": 99}),
        ]
        selected = select_x_candidates(items, max_items=10)
        names = [item["Name"] for item in selected]
        self.assertIn("decision", names)
        self.assertIn("screening", names)
        self.assertNotIn("weak", names)
        self.assertNotIn("no-url", names)

    def test_selector_does_not_mutate_input(self):
        original = _item()
        snapshot = dict(original)
        selected = select_x_candidates([original])
        self.assertEqual(original, snapshot)
        self.assertIn("x_candidate_score", selected[0])
        self.assertIn("x_primary_url", selected[0])

    def test_selector_is_deterministic_and_ranked(self):
        low = _item(Name="low", URL="https://example.com/low", **{"Decision Score": 65, "Screening Score": 60})
        high = _item(Name="high", URL="https://example.com/high", **{"Decision Score": 90, "Screening Score": 80})
        first = select_x_candidates([low, high], max_items=2)
        second = select_x_candidates([low, high], max_items=2)
        self.assertEqual([x["Name"] for x in first], ["high", "low"])
        self.assertEqual(first, second)

    def test_save_pending_post_writes_only_review_artifacts(self):
        draft = build_x_post(_item())
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            json_path, md_path = save_pending_post(draft, output_dir=output_dir, stem="sample")
            self.assertEqual(json_path, output_dir / "sample.json")
            self.assertEqual(md_path, output_dir / "sample.md")
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            self.assertIn("X Pending Review", md_path.read_text(encoding="utf-8"))
            self.assertIn('"x_api_calls": 0', json_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
