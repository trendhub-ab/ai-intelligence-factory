#!/usr/bin/env python3
"""Zero-provider governance check: AIIF's business purpose remains reviewable.

This protects documentation linkage and an explicit PR business-impact review.
It does not claim to prove the business value of any code change.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = "docs/AIIF_BUSINESS_NORTH_STAR.md"
HEADINGS = (
    "事業目的",
    "顧客価値と実測",
    "既存資産と重複回避",
    "E2Eと未接続区間",
    "安全・費用・ロールバック",
    "オーナー承認",
)
PLACEHOLDER = re.compile(r"^\s*[（(].*記入.*[）)]\s*$")
REQUIRED_CHARTR_TOKENS = (
    "PAID_PRODUCT_CONTRACT.md",
    "Use-Decision",
    "月額1,980円",
    "実有料顧客10人",
    "無料note",
    "Decision Brief",
    "Content Intelligence DB",
    "note投稿管理DB",
    "アイキャッチ",
    "Notion",
    "非公開下書き",
    "human-only",
    "AIIF Next",
    "Next",
    "旧Production",
    "PR",
)


class AlignmentError(ValueError):
    pass


def _read(root: Path, path: str) -> str:
    file = root / path
    if not file.is_file():
        raise AlignmentError("BUSINESS_GUARD_FILE_MISSING:" + path)
    return file.read_text(encoding="utf-8")


def verify_repository(root: Path = ROOT) -> None:
    canonical = _read(root, SOURCE)
    agents = _read(root, "AGENTS.md")
    template = _read(root, ".github/PULL_REQUEST_TEMPLATE.md")
    product = _read(root, "PAID_PRODUCT_CONTRACT.md")
    for token in REQUIRED_CHARTR_TOKENS:
        if token not in canonical:
            raise AlignmentError("BUSINESS_GUARD_CHARTER_DRIFT:" + token)
    if SOURCE not in agents or "PAID_PRODUCT_CONTRACT.md" not in agents:
        raise AlignmentError("BUSINESS_GUARD_AGENT_REFERENCE_MISSING")
    if "月額1,980円" not in product or "Use-Decision" not in product:
        raise AlignmentError("BUSINESS_GUARD_PRODUCT_CONTRACT_DRIFT")
    if SOURCE not in template:
        raise AlignmentError("BUSINESS_GUARD_TEMPLATE_REFERENCE_MISSING")
    for heading in HEADINGS:
        if not re.search(r"(?m)^###\s+" + re.escape(heading) + r"\s*$", template):
            raise AlignmentError("BUSINESS_GUARD_TEMPLATE_SECTION_MISSING:" + heading)


def verify_pr_body(body: str | None) -> None:
    if not isinstance(body, str) or SOURCE not in body:
        raise AlignmentError("BUSINESS_GUARD_PR_MISSING_CANONICAL_REFERENCE")
    for i, heading in enumerate(HEADINGS):
        expression = r"(?ms)^###\s+" + re.escape(heading) + r"\s*\n(.*?)(?=^###\s+|\Z)"
        match = re.search(expression, body)
        if not match:
            raise AlignmentError("BUSINESS_GUARD_PR_SECTION_MISSING:" + heading)
        # Ignore template comments; require a concrete nonplaceholder response.
        cleaned = re.sub(r"<!--.*?-->", "", match.group(1), flags=re.S)
        cleaned = " ".join(line.strip() for line in cleaned.splitlines()
                           if line.strip() and not line.strip().startswith("<!--"))
        if len(cleaned) < 14 or PLACEHOLDER.fullmatch(cleaned):
            raise AlignmentError("BUSINESS_GUARD_PR_SECTION_UNFILLED:" + heading)


def verify_event(path: str | None) -> None:
    if not path:
        return
    event_path = Path(path)
    if not event_path.is_file():
        raise AlignmentError("BUSINESS_GUARD_EVENT_UNAVAILABLE")
    payload = json.loads(event_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AlignmentError("BUSINESS_GUARD_EVENT_INVALID")
    pull = payload.get("pull_request")
    if pull is not None:
        if not isinstance(pull, dict):
            raise AlignmentError("BUSINESS_GUARD_PR_INVALID")
        verify_pr_body(pull.get("body"))


def main() -> int:
    try:
        verify_repository()
        verify_event(os.environ.get("GITHUB_EVENT_PATH"))
    except (AlignmentError, OSError, UnicodeError, ValueError) as exc:
        print("BUSINESS_NORTH_STAR_GUARD=FAIL " + str(exc), file=sys.stderr)
        return 1
    print("BUSINESS_NORTH_STAR_GUARD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
