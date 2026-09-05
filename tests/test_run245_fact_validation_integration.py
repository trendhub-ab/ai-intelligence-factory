from __future__ import annotations

import inspect
import os
import unittest
from pathlib import Path

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GH_PAT", "test-token")
os.environ.setdefault("GEMINI_QUOTA_PROJECT_ID", "test-project")

import fact_validation_signals as fact
import pipeline
import source_boundary_validation as boundary

ROOT = Path(__file__).resolve().parents[1]


class Run245FactValidationIntegrationTests(unittest.TestCase):
    def test_pipeline_wrappers_are_thin_and_heavy_bodies_left_pipeline(self):
        names = (
            "_find_unsupported_numeric_claims",
            "_find_hype_claims",
            "_find_false_negative_evidence_claims",
            "_find_unsupported_competitor_claims",
            "_extract_explicit_relation_claim",
            "_find_entity_relation_violations",
            "_expand_evidence_aliases",
            "_find_source_boundary_violations",
        )
        for name in names:
            src = inspect.getsource(getattr(pipeline, name))
            self.assertLessEqual(len(src.splitlines()), 4, (name, src))
            self.assertIn("_impl", src, (name, src))

    def test_numeric_wrapper_reads_live_pattern_constants(self):
        old_sensitive = pipeline._SENSITIVE_NUMERIC_PATTERNS
        old_vague = pipeline._VAGUE_QUANTIFIED_PATTERNS
        try:
            pipeline._SENSITIVE_NUMERIC_PATTERNS = (r"999",)
            pipeline._VAGUE_QUANTIFIED_PATTERNS = ()
            failures = pipeline._find_unsupported_numeric_claims("処理値は999です。", "一次情報に値の記載はありません。")
            self.assertTrue(any("999" in item for item in failures), failures)
            pipeline._SENSITIVE_NUMERIC_PATTERNS = ()
            self.assertEqual([], pipeline._find_unsupported_numeric_claims("処理値は999です。", "一次情報に値の記載はありません。"))
        finally:
            pipeline._SENSITIVE_NUMERIC_PATTERNS = old_sensitive
            pipeline._VAGUE_QUANTIFIED_PATTERNS = old_vague

    def test_alias_wrapper_reads_live_alias_groups(self):
        old = pipeline._EVIDENCE_ALIAS_GROUPS
        try:
            pipeline._EVIDENCE_ALIAS_GROUPS = (("XYZ", "Expanded XYZ"),)
            self.assertIn("Expanded XYZ", pipeline._expand_evidence_aliases("XYZ docs"))
            pipeline._EVIDENCE_ALIAS_GROUPS = (("ABC", "Expanded ABC"),)
            self.assertNotIn("Expanded XYZ", pipeline._expand_evidence_aliases("XYZ docs"))
        finally:
            pipeline._EVIDENCE_ALIAS_GROUPS = old

    def test_source_boundary_wrapper_reads_live_action_risk_classifier(self):
        old = pipeline.classify_action_risk_tier
        old_alias = pipeline._EVIDENCE_ALIAS_GROUPS
        try:
            pipeline._EVIDENCE_ALIAS_GROUPS = ()
            sentence = "私なら提供された Cargo.lock を監査します。"
            pipeline.classify_action_risk_tier = lambda _text: "LOW"
            low = pipeline._find_source_boundary_violations(sentence, "Official project documentation.")
            self.assertEqual([], low)
            pipeline.classify_action_risk_tier = lambda _text: "HIGH"
            high = pipeline._find_source_boundary_violations(sentence, "Official project documentation.")
            self.assertTrue(any("Cargo.lock" in item for item in high), high)
        finally:
            pipeline.classify_action_risk_tier = old
            pipeline._EVIDENCE_ALIAS_GROUPS = old_alias

    def test_wrapper_results_match_canonical_module_after_live_binding(self):
        text = "従来は1リクエスト・1レスポンスの単純な構成です。"
        token = "1リクエスト"
        start = text.index(token)
        via_pipeline = pipeline._is_protocol_cardinality_expression(text, start, start + len(token), token)
        pipeline._bind_run245_fact_runtime()
        via_module = fact._is_protocol_cardinality_expression(text, start, start + len(token), token)
        self.assertEqual(via_module, via_pipeline)

        pipeline._bind_run245_boundary_runtime()
        self.assertEqual(
            boundary._expand_evidence_aliases("MCP documentation"),
            pipeline._expand_evidence_aliases("MCP documentation"),
        )

    def test_side_effectful_boundary_and_gate_owners_remain_in_pipeline(self):
        pipeline_src = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        for name in (
            "_fetch_boundary_html",
            "_discover_boundary_candidate_urls",
            "reconcile_product_review_source_boundary",
            "validate_fact_gate",
        ):
            self.assertIn(f"def {name}", pipeline_src, name)
        new_src = (ROOT / "fact_validation_signals.py").read_text(encoding="utf-8") + (ROOT / "source_boundary_validation.py").read_text(encoding="utf-8")
        for forbidden in ("requests.get", "requests.post", "genai.Client", "notion", "GEMINI_API_KEY", "GH_PAT"):
            self.assertNotIn(forbidden, new_src)

    def test_pipeline_line_count_is_below_run244_baseline(self):
        lines = len((ROOT / "pipeline.py").read_text(encoding="utf-8").splitlines())
        self.assertEqual(9978, lines)
        self.assertLess(lines, 10434)


if __name__ == "__main__":
    unittest.main()
