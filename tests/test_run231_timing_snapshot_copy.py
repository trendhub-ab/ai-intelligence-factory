from __future__ import annotations

import importlib


def test_snapshot_is_copy(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIMING", "1")
    import perf_timing

    importlib.reload(perf_timing)
    perf_timing.reset()
    perf_timing.record("x", 0.1)
    snapshot = perf_timing.snapshot()
    snapshot.clear()
    assert perf_timing.summary()["x"]["count"] == 1
