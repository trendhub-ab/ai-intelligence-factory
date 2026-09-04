from __future__ import annotations

from pathlib import Path


def test_performance_diagnostics_are_opt_in_and_do_not_change_pipeline_defaults():
    timer = Path("perf_timing.py").read_text(encoding="utf-8")
    docs = Path("RUN231_PERFORMANCE_DIAGNOSTICS.md").read_text(encoding="utf-8")
    assert 'os.getenv("PIPELINE_TIMING", "0")' in timer
    assert "PIPELINE_TIMING=1" in docs
    assert "free-tier safety limits" in docs
