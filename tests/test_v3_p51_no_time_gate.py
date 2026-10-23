"""P5.1 model fallback must not have a local-hour eligibility rule.

This test is provider-free and does not call Gemini.
"""
from __future__ import annotations
import inspect
from experiments.editorial_engine_v3_phase0 import one_shot_fallback as f


def test_no_jst_time_window_gate_and_provider_only_fallback() -> None:
    source = inspect.getsource(f)
    assert "datetime.now" not in source
    assert "17:00" not in source
    assert "JST_17_GATE" not in source
    assert f.CANDIDATE_MODELS == (
        "gemini-3-flash-preview", "gemini-3.6-flash", "gemini-3.8-flash"
    )
    assert f.BASELINE_RUN_ID == 39239644474
    assert "transient_provider_429_503" in source
    assert "structural_failure_stop" in source
    assert '"no mixing, only provider 429/503, no publication"' in source
