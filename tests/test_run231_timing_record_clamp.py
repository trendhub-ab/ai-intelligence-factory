from __future__ import annotations

import importlib


def test_negative_duration_is_clamped(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIMING", "1")
    import perf_timing

    importlib.reload(perf_timing)
    perf_timing.reset()
    perf_timing.record("negative", -1.0)
    assert perf_timing.summary()["negative"]["total_seconds"] == 0.0
