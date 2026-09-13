#!/usr/bin/env python3
"""Fail closed when live Gemini routing or ONE-SHOT fan-out safety drifts.

Historical documentation wording and Run numbers are intentionally not part of this
contract. The guard protects only executable Production invariants:
- article routing remains Gemini-only and keeps distinct primary/quality models;
- the quality path is installed at the real Deep Dive entrypoint;
- successful ONE-SHOT fan-out uses explicit GH_PAT-authenticated dispatch;
- direct downstream workflows remain manually dispatchable and do not also subscribe
  passively to ONE-SHOT, preventing duplicate writes.

The guard is zero-network and zero-provider.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ONE_SHOT = ROOT / ".github" / "workflows" / "daily-one-shot.yml"
NOTE_READY = ROOT / ".github" / "workflows" / "note-ready-sync.yml"
SUBSCRIBER = ROOT / ".github" / "workflows" / "subscriber-decision-brief.yml"
CROSS_DB = ROOT / ".github" / "workflows" / "cross-db-contract-guard.yml"
ROUTING = ROOT / "run260_gemini_model_routing.py"

UPSTREAM = "Daily Intelligence & Content Pipeline [ONE-SHOT]"
DIRECT_TARGETS = {
    "note-ready-sync.yml": NOTE_READY,
    "subscriber-decision-brief.yml": SUBSCRIBER,
    "cross-db-contract-guard.yml": CROSS_DB,
}


def _workflow_run_block(text: str) -> str:
    match = re.search(
        r"(?ms)^\s{2}workflow_run:\s*\n(?P<body>.*?)(?=^\s{2}[A-Za-z_][A-Za-z0-9_-]*:\s*$|^permissions:|^concurrency:|^jobs:|\Z)",
        text,
    )
    return match.group("body") if match else ""


def _literal_string_assignments(text: str) -> dict[str, str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    values: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                values[target] = node.value.value
    return values


def routing_errors(routing: str) -> list[str]:
    failures: list[str] = []
    values = _literal_string_assignments(routing)
    primary = values.get("PRIMARY_MODEL", "")
    quality = values.get("QUALITY_MODEL", "")

    if not primary.startswith("gemini-"):
        failures.append("provider_routing_primary_not_gemini")
    if not quality.startswith("gemini-"):
        failures.append("provider_routing_quality_not_gemini")
    if primary and quality and primary == quality:
        failures.append("provider_routing_primary_quality_not_distinct")

    lowered = routing.lower()
    for retired in ("groq", "qwen"):
        if retired in lowered:
            failures.append(f"provider_routing_retired_provider_reintroduced:{retired}")

    required_semantics = (
        "_call_deep_dive_pool",
        "call_deep_dive_pool_run261",
        "pipeline_module._call_deep_dive_pool = call_deep_dive_pool_run261",
        "QUALITY_MODEL",
        "PRIMARY_MODEL",
    )
    for marker in required_semantics:
        if marker not in routing:
            failures.append(f"provider_routing_live_quality_path_missing:{marker}")
    return failures


def fanout_errors(*, one_shot: str, note_ready: str, subscriber: str, cross_db: str) -> list[str]:
    failures: list[str] = []
    for marker in (
        "GH_TOKEN: ${{ secrets.GH_PAT }}",
        "GH_PAT is required for authoritative ONE-SHOT downstream fan-out",
        "if: ${{ success() }}",
    ):
        if marker not in one_shot:
            failures.append(f"one_shot_explicit_fanout_missing:{marker}")
    for target in DIRECT_TARGETS:
        if target not in one_shot:
            failures.append(f"one_shot_target_missing:{target}")

    texts = {
        "note-ready-sync.yml": note_ready,
        "subscriber-decision-brief.yml": subscriber,
        "cross-db-contract-guard.yml": cross_db,
    }
    for target, text in texts.items():
        if not re.search(r"(?m)^\s{2}workflow_dispatch:\s*$", text):
            failures.append(f"one_shot_target_not_dispatchable:{target}")
        if UPSTREAM in _workflow_run_block(text):
            failures.append(f"one_shot_passive_duplicate_trigger:{target}")

    subscriber_block = _workflow_run_block(subscriber)
    if "Subscriber Inventory Bootstrap" not in subscriber_block:
        failures.append("subscriber_inventory_trigger_missing")
    if "contains(github.event.workflow_run.display_title, '[apply]')" not in subscriber:
        failures.append("subscriber_inventory_apply_filter_missing")
    return failures


def audit_texts(*, one_shot: str, note_ready: str, subscriber: str, cross_db: str, routing: str) -> list[str]:
    failures = routing_errors(routing)
    failures.extend(
        fanout_errors(
            one_shot=one_shot,
            note_ready=note_ready,
            subscriber=subscriber,
            cross_db=cross_db,
        )
    )
    return list(dict.fromkeys(failures))


def audit(root: Path = ROOT) -> list[str]:
    return audit_texts(
        one_shot=(root / ONE_SHOT.relative_to(ROOT)).read_text(encoding="utf-8"),
        note_ready=(root / NOTE_READY.relative_to(ROOT)).read_text(encoding="utf-8"),
        subscriber=(root / SUBSCRIBER.relative_to(ROOT)).read_text(encoding="utf-8"),
        cross_db=(root / CROSS_DB.relative_to(ROOT)).read_text(encoding="utf-8"),
        routing=(root / ROUTING.relative_to(ROOT)).read_text(encoding="utf-8"),
    )


def main() -> None:
    failures = audit()
    if failures:
        print("PROVIDER_ROUTING_AND_FANOUT_GUARD=FAIL")
        for item in failures:
            print("-", item)
        raise SystemExit(1)
    print("PROVIDER_ROUTING_AND_FANOUT_GUARD=PASS")


if __name__ == "__main__":
    main()
