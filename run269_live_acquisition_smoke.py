#!/usr/bin/env python3
"""Run269 live acquisition smoke for the Run268 source contract.

This diagnostic intentionally exercises only public network acquisition primitives.
It does NOT import ``pipeline``, call Gemini/model providers, access Notion, mutate
runtime state, publish content, or write any production database.

The report is written before any fail-closed exit so an operator can see exactly
which vendor/network surface failed on the GitHub-hosted runner.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import requests

from business_source_acquisition import (
    HN_AI_QUERIES,
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


def _probe_vendor(vendor: dict[str, Any]) -> dict[str, Any]:
    logger = _CaptureLogger()
    rows = fetch_official_vendor_updates(
        2,
        normalize_item=normalize_item,
        http_get=requests.get,
        logger=logger,
        registry=(vendor,),
    )
    sample = rows[0] if rows else {}
    details = sample.get("sourceDetails") or {}
    return {
        "vendor": vendor["vendor"],
        "region": vendor["region"],
        "release_url": vendor["release_url"],
        "ok": bool(rows),
        "candidate_count": len(rows),
        "sample_title": sample.get("nameWithOwner") or "",
        "sample_primary_url": sample.get("primaryUrl") or "",
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
    for row in rows[:10]:
        details = row.get("sourceDetails") or {}
        samples.append(
            {
                "title": row.get("nameWithOwner") or "",
                "primary_url": row.get("primaryUrl") or "",
                "points": row.get("stargazerCount") or 0,
                "comments": details.get("comments") or 0,
                "query": details.get("query") or "",
            }
        )
    return {
        "ok": len(rows) >= 5,
        "candidate_count": len(rows),
        "query_count": len(HN_AI_QUERIES),
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
            "successful": len(successful),
            "failed": len(failed),
            "us_success": us_success,
            "cn_success": cn_success,
        },
        "vendors": vendors,
        "hackernews": hn,
    }


def _print_human_summary(report: dict[str, Any]) -> None:
    summary = report["vendor_summary"]
    print(
        "RUN269_VENDOR_SUMMARY "
        f"configured={summary['configured']} successful={summary['successful']} "
        f"failed={summary['failed']} us_success={summary['us_success']} "
        f"cn_success={summary['cn_success']}"
    )
    for row in report["vendors"]:
        state = "PASS" if row["ok"] else "FAIL"
        print(
            f"RUN269_VENDOR_{state} vendor={row['vendor']} region={row['region']} "
            f"candidates={row['candidate_count']} url={row['release_url']}"
        )
        for warning in row["warnings"]:
            print(f"  warning={warning}")
    hn = report["hackernews"]
    print(
        f"RUN269_HN_{'PASS' if hn['ok'] else 'FAIL'} "
        f"candidates={hn['candidate_count']} queries={hn['query_count']}"
    )
    for sample in hn["samples"][:5]:
        print(f"  HN_SAMPLE points={sample['points']} comments={sample['comments']} title={sample['title'][:120]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="run269-live-acquisition-report.json")
    parser.add_argument("--hn-limit", type=int, default=20)
    parser.add_argument(
        "--require-all-vendors",
        action="store_true",
        help="Fail if any configured official vendor produces zero candidates.",
    )
    args = parser.parse_args()

    report = build_live_report(max(5, args.hn_limit))
    path = Path(args.report)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print_human_summary(report)

    failures: list[str] = []
    if not report["hackernews"]["ok"]:
        failures.append("HackerNews returned fewer than 5 AI reaction candidates")
    summary = report["vendor_summary"]
    if summary["successful"] < 6:
        failures.append("OfficialVendor coverage below 6/11")
    if summary["us_success"] < 2:
        failures.append("OfficialVendor US coverage below 2/3")
    if summary["cn_success"] < 4:
        failures.append("OfficialVendor CN coverage below 4/8")
    if args.require_all_vendors and summary["failed"]:
        failed_names = [row["vendor"] for row in report["vendors"] if not row["ok"]]
        failures.append("Configured vendors with zero candidates: " + ", ".join(failed_names))

    if failures:
        print("RUN269_LIVE_ACQUISITION_SMOKE=FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("RUN269_LIVE_ACQUISITION_SMOKE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
