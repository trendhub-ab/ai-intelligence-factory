from __future__ import annotations

import importlib


def test_summary_average(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIMING", "1")
    import perf_timing

    importlib.reload(perf_timing)
    perf_timing.reset()
    perf_timing.record("x", 0.1)
    perf_timing.record("x", 0.3)
    assert perf_timing.summary()["x"]["avg_seconds"] == 0.2
