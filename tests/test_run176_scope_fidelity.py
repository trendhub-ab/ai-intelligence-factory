import inspect
import types
import unittest
from unittest.mock import MagicMock

import production_pipeline
import run176_scope_fidelity as run176


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


class Run176ScopeFidelityTests(unittest.TestCase):
    def test_run175_nat_attribution_failure_is_blocked(self):
        article = (
            "そこで1994年、RFC 1631という文書で『本格的な新しい仕組み（IPv6）ができるまでの、"
            "一時的な住所節約術』としてNATが提案されました。"
        )
        source = (
            "RFC 1631 Network Address Translator May 1994. The long-term solutions consist of various "
            "proposals for new internet protocols with larger addresses. NAT can provide temporary relief."
        )
        failures = run176.historical_source_attribution_failures(article, source)
        self.assertTrue(any(x.startswith("historical_source_attribution_drift:") for x in failures), failures)

    def test_retrospective_protocol_mapping_is_allowed(self):
        article = (
            "RFC 1631は長期策を具体名では示していません。後にIPv6へつながる、"
            "より大きなアドレスを持つ新プロトコル群を想定していました。"
        )
        source = (
            "RFC 1631. The long-term solutions consist of various proposals for new internet protocols "
            "with larger addresses."
        )
        self.assertEqual([], run176.historical_source_attribution_failures(article, source))

    def test_protocol_name_present_in_rfc_local_evidence_is_allowed(self):
        article = "RFC 8200ではIPv6の基本仕様が定義されています。"
        source = "RFC 8200 Internet Protocol, Version 6 (IPv6) Specification."
        self.assertEqual([], run176.historical_source_attribution_failures(article, source))

    def test_unrelated_protocol_mention_without_rfc_attribution_is_allowed(self):
        article = "現在のIPv6ネットワークではNATなしの設計も可能です。"
        source = "RFC 1631 discusses address reuse while long-term protocols are developed."
        self.assertEqual([], run176.historical_source_attribution_failures(article, source))

    def test_run175_percolation_practical_guarantee_is_blocked(self):
        article = "分散システムやネットワークの耐障害性、拡散モデルの理論的基礎の正しさが担保された。"
        source = (
            "Mathematicians completed a proof of the supercritical sharpness conjecture for all infinite "
            "transitive graphs in percolation theory. The theorem is a pure mathematical result."
        )
        failures = run176.theory_to_practice_failures(article, source)
        self.assertTrue(any(x.startswith("theory_to_practice_overclaim:") for x in failures), failures)

    def test_theoretical_claim_about_theorem_itself_is_allowed(self):
        article = "この定理により、全無限推移的グラフで超臨界側の鋭さが証明されました。"
        source = "The proof establishes supercritical sharpness for all infinite transitive graphs."
        self.assertEqual([], run176.theory_to_practice_failures(article, source))

    def test_caveated_practical_relevance_is_allowed(self):
        article = "分散システムへの直接の実務効果は未検証ですが、理論モデルを見直す参考になる可能性があります。"
        source = "A mathematical proof establishes sharpness for infinite transitive graphs."
        self.assertEqual([], run176.theory_to_practice_failures(article, source))

    def test_empirical_practical_validation_disables_theory_only_guard(self):
        article = "実システムの性能が保証された。"
        source = (
            "The theorem motivates the method. A real-world evaluation then measured the system in production; "
            "the system was deployed in production and evaluated separately."
        )
        self.assertEqual([], run176.theory_to_practice_failures(article, source))

    def test_wrapper_preserves_existing_failure_and_adds_run176_failure(self):
        p = fake_pipeline(validate_fact_gate=lambda *a, **k: (False, ["existing_fact_failure"]))
        run176.install(p)
        parsed = {"note_draft": "分散システムの耐障害性の正しさが担保された。"}
        ok, failures = p.validate_fact_gate(
            parsed,
            "percolation",
            source_context="A mathematical theorem and proof about percolation on transitive graphs.",
        )
        self.assertFalse(ok)
        self.assertIn("existing_fact_failure", failures)
        self.assertTrue(any(x.startswith("theory_to_practice_overclaim:") for x in failures), failures)

    def test_prompt_adds_all_three_scope_boundaries(self):
        p = fake_pipeline()
        run176.install(p)
        prompt = p.build_decision_prompt()
        self.assertIn("出典時点", prompt)
        self.assertIn("理論→実務", prompt)
        self.assertIn("筆者は〜と論じている", prompt)

    def test_retry_is_local_and_does_not_request_new_facts(self):
        p = fake_pipeline()
        run176.install(p)
        instruction, sections = p.build_dynamic_retry_instruction([
            {"message": "historical_source_attribution_drift: RFC 1631 / IPv6"},
            {"message": "theory_to_practice_overclaim: practical guarantee"},
        ])
        self.assertIn("Run176 Scope Fidelity Patch", instruction)
        self.assertIn("該当文だけ", instruction)
        self.assertIn("新しい事実は追加しない", instruction)
        self.assertIn("実務影響は未検証", instruction)
        self.assertEqual({"article"}, sections)

    def test_install_is_idempotent(self):
        p = fake_pipeline()
        run176.install(p)
        first = p.validate_fact_gate
        run176.install(p)
        self.assertIs(first, p.validate_fact_gate)

    def test_production_entrypoint_installs_run176_after_run175_before_reader_bridge(self):
        src = inspect.getsource(production_pipeline.install_runtime_layers)
        # This assertion becomes active once the production entrypoint is updated in this change set.
        self.assertIn("run176_scope_fidelity.install", src)
        self.assertLess(src.index("run175_semantic_fact_precision.install"), src.index("run176_scope_fidelity.install"))
        self.assertLess(src.index("run176_scope_fidelity.install"), src.index("reader_value_review_bridge.install"))


if __name__ == "__main__":
    unittest.main()
