"""Fail-closed *offline* lock for the validated four-source Fresh runtime.

Checks current Git-blob content and fixed logical work bounds. This cannot
query actual Gemini quotas or certify candidate/Gate quality. No API access.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
LOCK = ROOT / "docs/audits/fresh-four-source-protocol-lock-v1.json"
SOURCES = frozenset({"GitHub", "HackerNews", "ArXiv", "OfficialVendor"})


def git_blob_id(contents: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(contents)).encode("ascii") + b"\0" + contents).hexdigest()


def _workflow_value(workflow: str, name: str) -> int:
    matches = re.findall(
        r"^\s+" + re.escape(name) + r': "([0-9]+)"\s*$',
        workflow, flags=re.MULTILINE,
    )
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one frozen Fresh workflow setting: " + name)
    return int(matches[0])


def validate(*, repo_root: Path = ROOT, manifest_path: Path = LOCK, source: str = "") -> dict:
    if source not in SOURCES and source != "":
        raise RuntimeError("Invalid or unexpected Fresh source target")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("protocol") != "fresh-unmodified-four-source-v439-v1":
        raise RuntimeError("Invalid frozen Fresh protocol id")
    if manifest.get("source_membership") != sorted(SOURCES):
        raise RuntimeError("Source-set drift in Fresh protocol lock")
    files = manifest.get("file_blobs")
    if not isinstance(files, dict) or len(files) < 18:
        raise RuntimeError("Incomplete frozen Fresh file manifest")
    for relative, expected in files.items():
        if not isinstance(relative, str) or relative.startswith("/") or ".." in Path(relative).parts:
            raise RuntimeError("Unsafe Fresh manifest path")
        if not re.fullmatch(r"[0-9a-f]{40}", str(expected)):
            raise RuntimeError("Invalid Fresh file blob fingerprint")
        path = repo_root / relative
        if not path.is_file() or git_blob_id(path.read_bytes()) != expected:
            raise RuntimeError("Fresh protocol drift detected: " + relative)
    canary = (repo_root / "local_skills_daily_canary.py").read_text(encoding="utf-8")
    workflow = (repo_root / ".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")
    if not all(part in canary for part in (
        "pipeline.MAX_QUALITY_RETRIES = 0",
        "pipeline.ENABLE_DETERMINISTIC_PUBLICATION_RESCUE = False",
        'raise RuntimeError("Cross-source Fresh candidate escaped source filter")',
        "Once one article-analysis provider call has happened",
        '"Inspect: An open-source framework for large language model evaluations"',
    )):
        raise RuntimeError("Fresh immutable retry/source/holdout contract drift")
    required = {
        "GITHUB_FETCH_LIMIT": 50, "HN_FETCH_LIMIT": 50,
        "ARXIV_FETCH_LIMIT": 50, "OFFICIAL_VENDOR_FETCH_LIMIT": 50,
        "MAX_SCREENING_CANDIDATES": 200, "SCREENING_BATCH_SIZE": 25,
        "GLOBAL_CALIBRATION_BATCH_SIZE": 50,
        "GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET": 12,
    }
    for key, count in required.items():
        if _workflow_value(workflow, key) != count:
            raise RuntimeError("Fresh configured bounds drift: " + key)
    if manifest.get("workflow_limits") != required:
        raise RuntimeError("Fresh registered workflow limits drift")
    if manifest.get("max_deep_dive_sends") != 1 or manifest.get("max_quality_retries") != 0:
        raise RuntimeError("Fresh attempt budget or retry protocol altered")
    # Source filter follows shared acquisition/dedupe. Max 50 screened per
    # explicit source. Per-batch figures are *logical* calls only; transport
    # fallback attempts can consume more provider quota.
    expected_logical = {"screening": 2, "calibration": 1, "deep_dive": 1}
    if manifest.get("max_logical_calls_per_exact_source") != expected_logical:
        raise RuntimeError("Fresh registered logical call budget drift")
    return {
        "protocol": manifest["protocol"],
        "source": source or "unspecified_legacy_canary",
        "file_fingerprints_verified": len(files),
        "max_logical_calls_per_exact_source": expected_logical,
        "actual_transport_attempts": "NOT_BOUNDED_BY_THIS_OFFLINE_CHECK",
        "actual_provider_rpm_rpd_remaining": "NOT_MEASURED",
        "quality_measured": False,
        "safe_to_start_without_quota_review": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="", choices=sorted(SOURCES) + [""])
    args = parser.parse_args()
    print(json.dumps(validate(source=args.source), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
