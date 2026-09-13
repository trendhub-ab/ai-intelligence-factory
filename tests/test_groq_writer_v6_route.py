import json
import tempfile
import unittest
from pathlib import Path

from groq_writer_v6_route import (
    WRITER_MAX_OUTPUT_TOKENS,
    WRITER_SAFE_TPM,
    preflight_writer_fixture,
    route_writer_fixture,
)


def fixture():
    return {
        "stage": "article",
        "provider": "groq",
        "model": "groq/compound-mini",
        "rate_policy": "compound_mini_article",
        "prompt": "日本語の記事本文だけを書く。" * 180,
        "max_output_tokens": 3200,
        "reasoning_effort": "medium",
        "schema": None,
        "business_writes": 0,
    }


class GroqWriterV6RouteTests(unittest.TestCase):
    def test_compact_writer_routes_to_gpt_oss_and_fits_safe_tpm(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "writer.json"
            path.write_text(json.dumps(fixture(), ensure_ascii=False), encoding="utf-8")
            routed = route_writer_fixture(str(path))
            self.assertEqual(routed["model"], "openai/gpt-oss-120b")
            self.assertEqual(routed["rate_policy"], "gpt_oss_120b")
            self.assertEqual(routed["max_output_tokens"], WRITER_MAX_OUTPUT_TOKENS)
            report = preflight_writer_fixture(str(path))
            self.assertLessEqual(report["reserved_estimate"], WRITER_SAFE_TPM)
            self.assertGreater(report["headroom"], 0)

    def test_route_preserves_prompt_and_zero_writes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "writer.json"
            original = fixture()
            path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
            routed = route_writer_fixture(str(path))
            self.assertEqual(routed["prompt"], original["prompt"])
            self.assertEqual(routed["business_writes"], 0)
            self.assertIsNone(routed["schema"])


if __name__ == "__main__":
    unittest.main()
