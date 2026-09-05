#!/usr/bin/env python3
"""Static guard that keeps every production Notion DB independent from MCP SQL.

Policy:
- Production/runtime code uses Notion Public API.
- Routine operator audits use registered saved Notion views where the DB is directly addressable.
- Secret-only destinations (Public mirror) use a Public API contract guard.
- Notion MCP SQL must never become a production or audit dependency.
- This guard is deterministic and makes ZERO network/model requests.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from member_presentation_identity import (
    CANONICAL_DATABASE_ID as MEMBER_PRESENTATION_CANONICAL_DATABASE_ID,
    CANONICAL_DATA_SOURCE_ID as MEMBER_PRESENTATION_CANONICAL_DATA_SOURCE_ID,
)


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
AUDIT_MANIFEST = "notion_audit_views.json"
VIEW_ID_RE = re.compile(r"^view://[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
EXPECTED_AUDIT_DATABASE_KEYS = {
    "content_intelligence",
    "technology_intelligence",
    "decision_history",
    "subscriber_bridge",
    "member_presentation",
    "decision_monthly",
    "evidence_ledger",
    "note_posting",
    "public_mirror",
}


def find_forbidden_patterns(text: str) -> list[dict[str, str]]:
    """Return MCP-SQL policy violations found in one source string."""
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


def load_audit_manifest(root: Path) -> dict[str, Any]:
    path = root / AUDIT_MANIFEST
    if not path.exists():
        raise ValueError(f"missing {AUDIT_MANIFEST}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("audit manifest must be an object")
    return data


def _validate_member_presentation_identity(item: dict[str, Any]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    actual_db = str(item.get("database_id") or "").strip()
    actual_ds = str(item.get("data_source_id") or "").strip()
    if actual_db != MEMBER_PRESENTATION_CANONICAL_DATABASE_ID:
        failures.append(
            {
                "database": "member_presentation",
                "reason": (
                    "stale_canonical_id: field=database_id "
                    f"expected={MEMBER_PRESENTATION_CANONICAL_DATABASE_ID} actual={actual_db}"
                ),
            }
        )
    if actual_ds != MEMBER_PRESENTATION_CANONICAL_DATA_SOURCE_ID:
        failures.append(
            {
                "database": "member_presentation",
                "reason": (
                    "stale_canonical_id: field=data_source_id "
                    f"expected={MEMBER_PRESENTATION_CANONICAL_DATA_SOURCE_ID} actual={actual_ds}"
                ),
            }
        )
    return failures


def validate_audit_manifest(data: dict[str, Any]) -> list[dict[str, str]]:
    """Ensure every production Notion DB has a SQL-free, current audit path."""
    failures: list[dict[str, str]] = []
    databases = data.get("databases")
    if not isinstance(databases, dict):
        return [{"database": "*", "reason": "missing databases map"}]

    missing = sorted(EXPECTED_AUDIT_DATABASE_KEYS - set(databases))
    extra = sorted(set(databases) - EXPECTED_AUDIT_DATABASE_KEYS)
    for key in missing:
        failures.append({"database": key, "reason": "missing audit contract"})
    for key in extra:
        failures.append({"database": key, "reason": "unregistered database key"})

    for key in sorted(EXPECTED_AUDIT_DATABASE_KEYS & set(databases)):
        item = databases.get(key) or {}
        mode = item.get("audit_mode")
        if mode not in {"view+public_api", "public_api"}:
            failures.append({"database": key, "reason": f"invalid audit_mode:{mode}"})
            continue

        views = item.get("views")
        if not isinstance(views, dict):
            failures.append({"database": key, "reason": "views must be an object"})
            continue

        if key == "public_mirror":
            if mode != "public_api":
                failures.append({"database": key, "reason": "public mirror must use Public API"})
            if item.get("guard") != "public_db_contract_guard.py":
                failures.append({"database": key, "reason": "missing public_db_contract_guard.py"})
            continue

        if not views:
            failures.append({"database": key, "reason": "saved audit view required"})
        for view_name, view_id in views.items():
            if not isinstance(view_id, str) or not VIEW_ID_RE.match(view_id):
                failures.append(
                    {"database": key, "reason": f"invalid view id for {view_name}:{view_id}"}
                )

        if not str(item.get("database_id") or "").strip():
            failures.append({"database": key, "reason": "database_id missing"})
        if not str(item.get("data_source_id") or "").strip():
            failures.append({"database": key, "reason": "data_source_id missing"})
        if key == "member_presentation":
            failures.extend(_validate_member_presentation_identity(item))

    return failures


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    root = Path(args[0]).resolve() if args else Path(__file__).resolve().parent
    code_failures = scan_repository(root)
    try:
        manifest_failures = validate_audit_manifest(load_audit_manifest(root))
    except Exception as exc:
        manifest_failures = [{"database": "*", "reason": str(exc)}]

    result = {
        "policy": "notion_public_api_and_view_first",
        "mcp_sql_production_dependency": False,
        "zero_network_calls": True,
        "registered_databases": len(EXPECTED_AUDIT_DATABASE_KEYS),
        "code_violations": code_failures,
        "manifest_violations": manifest_failures,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if code_failures or manifest_failures:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
