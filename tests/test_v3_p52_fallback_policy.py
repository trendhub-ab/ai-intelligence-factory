"""Non-production provider-free constraints for the P5.2 one-shot fallback."""
from __future__ import annotations
import inspect
from experiments.editorial_engine_v3_phase0 import one_shot_fallback as f

def test_p52_fallback_without_clock_gate_and_limited_provider_policy():
    source = inspect.getsource(f)
    assert "datetime.now" not in source
    assert "17:00" not in source
    assert f.CANDIDATE_MODELS == (
        "gemini-3-flash-preview", "gemini-3.6-flash", "gemini-3.8-flash"
    )
    assert f.BASELINE_RUN_ID == 39239644474
    assert "transient_provider_429_503" in source
    assert "structural_failure_stop" in source
    assert "whole_three_case_set; provider 429/503 only" in source
    assert "AIIF_PHASE0_REGENERATE_C_ONLY" in source
