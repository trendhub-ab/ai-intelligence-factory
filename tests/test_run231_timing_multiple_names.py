from __future__ import annotations

import importlib


def test_multiple_names_are_grouped_independently(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIMING", "1")
    import perf_timing

    importlib.reload(perf_timing)
    perf_timing.reset()
    perf_timing.record("api", 0.3)
    perf_timing.record("io", 0.2)
    summary = perf_timing.summary()
    assert summary["api"]["count"] == 1
    assert summary["io"]["count"] == 1
