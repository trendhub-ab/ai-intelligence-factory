from __future__ import annotations

import importlib
import json


def test_emit_payload_is_json_serializable(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIMING", "1")
    import perf_timing

    importlib.reload(perf_timing)
    perf_timing.reset()
    perf_timing.record("stage", 0.1234567)
    messages = []
    perf_timing.emit(messages.append)
    payload = json.loads(messages[0].split(" ", 1)[1])
    assert isinstance(payload["pipeline_timing"]["stage"]["total_seconds"], float)
