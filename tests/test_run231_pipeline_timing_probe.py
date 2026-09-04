from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_wall_clock_probe_reports_total(tmp_path):
    target = tmp_path / "tiny.py"
    target.write_text("x = sum(range(10))\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "pipeline_timing_probe.py", str(target)],
        check=True,
        capture_output=True,
        text=True,
    )
    line = next(line for line in proc.stdout.splitlines() if line.startswith("[PIPELINE_WALL_CLOCK] "))
    payload = json.loads(line.split(" ", 1)[1])
    assert payload[0]["stage"] == "total"
    assert payload[0]["seconds"] >= 0
