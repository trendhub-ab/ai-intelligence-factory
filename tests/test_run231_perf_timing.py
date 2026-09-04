from __future__ import annotations

import importlib
import json
import time


def test_timing_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PIPELINE_TIMING", raising=False)
    import perf_timing

    importlib.reload(perf_timing)
    perf_timing.reset()
    with perf_timing.span("disabled"):
        pass
    assert perf_timing.snapshot() == []


def test_timing_summary_and_emit(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIMING", "1")
    import perf_timing

    importlib.reload(perf_timing)
    perf_timing.reset()
    with perf_timing.span("stage"):
        time.sleep(0.001)
    perf_timing.record("stage", 0.002)

    row = perf_timing.summary()["stage"]
    assert row["count"] == 2
    assert row["total_seconds"] >= 0.002
    assert row["max_seconds"] >= 0.002

    messages = []
    perf_timing.emit(messages.append)
    assert len(messages) == 1
    assert messages[0].startswith("[PIPELINE_TIMING] ")
    payload = json.loads(messages[0].split(" ", 1)[1])
    assert "stage" in payload["pipeline_timing"]
