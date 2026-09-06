#!/usr/bin/env python3
"""Run269 live acquisition smoke for the Run268/269 source contract.

This diagnostic exercises only public network acquisition primitives. It does NOT
import ``pipeline``, call Gemini/model providers, access Notion, mutate runtime state,
publish content, or write any production database.

Run269 distinguishes transport reachability from candidate quality: a vendor passes
only when at least one structured update candidate is extracted. Page-level fallback
is reported but cannot silently satisfy the strict live smoke.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import requests

from run269_acquisition_precision import (
    HN_AI_QUERIES,
    HN_LOOKBACK_DAYS,
    OFFICIAL_VENDOR_REGISTRY,
    fetch_hackernews_ai_reactions,
    fetch_official_vendor_updates,
)
from source_normalization import normalize_item


class _CaptureLogger:
    def __init__(self) -> None:
        self.info_messages: list[str] = []
        self.warning_messages: list[str] = []

    def info(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self.info_messages.append(str(message))

    def warning(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self.warning_messages.append(str(message))


def _is_structured_kind(kind: str) -> bool:
    return str(kind or "").startswith("structured_")


def _probe_vendor(vendor: dict[str, Any]) -> dict[str, Any]:
    logger = _CaptureLogger()
    rows = fetch_official_vendor_updates(
        3,
        normalize_item=normalize_item,
        http_get=requests.get,
        logger=logger,
        registry=(vendor,),
    )
    kinds = [str(((row.get("sourceDetails") or {}).get("vendor_record_kind") or "")) for row in rows]
    structured_count = sum(1 for kind in kinds if _is_structured_kind(kind))
    fallback_count = sum(1 for kind in kinds if kind == "page_fallback")
    sample = next(
        (
            row for row in rows
            if _is_structured_kind((row.get("sourceDetails") or {}).get("vendor_record_kind") or "")
        ),
        rows[0] if rows else {},
    )
    details = sample.get("sourceDetails") or {}
    return {
        "vendor": vendor["vendor"],
        "region": vendor["region"],
        "release_url": vendor["release_url"],
        "transport_ok": bool(rows),
        "ok": structured_count > 0,
        "candidate_count": len(rows),
        "structured_count": structured_count,
        "fallback_count": fallback_count,
        "sample_kind": details.get("vendor_record_kind") or "",
        "sample_title": sample.get("nameWithOwner") or "",
        "sample_primary_url": sample.get("primaryUrl") or "",
        "sample_published_at": sample.get("publishedAt"),
        "sample_revision": details.get("candidate_revision") or "",
        "warnings": logger.warning_messages,
    }


def _probe_hackernews(limit: int) -> dict[str, Any]:
    logger = _CaptureLogger()
    rows = fetch_hackernews_ai_reactions(
        limit,
        normalize_item=normalize_item,
        http_get=requests.get,
        logger=logger,
        queries=HN_AI_QUERIES,
    )
    samples = []
    missing_match_metadata = 0
    for row in rows[:10]:
        details = row.get("sourceDetails") or {}
        matched_query = details.get("matched_query") or ""
        if not matched_query:
            missing_match_metadata += 1
        samples.append(
            {
                "title": row.get("nameWithOwner") or "",
                "primary_url": row.get("primaryUrl") or "",
                "published_at": row.get("publishedAt"),
                "points": row.get("stargazerCount") or 0,
                "comments": details.get("comments") or 0,
                "matched_query": matched_query,
            }
        )
    return {
        "ok": len(rows) >= 5 and missing_match_metadata == 0,
        "candidate_count": len(rows),
        "query_count": len(HN_AI_QUERIES),
        "lookback_days": HN_LOOKBACK_DAYS,
        "missing_match_metadata": missing_match_metadata,
        "samples": samples,
        "warnings": logger.warning_messages,
    }


def build_live_report(hn_limit: int = 20) -> dict[str, Any]:
    vendors = [_probe_vendor(vendor) for vendor in OFFICIAL_VENDOR_REGISTRY]
    hn = _probe_hackernews(hn_limit)
    successful = [row for row in vendors if row["ok"]]
    failed = [row for row in vendors if not row["ok"]]
    us_success = sum(1 for row in successful if row["region"] == "US")
    cn_success = sum(1 for row in successful if row["region"] == "CN")
    return {
        "run": "Run269 Live Acquisition Smoke",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "safety_contract": {
            "gemini_model_calls": 0,
            "notion_writes": 0,
            "production_db_writes": 0,
            "publication_actions": 0,
            "pipeline_imported": False,
        },
        "vendor_summary": {
            "configured": len(vendors),
            "structured_successful": len(successful),
            "structured_failed": len(failed),
            "us_structured_success": us_success,
            "cn_structured_success": cn_success,
            "fallback_only": sum(1 for row in vendors if row["transport_ok"] and not row["ok"]),
        },
        "vendors": vendors,
        "hackernews": hn,
    }


def _print_human_summary(report: dict[str, Any]) -> None:
    summary = report["vendor_summary"]
    print(
        "RUN269_VENDOR_SUMMARY "
        f"configured={summary['configured']} structured_successful={summary['structured_successful']} "
        f"structured_failed={summary['structured_failed']} us={summary['us_structured_success']} "
        f"cn={summary['cn_structured_success']} fallback_only={summary['fallback_only']}"
    )
    for row in report["vendors"]:
        state = "PASS" if row["ok"] else "FAIL"
        print(
            f"RUN269_VENDOR_{state} vendor={row['vendor']} region={row['region']} "
            f"structured={row['structured_count']} fallback={row['fallback_count']} "
            f"sample_kind={row['sample_kind']} url={row['release_url']}"
        )
        if row["sample_title"]:
            print(f"  sample={row['sample_title'][:180]}")
        for warning in row["warnings"]:
            print(f"  warning={warning}")
    hn = report["hackernews"]
    print(
        f"RUN269_HN_{'PASS' if hn['ok'] else 'FAIL'} candidates={hn['candidate_count']} "
        f"queries={hn['query_count']} lookback_days={hn['lookback_days']}"
    )
    for sample in hn["samples"][:8]:
        print(
            f"  HN_SAMPLE points={sample['points']} comments={sample['comments']} "
            f"query={sample['matched_query']} title={sample['title'][:120]}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="run269-live-acquisition-report.json")
    parser.add_argument("--hn-limit", type=int, default=20)
    parser.add_argument(
        "--require-all-vendors",
        action="store_true",
        help="Fail if any configured vendor lacks a structured update candidate.",
    )
    args = parser.parse_args()

    report = build_live_report(max(5, args.hn_limit))
    path = Path(args.report)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print_human_summary(report)

    failures: list[str] = []
    if not report["hackernews"]["ok"]:
        failures.append("HackerNews returned insufficient or untraceable exact-title AI reaction candidates")
    summary = report["vendor_summary"]
    if summary["structured_successful"] < 6:
        failures.append("OfficialVendor structured coverage below 6/11")
    if summary["us_structured_success"] < 2:
        failures.append("OfficialVendor structured US coverage below 2/3")
    if summary["cn_structured_success"] < 4:
        failures.append("OfficialVendor structured CN coverage below 4/8")
    if args.require_all_vendors and summary["structured_failed"]:
        failed_names = [row["vendor"] for row in report["vendors"] if not row["ok"]]
        failures.append("Configured vendors without structured candidates: " + ", ".join(failed_names))

    if failures:
        print("RUN269_LIVE_ACQUISITION_SMOKE=FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("RUN269_LIVE_ACQUISITION_SMOKE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
