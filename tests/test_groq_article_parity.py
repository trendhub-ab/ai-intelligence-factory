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
    EVIDENCE_SUFFICIENT = "SUFFICIENT"
    GATE_DISPOSITION_PASS = "PASS"
    GATE_DISPOSITION_PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"

    def __init__(self, publication_state="PASS", publication_issues=None, fact_failures=None):
        self.prompt_args = None
        self.gate_args = None
        self.publication_state = publication_state
        self.publication_issues = [] if publication_issues is None else publication_issues
        self.fact_failures = [] if fact_failures is None else fact_failures
        self.evidence_source_info = None

    def _build_evidence_metadata(self, context, deep_source_scanned):
        return {"coverage": {"method": "FOUND"}, "context_seen": context, "deep": deep_source_scanned}

    def assess_evidence_sufficiency(self, source_info):
        self.evidence_source_info = dict(source_info)
        state = self.EVIDENCE_SUFFICIENT if source_info.get("primary_source_resolved") else "INSUFFICIENT"
        return {"state": state, "decision_scope_safe": state == self.EVIDENCE_SUFFICIENT,
                "checks": {"primary_source_resolved": bool(source_info.get("primary_source_resolved"))}}

    def build_decision_prompt(self, *args, **kwargs):
        self.prompt_args = (args, kwargs)
        return canonical_test_prompt(kwargs["source_context"])

    def _parse_gemini_response(self, text):
        return {"note_draft": "本文 WATCH " * 100, "score": 82, "decision": "WATCH", "raw": text}

    def _apply_final_japanese_polish(self, parsed):
        out = dict(parsed)
        out["note_draft"] = out["note_draft"].replace("WATCH", "今後の動きを注視する")
        return out, ["decision_code:WATCH"]

    def _apply_deterministic_structure_polish(self, parsed):
        return dict(parsed), []

    def validate_fact_gate(self, *args, **kwargs):
        return not self.fact_failures, list(self.fact_failures)

    def validate_editorial_gate(self, parsed, name):
        return True, []

    def validate_publication_readiness_gate(self, parsed, source_context="", source_info=None):
        self.gate_args = (parsed, source_context, source_info)
        if not source_info.get("sufficient"):
            return "REVIEW", ["primary_evidence_insufficient"]
        return self.publication_state, list(self.publication_issues)

    def validate_human_appeal_gate(self, parsed, peer_articles):
        return "ACCEPTABLE", []

    def map_gate_reasons(self, gate, issues):
        return [{"gate": gate, "message": issue, "severity": "HARD"} for issue in issues]

    def gate_reason_disposition(self, rows):
        return "BLOCK" if rows else self.GATE_DISPOSITION_PASS


class GroqArticleParityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Path("tests/fixtures/groq/article_parity_B0049_input.json")
        self.assertTrue(self.fixture.exists())

    def _report(self, path):
        path.write_text(json.dumps({
            "provider": "groq", "model": "groq/compound-mini", "provider_calls": 1,
            "result": {"text": "MODEL_OUTPUT", "prompt_tokens": 100, "completion_tokens": 200}
        }), encoding="utf-8")

    def test_build_uses_current_production_prompt_and_computed_evidence(self):
        fake = FakePipeline()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "article.json"
            payload = parity.build_production_article_fixture(fake, str(self.fixture), str(out))
            self.assertEqual(payload["stage"], "article")
            self.assertIn("CURRENT_PRODUCTION_PROMPT", payload["prompt"])
            self.assertTrue(payload["provenance"]["evidence_sufficient"])
            self.assertEqual(payload["provenance"]["business_writes"], 0)
            self.assertEqual(payload["provenance"]["production_prompt_builder"], "pipeline.build_decision_prompt")
            self.assertEqual(payload["provenance"]["transport_compiler"], "groq_prompt_compiler.compile_article_prompt")
            self.assertLess(payload["provenance"]["compiled_prompt_bytes"], payload["provenance"]["canonical_prompt_bytes"])
            self.assertLessEqual(payload["provenance"]["compiled_prompt_bytes"], MAX_COMPILED_PROMPT_BYTES)
            self.assertEqual(fake.prompt_args[0][0], "Path to Astra: critical capabilities and frontier safeguards")
            self.assertTrue(fake.prompt_args[1]["evidence_result"]["decision_scope_safe"])
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

    def test_evaluation_computes_sufficiency_runs_polish_and_all_four_gates(self):
        fake = FakePipeline()
        with tempfile.TemporaryDirectory() as td:
            report = Path(td) / "groq.json"; self._report(report)
            out = Path(td) / "evaluation.json"
            evaluation = parity.evaluate_groq_article_output(fake, str(report), str(self.fixture), str(out))
            self.assertTrue(evaluation["evidence_sufficient"])
            self.assertTrue(fake.gate_args[2]["sufficient"])
            self.assertIn("decision_code:WATCH", evaluation["polish_changes"])
            self.assertTrue(evaluation["fact_ok"])
            self.assertEqual(evaluation["publication_state"], "PASS")
            self.assertEqual(evaluation["human_appeal_state"], "ACCEPTABLE")
            self.assertTrue(evaluation["quality_validated"])
            self.assertEqual(evaluation["business_writes"], 0)
            self.assertFalse(evaluation["persist_results"])

    def test_fact_failure_cannot_be_mislabeled_quality_validated(self):
        fake = FakePipeline(fact_failures=["unsupported claim"])
        with tempfile.TemporaryDirectory() as td:
            report = Path(td) / "groq.json"; self._report(report)
            evaluation = parity.evaluate_groq_article_output(fake, str(report), str(self.fixture), str(Path(td) / "evaluation.json"))
            self.assertFalse(evaluation["quality_validated"])
            self.assertEqual(evaluation["gate_disposition"], "BLOCK")

    def test_publication_issue_cannot_be_mislabeled_quality_validated(self):
        fake = FakePipeline(publication_state="REVIEW", publication_issues=["reader_issue"])
        with tempfile.TemporaryDirectory() as td:
            report = Path(td) / "groq.json"; self._report(report)
            evaluation = parity.evaluate_groq_article_output(fake, str(report), str(self.fixture), str(Path(td) / "evaluation.json"))
            self.assertFalse(evaluation["quality_validated"])

    def test_missing_primary_context_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad.json"
            data = parity.load_input(str(self.fixture)); data["source_context"] = ""
            bad.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                parity.load_input(str(bad))


if __name__ == "__main__":
    unittest.main()
