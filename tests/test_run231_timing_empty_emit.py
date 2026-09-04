from __future__ import annotations

import importlib


def test_emit_disabled_is_silent(monkeypatch):
    monkeypatch.delenv("PIPELINE_TIMING", raising=False)
    import perf_timing

    importlib.reload(perf_timing)
    messages = []
    perf_timing.emit(messages.append)
    assert messages == []
