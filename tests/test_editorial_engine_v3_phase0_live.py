from __future__ import annotations

import importlib.util


def test_live_module_exists_and_uses_fixed_non_lite_model() -> None:
    spec = importlib.util.find_spec("experiments.editorial_engine_v3_phase0.live")
    assert spec is not None
    from experiments.editorial_engine_v3_phase0 import live

    assert live.DEFAULT_MODEL == "gemini-3.6-flash"
    assert "lite" not in live.DEFAULT_MODEL.lower()


def test_live_experiment_has_exact_expected_call_budget() -> None:
    from experiments.editorial_engine_v3_phase0 import live

    assert live.B_CALLS_PER_CASE == 1
    assert live.C_CALLS_PER_CASE == 4
    assert live.EXPECTED_CASES == 3
    assert live.MAX_PROVIDER_CALLS == 15
