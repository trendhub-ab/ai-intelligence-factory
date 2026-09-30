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
LOCK = ROOT / "docs/audits/fresh-four-source-protocol-lock-v2.json"
SOURCES = frozenset({"GitHub", "HackerNews", "ArXiv", "OfficialVendor"})


def git_blob_id(contents: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(contents)).encode("ascii") + b"\0" + contents).hexdigest()


def _workflow_value(workflow: str, name: str) -> int:
    # Other Daily steps may declare similarly named budgets. Freeze only the
    # exact canary-capable Production entrypoint, not unrelated retry steps.
    anchor = "      - name: 通常Production entrypointを1回だけ実行"
    if workflow.count(anchor) != 1:
        raise RuntimeError("Fresh Production entrypoint definition changed")
    section = workflow.split(anchor, 1)[1].split("\n      - name:", 1)[0]
    if "run: python production_pipeline.py" not in section:
        raise RuntimeError("Fresh production command drift")
    prefix = name + ': "'
    matches = [
        line.strip().split('"')[1]
        for line in section.splitlines()
        if line.strip().startswith(prefix)
    ]
    if len(matches) != 1 or not matches[0].isdigit():
        raise RuntimeError("Expected exactly one frozen Fresh step setting: " + name)
    return int(matches[0])


def validate(*, repo_root: Path = ROOT, manifest_path: Path = LOCK, source: str = "") -> dict:
    if source not in SOURCES and source != "":
        raise RuntimeError("Invalid or unexpected Fresh source target")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("protocol") != "fresh-four-source-fallback-bounded-v2":
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
        "send_budget = FreshModelSendBudget()",
        "pipeline._generate_via_chat = send_budget.wrapped(original_send)",
        "pipeline._generate_via_chat = original_send",
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
    if manifest.get("max_article_candidates_after_send") != 1 or manifest.get("max_quality_retries") != 0:
        raise RuntimeError("Fresh article or quality retry protocol altered")
    from fresh_model_fallback_budget import (
        MAX_ARTICLE_SEND_SLOTS, MAX_PRE_ARTICLE_SEND_SLOTS, MAX_TOTAL_SEND_SLOTS,
    )
    hard_limits = {
        "total": MAX_TOTAL_SEND_SLOTS,
        "pre_article": MAX_PRE_ARTICLE_SEND_SLOTS,
        "article": MAX_ARTICLE_SEND_SLOTS,
    }
    if hard_limits != {"total": 10, "pre_article": 6, "article": 4}:
        raise RuntimeError("Fresh guarded model-send source cap drift")
    if manifest.get("max_provider_send_slots") != hard_limits:
        raise RuntimeError("Fresh registered model-send cap drift")
    # Read and fingerprint the exact Production 503 router, rather than falsely
    # claiming that limiting article candidates disables fallback.
    provider = (repo_root / "gemini_provider_resilience.py").read_text(encoding="utf-8")
    if not all(marker in provider for marker in (
        "for model_name in allowed_pool(pool)",
        "if code == 503:",
        "pipeline_module._generate_via_chat(",
    )):
        raise RuntimeError("Production distinct-model fallback contract drift")
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
        "max_provider_send_slots": hard_limits,
        "article_model_fallback": "PRESERVED_WITHIN_BOUND",
        "actual_transport_attempts": "SEND_INVOCATIONS_BOUNDED_SDK_SINGLE_ATTEMPT_RUNTIME_REQUIRED",
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
