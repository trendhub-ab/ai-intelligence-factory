import unittest
from pathlib import Path

from local_skills import a_plus


ROOT = Path(__file__).resolve().parents[1]


class APlusEditorialOrchestrationTests(unittest.TestCase):
    def _parsed(self):
        return {
            "source_summary_text": "公式資料で新しい制御方式が確認された。",
            "what_text": "AIの動作範囲を限定する仕組みが追加された。",
            "why_important_text": "自律処理を本番へ接続する際の権限設計に関係する。",
            "decision_text": "TRY",
            "decision_reason_text": "限定環境なら検証できるが、本番一般化には追加確認が必要。",
            "score": 82,
            "action_text": "限定した環境でログと権限境界を比較検証する。",
            "score_breakdown_text": "Business Impact 20/25; Technical Impact 22/25; Urgency 15/20; Market Impact 13/15; Reliability 12/15; 合計 82/100",
            "note_draft": "PROVIDER ARTICLE MUST NOT SURVIVE",
        }

    def test_prewrite_contract_is_deterministic_and_management_first(self):
        evidence_result = {
            "limitations_disclosed": True,
            "freshness_scope_limited": True,
            "numeric_claims_allowed": False,
            "actor_attribution_allowed": False,
        }
        evidence_metadata = {"required_qualifiers": ["条件A", "条件B"]}
        first = a_plus.build_prewrite_contract(evidence_result, evidence_metadata)
        second = a_plus.build_prewrite_contract(evidence_result, evidence_metadata)
        self.assertEqual(first, second)
        self.assertIn(a_plus.PREWRITE_CONTRACT_ID, first)
        self.assertIn("MANAGEMENT DATA", first)
        self.assertIn("What / Why Important / Decision / Decision Reason / Action", first)
        self.assertIn("追加Provider callを要求しない", first)
        self.assertIn("required_qualifiers（2件）", first)
        self.assertIn("Decisionコードを『導入する／導入しない』へ固定変換しない", first)
        self.assertIn("歴史・設立・判決・事件・制度・研究・ベンチマーク", first)

    def test_local_fallback_requires_safe_management_and_blocks_fact_failures(self):
        parsed = self._parsed()
        evidence = {"state": "SUFFICIENT", "decision_scope_safe": True}
        reader_rows = [{"gate": "human_appeal", "severity": "REVIEW", "reason_code": "APPEAL"}]
        fact_rows = [{"gate": "fact", "severity": "HARD", "reason_code": "FACT"}]
        self.assertTrue(a_plus.can_use_local_fallback(parsed, reader_rows, evidence))
        self.assertFalse(a_plus.can_use_local_fallback(parsed, fact_rows, evidence))

        missing = dict(parsed)
        missing["action_text"] = ""
        self.assertFalse(a_plus.can_use_local_fallback(missing, reader_rows, evidence))

    def test_provider_free_fallback_discards_provider_article_surface(self):
        parsed = self._parsed()
        repo = {
            "nameWithOwner": "example/project",
            "url": "https://example.com/project",
            "primaryUrl": "https://example.com/project",
        }
        evidence_context = (
            "公式資料で新しい制御方式が確認された。"
            "AIの動作範囲を限定する仕組みが追加された。"
            "自律処理を本番へ接続する際の権限設計に関係する。"
            "限定環境なら検証できるが、本番一般化には追加確認が必要。"
            "限定した環境でログと権限境界を比較検証する。"
        )
        out, meta = a_plus.compile_provider_free_fallback(
            repo,
            parsed,
            source="OfficialVendor",
            primary_url="https://example.com/project",
            grounding={"evidence_urls": ["https://example.com/project"]},
            evidence_context=evidence_context,
        )
        self.assertNotIn("PROVIDER ARTICLE MUST NOT SURVIVE", out["note_draft"])
        self.assertTrue(out["note_draft"].strip())
        self.assertFalse(meta["provider_article_surface_reused"])
        self.assertEqual(a_plus.LOCAL_FALLBACK_ID, meta["contract"])

    def test_runtime_layer_wires_a_plus_without_growing_pipeline_core(self):
        pipeline = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        runtime = (ROOT / "runtime_layers.py").read_text(encoding="utf-8")
        layer = (ROOT / "a_plus_editorial_orchestration.py").read_text(encoding="utf-8")
        self.assertNotIn("A+ LOCAL FALLBACK", pipeline)
        self.assertIn('"a_plus_editorial_orchestration.install"', runtime)
        self.assertIn("a_plus_editorial_orchestration.install(pipeline_module)", runtime)
        self.assertIn("build_prewrite_contract", layer)
        self.assertIn("should_attempt_dynamic_retry_a_plus", layer)
        self.assertIn("call_gemini_grounded_deep_dive_a_plus", layer)
        self.assertIn("[A+ LOCAL FALLBACK]", layer)


if __name__ == "__main__":
    unittest.main()
