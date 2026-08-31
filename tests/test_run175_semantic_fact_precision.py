import inspect
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import production_pipeline
import run175_semantic_fact_precision as run175


def fake_pipeline(**overrides):
    ns = types.SimpleNamespace(
        build_decision_prompt=lambda *a, **k: "BASE PROMPT",
        validate_fact_gate=lambda parsed, repo_name, source_context="", source="", evidence_metadata=None,
                                  source_info=None, freshness=None, output_truncated=False: (True, []),
        build_dynamic_retry_instruction=lambda rows: ("BASE RETRY", {"article"}),
        logger=MagicMock(),
    )
    for key, value in overrides.items():
        setattr(ns, key, value)
    return ns


class Run175SemanticFactPrecisionTests(unittest.TestCase):
    def test_probability_similarity_mismatch_is_blocked_without_source_support(self):
        article = "# Semantic Router\n\nベクトル空間上の距離計算（確率的な類似度）でルートを選びます。"
        source = "Routing uses semantic vector space, cosine similarity, a score threshold, and route scores."
        failures = run175.semantic_category_failures(article, source)
        self.assertTrue(any(x.startswith("semantic_category_mismatch:") for x in failures), failures)

    def test_explicit_probabilistic_similarity_in_primary_evidence_is_allowed(self):
        article = "# Research Model\n\nこの方式は確率的な類似度を推定します。"
        source = "The paper defines a probabilistic similarity score and calibrates it against observed labels."
        self.assertEqual([], run175.semantic_category_failures(article, source))

    def test_normal_cosine_similarity_is_not_false_positive(self):
        article = "# Router\n\n埋め込みベクトルのコサイン類似度を計算し、閾値と比較します。"
        source = "The router compares cosine similarity with a score threshold."
        self.assertEqual([], run175.semantic_category_failures(article, source))

    def test_unqualified_4ms_headline_is_blocked_when_source_is_comparison_example(self):
        article = "# LLMを待たずに4ミリ秒で分岐する。Semantic Routerの高速化。\n\n本文です。"
        source = (
            "DECISION TIME. Three orders of magnitude faster, every turn. "
            "CLAUDE OPUS 5 3,860ms. SEMANTIC ROUTER 4ms. "
            "Opus 5 figure: 3.86s time-to-first-token in a first-party API comparison."
        )
        failures = run175.benchmark_scope_failures(article, source)
        self.assertTrue(any(x.startswith("benchmark_scope_overgeneralized:") for x in failures), failures)

    def test_qualified_benchmark_headline_is_allowed(self):
        article = "# 公式比較では4ミリ秒。Semantic Routerの高速化。\n\n本文です。"
        source = "Comparison figure: Semantic Router 4ms versus Claude Opus 5 3,860ms."
        self.assertEqual([], run175.benchmark_scope_failures(article, source))

    def test_same_number_without_benchmark_context_is_not_hard_blocked(self):
        article = "# 4ミリ秒で応答する専用ハードウェア\n\n本文です。"
        source = "The hardware specification states a response latency of 4ms under its documented operating mode."
        self.assertEqual([], run175.benchmark_scope_failures(article, source))

    def test_fact_wrapper_preserves_existing_failure_and_adds_run175_failure(self):
        p = fake_pipeline(
            validate_fact_gate=lambda *a, **k: (False, ["existing_fact_failure"]),
        )
        run175.install(p)
        parsed = {"note_draft": "# Router\n\n確率的な類似度で経路を決めます。"}
        ok, failures = p.validate_fact_gate(parsed, "router", source_context="cosine similarity and threshold")
        self.assertFalse(ok)
        self.assertIn("existing_fact_failure", failures)
        self.assertTrue(any(x.startswith("semantic_category_mismatch:") for x in failures), failures)

    def test_prompt_prevents_category_drift_and_benchmark_generalization(self):
        p = fake_pipeline()
        run175.install(p)
        prompt = p.build_decision_prompt()
        self.assertIn("確率的な類似度", prompt)
        self.assertIn("ベンチマーク", prompt)
        self.assertIn("一般的な保証", prompt)

    def test_retry_adds_only_targeted_semantic_patch_instruction(self):
        p = fake_pipeline()
        run175.install(p)
        instruction, sections = p.build_dynamic_retry_instruction([
            {"message": "semantic_category_mismatch: unsupported probability label"}
        ])
        self.assertIn("Run175 Semantic Fact Patch", instruction)
        self.assertIn("該当文だけ", instruction)
        self.assertIn("similarity/distance/score/threshold", instruction)
        self.assertEqual({"article"}, sections)

    def test_retry_adds_only_targeted_benchmark_scope_instruction(self):
        p = fake_pipeline()
        run175.install(p)
        instruction, _ = p.build_dynamic_retry_instruction([
            {"message": "benchmark_scope_overgeneralized: 4ms is a comparison value"}
        ])
        self.assertIn("公式例では", instruction)
        self.assertIn("保証表現", instruction)

    def test_install_is_idempotent(self):
        p = fake_pipeline()
        run175.install(p)
        first = p.validate_fact_gate
        run175.install(p)
        self.assertIs(first, p.validate_fact_gate)

    def test_production_entrypoint_installs_run175_before_reader_bridge(self):
        src = inspect.getsource(production_pipeline.install_runtime_layers)
        self.assertIn("run175_semantic_fact_precision.install", src)
        self.assertLess(src.index("run175_semantic_fact_precision.install"), src.index("reader_value_review_bridge.install"))

    def test_safe_one_shot_workflow_never_uses_automatic_trigger(self):
        workflow = Path(".github/workflows/daily-one-shot.yml")
        if not workflow.exists():
            self.skipTest("workflow is added in the same Run175 change set")
        text = workflow.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("\n  push:", text)
        self.assertNotIn("\n  schedule:", text)
        self.assertIn("RUN_ONCE", text)
        self.assertIn("ai-intelligence-gemini-budget", text)


if __name__ == "__main__":
    unittest.main()
