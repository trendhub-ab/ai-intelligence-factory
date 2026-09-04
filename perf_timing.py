from __future__ import annotations

import contextlib
import json
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterator, List


_TRUE = {"1", "true", "yes", "on"}


def _enabled() -> bool:
    return os.getenv("PIPELINE_TIMING", "0").strip().lower() in _TRUE


@dataclass(frozen=True)
class TimingSample:
    name: str
    seconds: float


_lock = threading.Lock()
_samples: List[TimingSample] = []


def record(name: str, seconds: float) -> None:
    if not _enabled():
        return
    with _lock:
        _samples.append(TimingSample(str(name), max(0.0, float(seconds))))


@contextlib.contextmanager
def span(name: str) -> Iterator[None]:
    if not _enabled():
        yield
        return
    started = time.perf_counter()
    try:
        yield
    finally:
        record(name, time.perf_counter() - started)


def reset() -> None:
    with _lock:
        _samples.clear()


def snapshot() -> List[TimingSample]:
    with _lock:
        return list(_samples)


def summary() -> Dict[str, dict]:
    grouped: Dict[str, List[float]] = defaultdict(list)
    for sample in snapshot():
        grouped[sample.name].append(sample.seconds)

    rows: Dict[str, dict] = {}
    for name, values in grouped.items():
        total = sum(values)
        rows[name] = {
            "count": len(values),
            "total_seconds": round(total, 6),
            "avg_seconds": round(total / len(values), 6),
            "max_seconds": round(max(values), 6),
        }
    return dict(sorted(rows.items(), key=lambda item: item[1]["total_seconds"], reverse=True))


def emit(logger=print) -> None:
    if not _enabled():
        return
    payload = {
        "pipeline_timing": summary(),
        "total_recorded_seconds": round(sum(s.seconds for s in snapshot()), 6),
    }
    logger("[PIPELINE_TIMING] " + json.dumps(payload, ensure_ascii=False, sort_keys=True))
