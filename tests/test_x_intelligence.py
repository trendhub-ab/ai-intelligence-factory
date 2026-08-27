import csv
import json
import tempfile
import unittest
from pathlib import Path

from x_intelligence import (
    build_x_post,
    build_x_variants,
    generate_batch,
    load_records,
    save_pending_post,
    select_x_candidates,
)


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
        self.assertEqual(draft["variant"], "breaking")
        self.assertEqual(draft["gemini_calls"], 0)
        self.assertEqual(draft["x_api_calls"], 0)
        self.assertFalse(draft["auto_posted"])
        self.assertEqual(draft["generator_mode"], "deterministic_zero_api")

    def test_build_x_variants_returns_three_distinct_human_choices(self):
        variants = build_x_variants(_item(**{"portfolio_topic": "AGENT"}))
        self.assertEqual(set(variants), {"breaking", "curiosity", "decision"})
        self.assertIn("【速報｜AIエージェント】", variants["breaking"]["post"])
        self.assertIn("地味に大きな変化", variants["curiosity"]["post"])
        self.assertIn("【実務判断｜AIエージェント】", variants["decision"]["post"])
        for draft in variants.values():
            self.assertLessEqual(draft["characters"], 280)
            self.assertEqual(draft["gemini_calls"], 0)
            self.assertEqual(draft["x_api_calls"], 0)

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
        self.assertIn("一次情報", draft["post"])

    def test_build_x_post_uses_existing_japanese_summary_as_hook(self):
        item = _item(
            Name="The New MCP Roadmap",
            **{
                "Source Summary": "MCPの標準ロードマップ策定で実務影響大",
                "portfolio_topic": "AGENT",
            },
        )
        draft = build_x_post(item)
        self.assertTrue(draft["post"].startswith("【速報｜AIエージェント】MCPの標準ロードマップ策定で実務影響大"))

    def test_build_x_post_strips_producthunt_tracking_query(self):
        item = _item(URL="https://www.producthunt.com/r/ABC123?utm_campaign=x&utm_medium=api&foo=bar")
        draft = build_x_post(item)
        self.assertEqual(draft["primary_url"], "https://www.producthunt.com/r/ABC123")

    def test_build_x_post_preserves_functional_youtube_query(self):
        item = _item(URL="https://www.youtube.com/watch?v=abc123&utm_source=test")
        draft = build_x_post(item)
        self.assertEqual(draft["primary_url"], "https://www.youtube.com/watch?v=abc123")
        self.assertIn("?v=abc123", draft["post"])

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

    def test_screening_only_x_ranking_can_surface_high_audience_interest(self):
        high_engagement = {
            "name": "audience",
            "url": "https://example.com/audience",
            "final_screening_score": 62,
            "commercial_value_score": 52,
            "engagement": 580,
            "shelf_life": "TREND",
        }
        high_screening = {
            "name": "quality",
            "url": "https://example.com/quality",
            "final_screening_score": 78,
            "commercial_value_score": 72,
            "engagement": 14,
            "shelf_life": "EVERGREEN",
        }
        selected = select_x_candidates([high_screening, high_engagement], max_items=2)
        self.assertEqual(selected[0]["name"], "audience")

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

    def test_load_records_accepts_wrapped_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "factory.json"
            path.write_text(json.dumps({"items": [_item()]}, ensure_ascii=False), encoding="utf-8")
            records = load_records(path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["Decision Score"], 81)

    def test_load_records_accepts_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "factory.csv"
            row = _item()
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
                writer.writeheader()
                writer.writerow(row)
            records = load_records(path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["URL"], row["URL"])

    def test_generate_batch_outputs_three_variants_for_top_five(self):
        records = [
            _item(Name=f"candidate-{i}", URL=f"https://example.com/{i}", **{"Decision Score": 95 - i, "Screening Score": 80 - i})
            for i in range(8)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "pending"
            manifest = generate_batch(records, output_dir=output_dir, max_items=5)

            self.assertEqual(manifest["input_records"], 8)
            self.assertEqual(manifest["generated_candidates"], 5)
            self.assertEqual(manifest["variants_per_candidate"], 3)
            self.assertEqual(manifest["generated_drafts"], 15)
            self.assertEqual(manifest["gemini_calls"], 0)
            self.assertEqual(manifest["x_api_calls"], 0)
            self.assertFalse(manifest["auto_posted"])
            self.assertEqual(len(manifest["candidates"]), 5)
            self.assertTrue((output_dir / "manifest.json").exists())
            self.assertEqual(len(list(output_dir.glob("*-COMPARE.md"))), 5)
            self.assertEqual(len(list(output_dir.glob("*.json"))), 16)

    def test_generate_batch_skips_weak_or_url_less_records(self):
        records = [
            _item(Name="strong"),
            _item(Name="weak", URL="https://example.com/weak", **{"Decision Score": 10, "Screening Score": 10}),
            _item(Name="missing-url", URL="", **{"Decision Score": 99, "Screening Score": 99}),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            manifest = generate_batch(records, output_dir=tmp, max_items=5)
            self.assertEqual(manifest["generated_candidates"], 1)
            self.assertEqual(manifest["generated_drafts"], 3)
            self.assertEqual(manifest["candidates"][0]["name"], "strong")


if __name__ == "__main__":
    unittest.main()
