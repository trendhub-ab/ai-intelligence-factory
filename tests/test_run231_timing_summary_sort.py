from __future__ import annotations

import importlib


def test_summary_is_sorted_by_total_descending(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIMING", "1")
    import perf_timing

    importlib.reload(perf_timing)
    perf_timing.reset()
    perf_timing.record("small", 0.1)
    perf_timing.record("large", 0.9)
    assert list(perf_timing.summary()) == ["large", "small"]
