from __future__ import annotations

import importlib


def test_reset_clears_samples(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIMING", "1")
    import perf_timing

    importlib.reload(perf_timing)
    perf_timing.record("x", 0.1)
    perf_timing.reset()
    assert perf_timing.summary() == {}
