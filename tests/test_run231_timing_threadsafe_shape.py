from __future__ import annotations

import importlib
import threading


def test_record_keeps_all_samples_across_threads(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIMING", "1")
    import perf_timing

    importlib.reload(perf_timing)
    perf_timing.reset()

    threads = [threading.Thread(target=perf_timing.record, args=("threaded", 0.001)) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert perf_timing.summary()["threaded"]["count"] == 8
