from __future__ import annotations

import ast
import inspect
import re
import unittest
from pathlib import Path

import fact_validation_signals as fact
import source_boundary_validation as boundary

ROOT = Path(__file__).resolve().parents[1]


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


class Run245FactValidationModuleTests(unittest.TestCase):
    def test_modules_are_provider_network_persistence_free(self):
        allowed = {
            "fact_validation_signals.py": {"__future__", "json", "re", "unicodedata"},
            "source_boundary_validation.py": {"__future__", "re"},
        }
        forbidden = {"requests", "google", "genai", "notion", "github", "os", "pathlib", "urllib", "httpx"}
        for filename, expected in allowed.items():
            tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imported.add((node.module or "").split(".")[0])
            self.assertTrue(imported <= expected, (filename, imported))
            self.assertTrue(imported.isdisjoint(forbidden), (filename, imported & forbidden))

    def test_numeric_normalization_preserves_historical_equivalences(self):
        self.assertEqual("1/40", fact._normalize_numeric_evidence_text("40分の1"))
        self.assertEqual("10hours", fact._normalize_numeric_evidence_text("10-hour"))
        self.assertEqual("50-80%", fact._normalize_numeric_evidence_text("50%-80%"))
        self.assertEqual("250ms", fact._normalize_numeric_evidence_text("250ミリ秒"))

    def test_numeric_condition_mismatch_remains_fail_closed(self):
        fact.bind_runtime(_numeric_claim_condition_tags=fact._numeric_claim_condition_tags)
        self.assertFalse(fact._numeric_condition_compatible("H100 latency 25ms", "A100 latency 25ms"))
        self.assertFalse(fact._numeric_condition_compatible("H100 memory 80GB", "H100 latency 80ms"))
        self.assertTrue(fact._numeric_condition_compatible("latency 25ms", "25ms"))

    def test_protocol_cardinality_exception_requires_structure_and_rejects_quota_cues(self):
        structural = "従来は1リクエスト・1レスポンスの単純な構成です。"
        token = "1リクエスト"
        start = structural.index(token)
        self.assertTrue(fact._is_protocol_cardinality_expression(structural, start, start + len(token), token))

        quota = "従来は上限1リクエスト・1レスポンスの単純な構成です。"
        start = quota.index(token)
        self.assertFalse(fact._is_protocol_cardinality_expression(quota, start, start + len(token), token))

    def test_hype_negation_is_sentence_scoped(self):
        text = "今すぐ全面移行することは推奨しません。別の段落では検証します。"
        start = text.index("今すぐ")
        self.assertTrue(fact._claim_is_negated(text, start, start + len("今すぐ")))
        other = "今すぐ全面移行できます。次の文では推奨しません。"
        start = other.index("今すぐ")
        self.assertFalse(fact._claim_is_negated(other, start, start + len("今すぐ")))

    def test_relation_entity_parser_does_not_promote_generic_nouns(self):
        fact.bind_runtime(_relation_family_for_predicate=fact._relation_family_for_predicate)
        self.assertFalse(fact._looks_like_relation_entity("開発体制"))
        claim = fact._extract_explicit_relation_claim("Timescale provides pgvector for PostgreSQL users.")
        self.assertTrue(claim is None or isinstance(claim, tuple))

    def test_alias_expansion_requires_real_token_presence(self):
        boundary.bind_runtime(
            _EVIDENCE_ALIAS_GROUPS=(("RAG", "Retrieval Augmented Generation"),),
            _normalized_evidence_text=_norm,
        )
        untouched = boundary._expand_evidence_aliases("storage system documentation")
        self.assertNotIn("Retrieval Augmented Generation", untouched)
        expanded = boundary._expand_evidence_aliases("RAG system documentation")
        self.assertIn("Retrieval Augmented Generation", expanded)

    def test_source_boundary_unknown_named_product_remains_blocked(self):
        boundary.bind_runtime(
            _EVIDENCE_ALIAS_GROUPS=(),
            _normalized_evidence_text=_norm,
            _normalized_named_fact=_norm,
            _expand_evidence_aliases=boundary._expand_evidence_aliases,
            classify_action_risk_tier=lambda _text: "HIGH",
        )
        failures = boundary._find_source_boundary_violations(
            "公式では PhantomCloud を提供しています。",
            "Official project documentation only.",
        )
        self.assertTrue(any("PhantomCloud" in item for item in failures), failures)

    def test_bind_runtime_rebinding_is_explicit_and_repeatable(self):
        boundary.bind_runtime(_EVIDENCE_ALIAS_GROUPS=(("AAA", "Alpha Alias"),), _normalized_evidence_text=_norm)
        self.assertIn("Alpha Alias", boundary._expand_evidence_aliases("AAA docs"))
        boundary.bind_runtime(_EVIDENCE_ALIAS_GROUPS=(("BBB", "Beta Alias"),), _normalized_evidence_text=_norm)
        self.assertNotIn("Alpha Alias", boundary._expand_evidence_aliases("AAA docs"))
        self.assertIn("Beta Alias", boundary._expand_evidence_aliases("BBB docs"))

    def test_canonical_owners_remain_substantive(self):
        self.assertGreater(len(inspect.getsource(fact._find_unsupported_numeric_claims).splitlines()), 50)
        self.assertGreater(len(inspect.getsource(fact._extract_explicit_relation_claim).splitlines()), 50)
        self.assertGreater(len(inspect.getsource(boundary._find_source_boundary_violations).splitlines()), 90)


if __name__ == "__main__":
    unittest.main()
