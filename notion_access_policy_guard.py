#!/usr/bin/env python3
"""Static guard that keeps production code independent from Notion MCP SQL.

Policy:
- Production/runtime code must use the Notion Public API (or preconfigured Notion views).
- Notion MCP `query_data_sources` SQL mode is an operator-side convenience only and
  must never become a production dependency.
- This guard is deterministic and makes ZERO network/model requests.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable


FORBIDDEN_PATTERNS: dict[str, str] = {
    "query_data_sources": "Notion MCP query_data_sources symbol",
    "query-data-sources": "Notion MCP query-data-sources tool name",
    '"mode": "sql"': "Notion MCP SQL mode payload",
    "'mode': 'sql'": "Notion MCP SQL mode payload",
    'mode="sql"': "Notion MCP SQL mode argument",
    "mode='sql'": "Notion MCP SQL mode argument",
}

SCANNED_SUFFIXES = {".py", ".yml", ".yaml"}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "tests"}
SKIP_FILES = {Path(__file__).name}


def find_forbidden_patterns(text: str) -> list[dict[str, str]]:
    """Return policy violations found in one source string."""
    violations: list[dict[str, str]] = []
    for pattern, reason in FORBIDDEN_PATTERNS.items():
        if pattern in text:
            violations.append({"pattern": pattern, "reason": reason})
    return violations


def iter_production_files(root: Path) -> Iterable[Path]:
    """Yield production Python/workflow files while excluding tests and this guard."""
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SCANNED_SUFFIXES:
            continue
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        yield path


def scan_repository(root: Path) -> list[dict[str, str]]:
    """Scan production files and return all MCP-SQL policy violations."""
    failures: list[dict[str, str]] = []
    for path in iter_production_files(root):
        text = path.read_text(encoding="utf-8")
        for item in find_forbidden_patterns(text):
            failures.append(
                {
                    "file": str(path.relative_to(root)),
                    "pattern": item["pattern"],
                    "reason": item["reason"],
                }
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    root = Path(args[0]).resolve() if args else Path(__file__).resolve().parent
    failures = scan_repository(root)
    result = {
        "policy": "notion_public_api_and_view_first",
        "mcp_sql_production_dependency": False,
        "zero_network_calls": True,
        "violations": failures,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if failures:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
