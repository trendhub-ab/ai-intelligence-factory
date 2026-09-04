from __future__ import annotations

import importlib


def test_default_timer_does_not_record(monkeypatch):
    monkeypatch.delenv("PIPELINE_TIMING", raising=False)
    import perf_timing

    importlib.reload(perf_timing)
    perf_timing.reset()
    perf_timing.record("should_not_exist", 1.0)
    assert perf_timing.summary() == {}
