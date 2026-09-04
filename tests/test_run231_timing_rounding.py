from __future__ import annotations

import importlib


def test_summary_rounds_to_microseconds(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIMING", "1")
    import perf_timing

    importlib.reload(perf_timing)
    perf_timing.reset()
    perf_timing.record("x", 0.123456789)
    assert perf_timing.summary()["x"]["total_seconds"] == 0.123457
