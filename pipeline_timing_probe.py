from __future__ import annotations

import argparse
import json
import runpy
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator, List


@contextmanager
def _measure(bucket: List[dict], name: str) -> Iterator[None]:
    started = time.perf_counter()
    try:
        yield
    finally:
        bucket.append({"stage": name, "seconds": round(time.perf_counter() - started, 6)})


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Python entry point and report coarse wall-clock timing.")
    parser.add_argument("script", nargs="?", default="pipeline.py")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args()

    script = Path(ns.script)
    if not script.exists():
        raise SystemExit(f"script not found: {script}")

    timings: List[dict] = []
    old_argv = sys.argv[:]
    sys.argv = [str(script), *ns.args]
    try:
        with _measure(timings, "total"):
            runpy.run_path(str(script), run_name="__main__")
    finally:
        sys.argv = old_argv

    print("[PIPELINE_WALL_CLOCK] " + json.dumps(timings, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
