import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GH_PAT", "test-token")
os.environ.setdefault("GEMINI_QUOTA_PROJECT_ID", "test-project")
os.environ.setdefault("GEMINI_DEEP_DIVE_CALL_PACING_SECONDS", "0")

try:
    from google import genai  # noqa: F401
except ImportError:
    google_mod = types.ModuleType("google")
    google_mod.__path__ = []
    genai_mod = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")
    class APIError(Exception):
        pass
    class Client:
        def __init__(self, **_kwargs):
            self.models = types.SimpleNamespace()
    genai_mod.Client = Client
    errors_mod.APIError = APIError
    google_mod.genai = genai_mod
    sys.modules.update({"google": google_mod, "google.genai": genai_mod, "google.genai.errors": errors_mod})

import pipeline  # noqa: E402


class TestRun102PublishYieldPrecision(unittest.TestCase):
    def test_fact_and_publication_safety_remain_hard(self):
        fact = pipeline.map_gate_reasons("fact", ["unsupported numeric claim: 50GB"])
        pub = pipeline.map_gate_reasons("publication", ["research_to_production_leap"])
        self.assertEqual(pipeline.GATE_SEVERITY_HARD, fact[0]["severity"])
        self.assertEqual(pipeline.GATE_SEVERITY_HARD, pub[0]["severity"])
        self.assertEqual(pipeline.GATE_DISPOSITION_BLOCK, pipeline.gate_reason_disposition(fact + pub))

    def test_opening_hook_and_flat_title_are_soft_and_publishable(self):
        rows = (
            pipeline.map_gate_reasons("human_appeal", ["opening_hook_weak"])
            + pipeline.map_gate_reasons("human_appeal", ["headline_flattened"])
        )
        self.assertTrue(all(row["severity"] == pipeline.GATE_SEVERITY_SOFT for row in rows))
        self.assertEqual(pipeline.GATE_DISPOSITION_PASS_WITH_WARNINGS, pipeline.gate_reason_disposition(rows))
        allowed, reason = pipeline.should_attempt_dynamic_retry(rows, {"state": pipeline.EVIDENCE_SUFFICIENT})
        self.assertFalse(allowed)
        self.assertEqual("soft_quality_only", reason)

    def test_decision_value_loss_is_review_not_soft(self):
        rows = pipeline.map_gate_reasons(
            "human_appeal", ["action_collapsed_to_generic_monitoring", "decision_voice_missing"]
        )
        self.assertTrue(all(row["severity"] == pipeline.GATE_SEVERITY_REVIEW for row in rows))
        self.assertEqual(pipeline.GATE_DISPOSITION_REVIEW, pipeline.gate_reason_disposition(rows))
        allowed, reason = pipeline.should_attempt_dynamic_retry(rows, {"state": pipeline.EVIDENCE_SUFFICIENT})
        self.assertTrue(allowed)
        self.assertEqual("repairable", reason)

    def test_fabricated_experience_is_hard_even_when_detected_editorially(self):
        rows = pipeline.map_gate_reasons("editorial", ["unsupported personal experience"])
        self.assertEqual(pipeline.REASON_CODE_APPEAL_FABRICATED_EXPERIENCE, rows[0]["reason_code"])
        self.assertEqual(pipeline.GATE_SEVERITY_HARD, rows[0]["severity"])
        self.assertEqual(pipeline.GATE_DISPOSITION_BLOCK, pipeline.gate_reason_disposition(rows))

    def test_multiple_soft_warnings_do_not_create_an_implicit_threshold(self):
        rows = (
            pipeline.map_gate_reasons("human_appeal", ["opening_hook_weak", "headline_flattened"])
            + pipeline.map_gate_reasons("editorial", ["mechanical ordinal structure"])
        )
        self.assertEqual(3, len(rows))
        self.assertEqual(pipeline.GATE_DISPOSITION_PASS_WITH_WARNINGS, pipeline.gate_reason_disposition(rows))
        allowed, reason = pipeline.should_attempt_dynamic_retry(rows, {"state": pipeline.EVIDENCE_SUFFICIENT})
        self.assertFalse(allowed)
        self.assertEqual("soft_quality_only", reason)

    def test_editorial_gate_itself_treats_style_only_repetition_as_nonblocking(self):
        article = "\n".join([
            "## はじめに",
            "ただ、原資料の条件は確認します。",
            "これは意味します。これは意味します。これは意味します。これは意味します。これは意味します。",
        ])
        ok, warnings = pipeline.validate_editorial_gate({"note_draft": article}, "style-only")
        self.assertTrue(ok, warnings)
        self.assertIn("repetitive AI-like sentence endings", warnings)

    def test_material_list_heavy_article_requires_review_but_not_fact_failure(self):
        article = "\n".join(f"- 項目{i}" for i in range(30))
        ok, warnings = pipeline.validate_editorial_gate({"note_draft": article}, "list-heavy")
        self.assertFalse(ok)
        rows = pipeline.map_gate_reasons("editorial", warnings)
        self.assertIn(pipeline.GATE_SEVERITY_REVIEW, {row["severity"] for row in rows})
        self.assertNotIn(pipeline.GATE_SEVERITY_HARD, {row["severity"] for row in rows})

    def test_unknown_future_editorial_and_human_rules_fail_safe_to_review(self):
        editorial = pipeline.map_gate_reasons("editorial", ["future material readability defect"])
        human = pipeline.map_gate_reasons("human_appeal", ["future decision-value defect"])
        self.assertEqual(pipeline.GATE_SEVERITY_REVIEW, editorial[0]["severity"])
        self.assertEqual(pipeline.GATE_SEVERITY_REVIEW, human[0]["severity"])

    def test_legacy_reason_rows_without_severity_are_normalized_fail_safe(self):
        record = pipeline.build_candidate_gate_record(
            1, "legacy", "https://example.com", 70, "completed",
            reason_codes=[{
                "reason_code": pipeline.REASON_CODE_PUB_UNSUPPORTED_CONCLUSION,
                "message": "research_to_production_leap",
            }],
            final_status=pipeline.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW,
        )
        self.assertEqual(pipeline.GATE_SEVERITY_HARD, record["reason_codes"][0]["severity"])
        self.assertEqual("publication", record["reason_codes"][0]["gate"])
        self.assertEqual(pipeline.GATE_DISPOSITION_BLOCK, record["gate_disposition"])

    def test_nonrepairable_evidence_gap_never_spends_quality_retry(self):
        rows = [{
            "reason_code": pipeline.REASON_CODE_PRIMARY_EVIDENCE_INSUFFICIENT,
            "message": "Evidence-to-Decision Sufficiency cannot safely support the core decision.",
            "gate": "evidence",
            "severity": pipeline.GATE_SEVERITY_HARD,
        }]
        allowed, reason = pipeline.should_attempt_dynamic_retry(rows, {"state": pipeline.EVIDENCE_SUFFICIENT})
        self.assertFalse(allowed)
        self.assertEqual("non_repairable_evidence_or_source_gap", reason)

    def test_candidate_record_preserves_severity_and_disposition(self):
        rows = pipeline.map_gate_reasons("human_appeal", ["opening_hook_weak"])
        record = pipeline.build_candidate_gate_record(
            1, "example", "https://example.com", 72, "completed",
            pipeline.GATE_STATUS_PASS, pipeline.GATE_STATUS_PASS,
            pipeline.GATE_STATUS_PASS, pipeline.GATE_STATUS_WARNING,
            rows, pipeline.ARTICLE_STATUS_READY, True,
        )
        self.assertEqual(pipeline.GATE_DISPOSITION_PASS_WITH_WARNINGS, record["gate_disposition"])
        self.assertEqual(0, record["hard_reason_count"])
        self.assertEqual(0, record["review_reason_count"])
        self.assertEqual(1, record["soft_warning_count"])

    def test_funnel_reports_both_publish_yields_and_soft_retry_savings(self):
        funnel = pipeline.DeepDiveGateFunnel()
        rows = pipeline.map_gate_reasons("human_appeal", ["opening_hook_weak"])
        record = pipeline.build_candidate_gate_record(
            1, "example", "https://example.com", 72, "completed",
            pipeline.GATE_STATUS_PASS, pipeline.GATE_STATUS_PASS,
            pipeline.GATE_STATUS_PASS, pipeline.GATE_STATUS_WARNING,
            rows, pipeline.ARTICLE_STATUS_READY, True,
            evidence_result={"state": pipeline.EVIDENCE_SUFFICIENT},
            retry_diagnostics={
                "retry_attempted": False,
                "retry_skipped_reason": "soft_quality_only",
                "trigger_reason_codes": rows,
            },
        )
        funnel.record(record)
        text = funnel.render_text()
        self.assertIn("Candidate Publish Yield: 1/1 (100.0%)", text)
        self.assertIn("Generated Publish Yield: 1/1 (100.0%)", text)
        self.assertIn("Retry Avoided (SOFT only): 1", text)
        self.assertEqual(1, funnel.counters["soft_warning_ready"])


    def _run_nonpersistent_with_gates(self, *, fact=(True, []), editorial=(True, []), publication=("PASS", []), appeal=("ACCEPTABLE", [])):
        repo = {
            "nameWithOwner": "owner/example", "url": "https://example.com/source",
            "description": "desc", "stargazerCount": 10, "source": "HackerNews",
            "publishedAt": "2026-08-22T00:00:00Z",
        }
        parsed = {
            "note_draft": "## はじめに\n原資料を確認する。\n\n## 結論\n限定検証する。\n\n## 最終判断\n小さく試す。",
            "title_text": "この技術を試すべきか？", "score": 72, "score_breakdown_text": "Technical Impact 18/25; Urgency 10/20",
            "source_summary_text": "概要", "what_text": "what", "why_important_text": "why",
            "paradigm_shift_text": "p", "alternative_comparison_text": "a", "migration_cost_text": "m",
            "decision_text": "TRY", "decision_reason_text": "dr", "why_not_important_text": "wn",
            "who_should_use_text": "wu", "who_should_not_use_text": "wnu",
            "action_text": "検証環境で小さく比較テストする。", "future_scenario_text": "fs", "article_value": 70,
            "grounding_status": pipeline.GROUNDING_SOURCE_NATIVE, "evidence_urls_text": "",
        }
        response = MagicMock(); response.text = "dummy"
        source_info = {
            "primary_source_resolved": True, "primary_url": repo["url"],
            "context": "official method implementation limitation", "verification_context": "official method implementation limitation",
            "method": pipeline.GROUNDING_SOURCE_NATIVE, "source": "HackerNews", "deep_source_scanned": False,
            "evidence_metadata": {}, "evidence_urls": [repo["url"]],
        }
        evidence = {
            "state": pipeline.EVIDENCE_SUFFICIENT, "initial_state": pipeline.EVIDENCE_SUFFICIENT,
            "core_missing": [], "blocking_missing": [], "decision_scope_safe": True,
            "action_risk_tier": "LOW", "supplement_attempted": False, "supplement_success": False,
        }
        with patch.object(pipeline, "legal_safety_gate", return_value=(True, "MIT")), \
             patch.object(pipeline, "prepare_source_context", return_value=source_info), \
             patch.object(pipeline, "resolve_followup_freshness", return_value={"triggered": False, "followup_found": False, "context": ""}), \
             patch.object(pipeline, "assess_evidence_sufficiency", return_value=evidence), \
             patch.object(pipeline, "classify_action_risk_tier", return_value="LOW"), \
             patch.object(pipeline, "build_decision_prompt", return_value="prompt"), \
             patch.object(pipeline, "call_gemini_grounded_deep_dive", return_value=(response, {"grounding_status": pipeline.GROUNDING_SOURCE_NATIVE, "evidence_urls": [repo["url"]]})) as gemini, \
             patch.object(pipeline, "_response_was_truncated", return_value=False), \
             patch.object(pipeline, "_parse_gemini_response", side_effect=lambda _text: dict(parsed)), \
             patch.object(pipeline, "_apply_final_japanese_polish", side_effect=lambda x: (x, [])), \
             patch.object(pipeline, "validate_fact_gate", return_value=fact), \
             patch.object(pipeline, "validate_editorial_gate", return_value=editorial), \
             patch.object(pipeline, "validate_publication_readiness_gate", return_value=publication), \
             patch.object(pipeline, "validate_human_appeal_gate", return_value=appeal), \
             patch.object(pipeline, "build_clean_note_manuscript", return_value="clean manuscript"), \
             patch.object(pipeline, "save_regen_test_manuscript"):
            result = pipeline.generate_intelligence_report(repo, persist_results=False)
        return result, gemini.call_count

    def test_soft_only_full_pipeline_uses_one_generation_call_and_no_quality_retry(self):
        result, calls = self._run_nonpersistent_with_gates(appeal=("WEAK", ["opening_hook_weak"]))
        self.assertEqual(1, calls)
        self.assertEqual(("clean manuscript", "accepted"), result)

    def test_decision_value_review_full_pipeline_uses_one_repair_retry_then_stops_unpublished(self):
        result, calls = self._run_nonpersistent_with_gates(
            appeal=("WEAK", ["action_collapsed_to_generic_monitoring"])
        )
        self.assertEqual(2, calls)
        self.assertEqual(("clean manuscript", "rejected"), result)

    def test_article_audit_ready_exposes_quality_notes_not_failure_reason(self):
        repo = {"nameWithOwner": "owner/repo", "url": "https://example.com/repo", "source": "GitHub"}
        parsed = {"note_draft": "本文", "score": 72, "title_text": "題名。"}
        rows = pipeline.map_gate_reasons("human_appeal", ["opening_hook_weak"])
        gate = pipeline.build_candidate_gate_record(
            1, repo["nameWithOwner"], repo["url"], 72, "completed",
            pipeline.GATE_STATUS_PASS, pipeline.GATE_STATUS_PASS,
            pipeline.GATE_STATUS_PASS, pipeline.GATE_STATUS_WARNING,
            rows, pipeline.ARTICLE_STATUS_READY, True,
        )
        with tempfile.TemporaryDirectory() as td, patch.object(pipeline, "ARTICLE_AUDIT_DIR", td):
            files = pipeline.save_article_audit_package(
                repo, "READY", parsed, {"primary_url": repo["url"]}, gate,
                "opening_hook_weak", clean_manuscript="本文"
            )
            final = next(Path(x) for x in files if x.endswith("final.md"))
            body = final.read_text(encoding="utf-8")
            self.assertIn("## Quality Notes", body)
            self.assertIn("opening_hook_weak", body)
            self.assertNotIn("## Failure Reason", body)
            summary = (Path(td) / "RUN_SUMMARY.md").read_text(encoding="utf-8")
            self.assertIn("Disposition", summary)
            self.assertIn("PASS_WITH_WARNINGS", summary)


if __name__ == "__main__":
    unittest.main()
