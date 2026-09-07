from __future__ import annotations

import inspect
import logging
import os
import types
import unittest
from unittest.mock import patch

import run226_reader_delight_planning as run226
import run228_reader_rhythm_planning as run228
import run274_zero_api_evidence_backfill as run274
import runtime_layers


class _Funnel:
    def __init__(self):
        self.counters = {"deep_dive_calls_avoided": 0}


class Run274ReadyYieldReaderValueTests(unittest.TestCase):
    def _dummy_pipeline(self):
        state = {"model_calls": 0}
        funnel = _Funnel()

        def generate(repo, notion_page_id=None, screening_score=None, screening_reason="", persist_results=True, **kwargs):
            if repo.get("evidence_fail"):
                funnel.counters["deep_dive_calls_avoided"] += 1
                return None
            state["model_calls"] += 1
            return "READY" if repo.get("ready") else None

        pipe = types.SimpleNamespace(
            generate_intelligence_report=generate,
            MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS=7,
            _active_gate_funnel=lambda persist=True: funnel,
            logger=logging.getLogger("run274-test"),
        )
        return pipe, funnel, state

    def test_zero_api_evidence_reject_returns_attempt_headroom_without_model_call(self):
        pipe, _, state = self._dummy_pipeline()
        run274.install(pipe)
        result = pipe.generate_intelligence_report({"evidence_fail": True})
        self.assertIsNone(result)
        self.assertEqual(state["model_calls"], 0)
        self.assertEqual(pipe.MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS, 8)
        self.assertEqual(getattr(pipe, run274._COMPENSATIONS_ATTR), 1)

    def test_model_bearing_candidate_does_not_increase_attempt_cap(self):
        pipe, _, state = self._dummy_pipeline()
        run274.install(pipe)
        pipe.generate_intelligence_report({"evidence_fail": True})
        pipe.generate_intelligence_report({"ready": False})
        self.assertEqual(state["model_calls"], 1)
        self.assertEqual(pipe.MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS, 8)

    def test_headroom_is_bounded_and_does_not_change_base_model_attempt_cap(self):
        pipe, _, state = self._dummy_pipeline()
        with patch.dict(os.environ, {run274.HEADROOM_ENV: "3"}):
            run274.install(pipe)
            for _ in range(10):
                pipe.generate_intelligence_report({"evidence_fail": True})
        self.assertEqual(state["model_calls"], 0)
        self.assertEqual(pipe.MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS, 10)
        self.assertEqual(getattr(pipe, run274._BASE_CAP_ATTR), 7)
        self.assertEqual(getattr(pipe, run274._COMPENSATIONS_ATTR), 3)

    def test_nonpersistent_regen_cannot_mutate_production_headroom(self):
        pipe, _, _ = self._dummy_pipeline()
        run274.install(pipe)
        pipe.generate_intelligence_report({"evidence_fail": True}, persist_results=False)
        self.assertEqual(pipe.MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS, 7)
        self.assertEqual(getattr(pipe, run274._COMPENSATIONS_ATTR), 0)

    def test_new_funnel_resets_run_local_headroom(self):
        pipe, funnel, _ = self._dummy_pipeline()
        current = {"funnel": funnel}
        pipe._active_gate_funnel = lambda persist=True: current["funnel"]
        run274.install(pipe)
        pipe.generate_intelligence_report({"evidence_fail": True})
        self.assertEqual(pipe.MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS, 8)
        current["funnel"] = _Funnel()
        pipe.generate_intelligence_report({"ready": False})
        self.assertEqual(pipe.MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS, 7)
        self.assertEqual(getattr(pipe, run274._COMPENSATIONS_ATTR), 0)

    def test_run274_adds_no_provider_or_model_call_site(self):
        src = inspect.getsource(run274)
        self.assertNotIn("_generate_via_chat(", src)
        self.assertNotIn("genai.Client(", src)
        self.assertNotIn("requests.get(", src)
        self.assertNotIn("requests.post(", src)

    def test_runtime_installs_run274_after_reader_planning(self):
        order = runtime_layers.RUNTIME_LAYER_ORDER
        self.assertIn("run274_zero_api_evidence_backfill.install", order)
        self.assertGreater(
            order.index("run274_zero_api_evidence_backfill.install"),
            order.index("run228_reader_rhythm_planning.install"),
        )

    def test_real_production_reader_failure_fingerprint_is_addressed_without_gate_relaxation(self):
        rhythm = run228.reader_rhythm_contract()
        for label in (
            "dense_report_cluster",
            "repetitive_insight",
            "non_engineer_access_failure",
            "報告書の塊",
            "理解→意味→判断",
        ):
            self.assertIn(label, rhythm)
        self.assertIn("Evidence上重要な数値・条件・反証・制約は削らない", rhythm)
        self.assertIn("新しいFact、数字、人物、会話、利用実績、因果、競合情報を作る", rhythm)

    def test_editorial_plan_keeps_source_boundary_and_subtractive_priority(self):
        plan = run226.editorial_planning_contract()
        self.assertIn("SOURCE BOUNDARY", plan)
        self.assertIn("Fact / Evidence / Decision", plan)
        self.assertIn("周辺仕様・実装列挙・重複説明", plan)
        self.assertIn("新情報の足し算ではなく", plan)


if __name__ == "__main__":
    unittest.main()
