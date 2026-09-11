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
    MAX_QUALITY_RETRIES = 0
    ENABLE_URL_CONTEXT = False
    ENABLE_GOOGLE_SEARCH_GROUNDING = False
    DEEP_DIVE_MODEL_POOL = [MODEL]
    GH_PAT = "test-token"
    client = object()
    LAST_GEMINI_USAGE = None

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
        self.old_operation = os.environ.get("AIIF_X_DEEP_DIVE_OPERATION")
        self.old_attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
        os.environ["AIIF_X_DEEP_DIVE_OPERATION"] = OPERATION
        os.environ["GITHUB_RUN_ATTEMPT"] = "1"
        self.candidate = load("fixtures/defense_factory_boundary_20260911.json")
        self.calibration = load("observations/defense_factory_calibration_20260911.json")
        self.stock = load("observations/defense_factory_stock_20260911.json")

    def tearDown(self):
        if self.old_operation is None:
            os.environ.pop("AIIF_X_DEEP_DIVE_OPERATION", None)
        else:
            os.environ["AIIF_X_DEEP_DIVE_OPERATION"] = self.old_operation
        if self.old_attempt is None:
            os.environ.pop("GITHUB_RUN_ATTEMPT", None)
        else:
            os.environ["GITHUB_RUN_ATTEMPT"] = self.old_attempt

    @patch("x_discovery.deep_dive_once._strict_single_model_pool", return_value=lambda *_a, **_k: None)
    def test_exactly_one_nonpersistent_generation(self, _strict):
        p = FakePipeline()
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

    def test_rerun_is_rejected_before_claim(self):
        os.environ["GITHUB_RUN_ATTEMPT"] = "2"
        p = FakePipeline()
        with self.assertRaisesRegex(DeepDiveOnceError, "reruns"):
            run_once(p, self.candidate, self.calibration, self.stock, claim=lambda *_a: None)
        self.assertEqual(p.GEMINI_BUDGET.request_count, 0)

    def test_quality_retry_must_be_zero(self):
        p = FakePipeline()
        p.MAX_QUALITY_RETRIES = 1
        with self.assertRaisesRegex(DeepDiveOnceError, "Quality Retry"):
            run_once(p, self.candidate, self.calibration, self.stock, claim=lambda *_a: None)
        self.assertEqual(p.GEMINI_BUDGET.request_count, 0)

    def test_url_context_or_search_is_rejected(self):
        p = FakePipeline()
        p.ENABLE_URL_CONTEXT = True
        with self.assertRaisesRegex(DeepDiveOnceError, "URL Context/Search"):
            run_once(p, self.candidate, self.calibration, self.stock, claim=lambda *_a: None)
        self.assertEqual(p.GEMINI_BUDGET.request_count, 0)

    def test_wrong_stock_page_is_rejected(self):
        stock = dict(self.stock)
        stock["notion_page_id"] = "wrong"
        p = FakePipeline()
        with self.assertRaises(DeepDiveOnceError):
            run_once(p, self.candidate, self.calibration, stock, claim=lambda *_a: None)
        self.assertEqual(p.GEMINI_BUDGET.request_count, 0)


if __name__ == "__main__":
    unittest.main()
