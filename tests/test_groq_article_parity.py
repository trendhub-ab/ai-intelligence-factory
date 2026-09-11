import json
import tempfile
import unittest
from pathlib import Path

import groq_article_parity as parity


class FakePipeline:
    def __init__(self):
        self.prompt_args = None
        self.gate_args = None

    def build_decision_prompt(self, *args, **kwargs):
        self.prompt_args = (args, kwargs)
        return "CURRENT_PRODUCTION_PROMPT::" + kwargs["source_context"]

    def _parse_gemini_response(self, text):
        return {"note_draft": "本文" * 300, "score": 82, "decision": "WATCH", "raw": text}

    def validate_publication_readiness_gate(self, parsed, source_context="", source_info=None):
        self.gate_args = (parsed, source_context, source_info)
        return "PASS", []


class GroqArticleParityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Path("tests/fixtures/groq/article_parity_B0049_input.json")
        self.assertTrue(self.fixture.exists())

    def test_build_uses_current_production_prompt_builder(self):
        fake = FakePipeline()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "article.json"
            payload = parity.build_production_article_fixture(fake, str(self.fixture), str(out))
            self.assertEqual(payload["stage"], "article")
            self.assertIn("CURRENT_PRODUCTION_PROMPT", payload["prompt"])
            self.assertEqual(payload["provenance"]["business_writes"], 0)
            self.assertEqual(payload["provenance"]["production_prompt_builder"], "pipeline.build_decision_prompt")
            self.assertEqual(fake.prompt_args[0][0], "Path to Astra: critical capabilities and frontier safeguards")
            self.assertEqual(fake.prompt_args[0][5], "HackerNews")
            self.assertTrue(out.exists())

    def test_evaluation_uses_current_parser_and_publication_gate(self):
        fake = FakePipeline()
        with tempfile.TemporaryDirectory() as td:
            report = Path(td) / "groq.json"
            report.write_text(json.dumps({
                "provider": "groq", "model": "openai/gpt-oss-120b", "provider_calls": 1,
                "result": {"text": "MODEL_OUTPUT", "prompt_tokens": 100, "completion_tokens": 200}
            }), encoding="utf-8")
            out = Path(td) / "evaluation.json"
            evaluation = parity.evaluate_groq_article_output(fake, str(report), str(self.fixture), str(out))
            self.assertEqual(evaluation["gate_state"], "PASS")
            self.assertTrue(evaluation["quality_validated"])
            self.assertEqual(evaluation["business_writes"], 0)
            self.assertFalse(evaluation["persist_results"])
            self.assertEqual(fake.gate_args[1], parity.load_input(str(self.fixture))["source_context"])

    def test_missing_primary_context_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad.json"
            data = parity.load_input(str(self.fixture))
            data["source_context"] = ""
            bad.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                parity.load_input(str(bad))


if __name__ == "__main__":
    unittest.main()
