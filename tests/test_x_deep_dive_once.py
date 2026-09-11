import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from x_discovery.deep_dive_once import (
    DeepDiveOnceError,
    MODEL,
    OPERATION,
    run_once,
)

ROOT = Path("x_discovery")


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class FakePipeline:
    EVIDENCE_SUPPLEMENT_REQUIRED = "SUPPLEMENT_REQUIRED"
    EVIDENCE_SUFFICIENT = "SUFFICIENT"
    GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS = 8000
    MAX_QUALITY_RETRIES = 1
    ENABLE_URL_CONTEXT = True
    ENABLE_GOOGLE_SEARCH_GROUNDING = True
    DEEP_DIVE_MODEL_POOL = [MODEL]
    GH_PAT = "test-token"
    client = object()
    AIIF_X_DEEP_DIVE_USAGE = None

    def __init__(self):
        self.GEMINI_BUDGET = NS(daily_budget=1, request_count=0)
        self.DEEP_DIVE_MODEL_BUDGET = NS(budget=1, used=0)
        self.PERSISTENT_GEMINI_COUNTER = NS(
            enabled=True, branch="runtime-state",
            repo="trendhub-ab/ai-intelligence-factory", counter_scope="test",
        )
        self._call_deep_dive_pool = lambda *_args, **_kwargs: None
        self.send_telegram_alert = lambda *_args, **_kwargs: None
        self.generate_note_editorial_eyecatch = lambda *_args, **_kwargs: None
        self.generated_kwargs = None

    def _select_stocked_deep_dive_candidates(self, items):
        return [row for row in items if row.get("notion_page_id") and row.get("score", 0) >= 60]

    def prepare_source_context(self, repo):
        return {
            "primary_source_resolved": True,
            "primary_url": repo["url"],
            "context": "official primary source context " * 30,
            "verification_context": "official verified primary source context " * 30,
            "deep_source_scanned": True,
            "evidence_documents": [{"url": repo["url"]}],
        }

    def resolve_followup_freshness(self, info):
        return {"triggered": False, "followup_found": False, "context": ""}

    def _truncate_source_context(self, value):
        return value

    def _merge_verification_context(self, before, after):
        return before + "\n" + after

    def _build_evidence_metadata(self, context, deep):
        return {"context_chars": len(context), "deep": deep}

    def assess_evidence_sufficiency(self, info):
        return {"state": self.EVIDENCE_SUFFICIENT, "decision_scope_safe": True}

    def supplement_source_evidence(self, info):
        raise AssertionError("supplement should not be needed")

    def generate_intelligence_report(self, *args, **kwargs):
        self.generated_kwargs = kwargs
        self.GEMINI_BUDGET.request_count += 1
        self.DEEP_DIVE_MODEL_BUDGET.used += 1
        return ("# Defense Factory\n\n検証用の生成記事。", "accepted")


class DeepDiveOnceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AIIF_X_DEEP_DIVE_EXECUTE": "true",
            "AIIF_X_DEEP_DIVE_OPERATION": OPERATION,
            "GITHUB_RUN_ATTEMPT": "1",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.candidate = load("fixtures/defense_factory_boundary_20260911.json")
        self.calibration = load("observations/defense_factory_calibration_20260911.json")
        self.stock = load("observations/defense_factory_stock_20260911.json")

    @patch("x_discovery.deep_dive_once._strict_single_model_pool", return_value=lambda *_a, **_k: None)
    def test_exactly_one_nonpersistent_generation_and_controls_restore(self, _strict):
        p = FakePipeline()
        original = (p.MAX_QUALITY_RETRIES, p.ENABLE_URL_CONTEXT, p.ENABLE_GOOGLE_SEARCH_GROUNDING)
        claims = []
        result = run_once(p, self.candidate, self.calibration, self.stock,
                          claim=lambda _p, evidence: claims.append(evidence))
        self.assertEqual(result["status"], "DEEP_DIVE_GENERATED")
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(result["notion_writes"], 0)
        self.assertFalse(result["publication_executed"])
        self.assertFalse(result["screening_reexecuted"])
        self.assertFalse(result["calibration_reexecuted"])
        self.assertFalse(result["stock_reexecuted"])
        self.assertEqual(len(claims), 1)
        self.assertFalse(p.generated_kwargs["persist_results"])
        self.assertEqual(p.GEMINI_BUDGET.request_count, 1)
        self.assertEqual(p.DEEP_DIVE_MODEL_BUDGET.used, 1)
        self.assertEqual(
            (p.MAX_QUALITY_RETRIES, p.ENABLE_URL_CONTEXT, p.ENABLE_GOOGLE_SEARCH_GROUNDING),
            original,
        )

    def test_execution_flag_is_required(self):
        os.environ["AIIF_X_DEEP_DIVE_EXECUTE"] = "false"
        p = FakePipeline()
        with self.assertRaisesRegex(DeepDiveOnceError, "execution authorization"):
            run_once(p, self.candidate, self.calibration, self.stock, claim=lambda *_a: None)
        self.assertEqual(p.GEMINI_BUDGET.request_count, 0)

    def test_rerun_is_rejected_before_claim(self):
        os.environ["GITHUB_RUN_ATTEMPT"] = "2"
        p = FakePipeline()
        with self.assertRaisesRegex(DeepDiveOnceError, "reruns"):
            run_once(p, self.candidate, self.calibration, self.stock, claim=lambda *_a: None)
        self.assertEqual(p.GEMINI_BUDGET.request_count, 0)

    def test_lane_forces_retry_and_gemini_tools_off(self):
        p = FakePipeline()
        seen = []
        original_generate = p.generate_intelligence_report
        def generate(*args, **kwargs):
            seen.append((p.MAX_QUALITY_RETRIES, p.ENABLE_URL_CONTEXT, p.ENABLE_GOOGLE_SEARCH_GROUNDING))
            return original_generate(*args, **kwargs)
        p.generate_intelligence_report = generate
        with patch("x_discovery.deep_dive_once._strict_single_model_pool", return_value=lambda *_a, **_k: None):
            run_once(p, self.candidate, self.calibration, self.stock, claim=lambda *_a: None)
        self.assertEqual(seen, [(0, False, False)])

    def test_wrong_stock_page_is_rejected(self):
        stock = dict(self.stock)
        stock["notion_page_id"] = "wrong"
        p = FakePipeline()
        with self.assertRaises(DeepDiveOnceError):
            run_once(p, self.candidate, self.calibration, stock, claim=lambda *_a: None)
        self.assertEqual(p.GEMINI_BUDGET.request_count, 0)


if __name__ == "__main__":
    unittest.main()
