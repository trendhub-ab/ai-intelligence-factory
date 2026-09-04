# Run231 Performance Diagnostics

## Purpose

Separate maintainability problems caused by `pipeline.py` size from actual wall-clock latency caused by external I/O, API pacing, retries, and waits.

## How to measure

Baseline total wall clock:

```bash
python pipeline_timing_probe.py pipeline.py
```

Enable fine-grained timing for instrumented stages:

```bash
PIPELINE_TIMING=1 python pipeline.py
```

The opt-in timer is disabled by default and records nothing unless `PIPELINE_TIMING=1` (or `true/yes/on`) is set.

## Interpretation

Do not treat source line count as a latency metric. Python parses/imports the file once per process; production wall-clock time is expected to be dominated by network/API calls, explicit pacing waits, retry/backoff, source fetches, and persistence I/O.

Optimize only after timing data identifies the largest contributors. Preserve free-tier safety limits, retry correctness, Evidence/Quality gates, and fail-closed behavior.
