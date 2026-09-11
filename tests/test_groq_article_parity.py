import json
import tempfile
import unittest
from pathlib import Path

import groq_article_parity as parity
from groq_prompt_compiler import MAX_COMPILED_PROMPT_BYTES, PromptCompileError, compile_article_prompt


def canonical_test_prompt(source_context="PRIMARY FACT"):
    verbose = "説明を繰り返す。" * 300
    return f"""CURRENT_PRODUCTION_PROMPT
【SOURCE BOUNDARY — 最重要】
一次情報を越えない。
【全ソース共通 Fact Discipline】
事実と推論を分ける。
【Human Editorial Style｜最重要】
{verbose}
【Reader Experience｜知的エンタメ × Decision Intelligence】
{verbose}
【出典時点と理論→実務の境界 / Run176】
{verbose}
【実行優先順位】
{verbose}
【ARTICLEの追加ルール】
{verbose}
【Production Yield Consistency Contract｜最終セルフチェック】
{verbose}
【Source Native Context】
{source_context}
【Structured Evidence / Required Qualifiers — 最優先】
required_qualifiers を削除しない。Evidenceを守る。
【Freshness Resolution】
時点を守る。
=== MANAGEMENT DATA ===
・Decision Score: 80/100
SECTION_SPLIT_TOKEN
ARTICLE
"""


class FakePipeline:
    def __init__(self, gate_state="PASS", gate_issues=None):
        self.prompt_args = None
        self.gate_args = None
        self.gate_state = gate_state
        self.gate_issues = [] if gate_issues is None else gate_issues

    def build_decision_prompt(self, *args, **kwargs):
        self.prompt_args = (args, kwargs)
        return canonical_test_prompt(kwargs["source_context"])

    def _parse_gemini_response(self, text):
        return {"note_draft": "本文" * 300, "score": 82, "decision": "WATCH", "raw": text}

    def validate_publication_readiness_gate(self, parsed, source_context="", source_info=None):
        self.gate_args = (parsed, source_context, source_info)
        return self.gate_state, self.gate_issues


class GroqArticleParityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Path("tests/fixtures/groq/article_parity_B0049_input.json")
        self.assertTrue(self.fixture.exists())

    def test_build_uses_current_production_prompt_builder_then_compiles_transport_copy(self):
        fake = FakePipeline()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "article.json"
            payload = parity.build_production_article_fixture(fake, str(self.fixture), str(out))
            self.assertEqual(payload["stage"], "article")
            self.assertIn("CURRENT_PRODUCTION_PROMPT", payload["prompt"])
            self.assertEqual(payload["provenance"]["business_writes"], 0)
            self.assertEqual(payload["provenance"]["production_prompt_builder"], "pipeline.build_decision_prompt")
            self.assertEqual(payload["provenance"]["transport_compiler"], "groq_prompt_compiler.compile_article_prompt")
            self.assertLess(payload["provenance"]["compiled_prompt_bytes"], payload["provenance"]["canonical_prompt_bytes"])
            self.assertLessEqual(payload["provenance"]["compiled_prompt_bytes"], MAX_COMPILED_PROMPT_BYTES)
            self.assertEqual(fake.prompt_args[0][0], "Path to Astra: critical capabilities and frontier safeguards")
            self.assertEqual(fake.prompt_args[0][5], "HackerNews")
            self.assertTrue(out.exists())

    def test_compiler_preserves_evidence_contract_and_fails_on_drift(self):
        source = canonical_test_prompt("UNIQUE_SOURCE_CONTEXT_123")
        result = compile_article_prompt(source)
        self.assertIn("UNIQUE_SOURCE_CONTEXT_123", result.prompt)
        self.assertIn("【SOURCE BOUNDARY — 最重要】", result.prompt)
        self.assertIn("【Structured Evidence / Required Qualifiers — 最優先】", result.prompt)
        self.assertIn("required_qualifiers", result.prompt)
        self.assertEqual(len(result.replaced_sections), 6)
        with self.assertRaises(PromptCompileError):
            compile_article_prompt(source.replace("【SOURCE BOUNDARY — 最重要】", "【SOURCE BOUNDARY】"))

    def test_evaluation_uses_current_parser_and_publication_gate(self):
        fake = FakePipeline()
        with tempfile.TemporaryDirectory() as td:
            report = Path(td) / "groq.json"
            report.write_text(json.dumps({
                "provider": "groq", "model": "groq/compound-mini", "provider_calls": 1,
                "result": {"text": "MODEL_OUTPUT", "prompt_tokens": 100, "completion_tokens": 200}
            }), encoding="utf-8")
            out = Path(td) / "evaluation.json"
            evaluation = parity.evaluate_groq_article_output(fake, str(report), str(self.fixture), str(out))
            self.assertEqual(evaluation["gate_state"], "PASS")
            self.assertTrue(evaluation["quality_validated"])
            self.assertEqual(evaluation["business_writes"], 0)
            self.assertFalse(evaluation["persist_results"])
            self.assertEqual(fake.gate_args[1], parity.load_input(str(self.fixture))["source_context"])

    def test_gate_issue_cannot_be_mislabeled_quality_validated(self):
        fake = FakePipeline(gate_state="PASS", gate_issues=["reader_issue"])
        with tempfile.TemporaryDirectory() as td:
            report = Path(td) / "groq.json"
            report.write_text(json.dumps({
                "provider": "groq", "model": "groq/compound-mini", "provider_calls": 1,
                "result": {"text": "MODEL_OUTPUT", "prompt_tokens": 100, "completion_tokens": 200}
            }), encoding="utf-8")
            out = Path(td) / "evaluation.json"
            evaluation = parity.evaluate_groq_article_output(fake, str(report), str(self.fixture), str(out))
            self.assertFalse(evaluation["quality_validated"])

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
