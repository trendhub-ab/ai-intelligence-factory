#!/usr/bin/env python3
"""Run262: fail closed when canonical docs drift from the live Run261 contract.

Run261 fixed two live-only production defects:
- quality retry must be Gemini 3.8-first at the real `_call_deep_dive_pool` entrypoint;
- successful ONE-SHOT fan-out is explicit GH_PAT-authenticated workflow_dispatch,
  not passive ONE-SHOT workflow_run chaining.

The older Documentation Freshness Guard protected broad markers but allowed the
canonical spec to retain the obsolete Run260/Run259 mechanism. This guard makes
that specific current contract content-addressable by required CI without any
network/provider call.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "AI_Intelligence_Factory_最終仕様書.md"
ONE_SHOT = ROOT / ".github" / "workflows" / "daily-one-shot.yml"
NOTE_READY = ROOT / ".github" / "workflows" / "note-ready-sync.yml"
SUBSCRIBER = ROOT / ".github" / "workflows" / "subscriber-decision-brief.yml"
CROSS_DB = ROOT / ".github" / "workflows" / "cross-db-contract-guard.yml"
ROUTING = ROOT / "run260_gemini_model_routing.py"
RUN261_DOC = ROOT / "docs" / "reference" / "RUN261_LIVE_ROUTING_AND_FANOUT_REPAIR.md"
QUOTA_DOC = ROOT / "GEMINI_QUOTA_SETUP.md"

UPSTREAM = "Daily Intelligence & Content Pipeline [ONE-SHOT]"
DIRECT_TARGETS = {
    "note-ready-sync.yml": NOTE_READY,
    "subscriber-decision-brief.yml": SUBSCRIBER,
    "cross-db-contract-guard.yml": CROSS_DB,
}

REQUIRED_SPEC_MARKERS = (
    "Article Model Routing Baseline: **Run261",
    "ONE-SHOT Downstream Fan-out Baseline: **Run261",
    "Run261 article model routing",
    "`_call_deep_dive_pool`",
    "`gemini-3.7-flash`",
    "`gemini-3.8-flash`",
    "note-ready-sync.yml",
    "subscriber-decision-brief.yml",
    "cross-db-contract-guard.yml",
    "`${{ secrets.GH_PAT }}`",
    "docs/reference/RUN261_LIVE_ROUTING_AND_FANOUT_REPAIR.md",
)

FORBIDDEN_SPEC_MARKERS = (
    "Subscriber Decision Brief Sync` の実在するworkflow_run上流は **`Daily Intelligence & Content Pipeline [ONE-SHOT]",
    "ONE-SHOT完了後の `workflow_run` fan-out",
    "現在のArticle Model Routing正本はRun260。",
    "現在のChatOps Fan-out正本はRun259。",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _workflow_run_block(text: str) -> str:
    match = re.search(
        r"(?ms)^\s{2}workflow_run:\s*\n(?P<body>.*?)(?=^\s{2}[A-Za-z_][A-Za-z0-9_-]*:\s*$|^permissions:|^concurrency:|^jobs:|\Z)",
        text,
    )
    return match.group("body") if match else ""


def audit_texts(
    *,
    spec: str,
    one_shot: str,
    note_ready: str,
    subscriber: str,
    cross_db: str,
    routing: str,
    run261_doc: str,
    quota_doc: str,
) -> list[str]:
    failures: list[str] = []

    for marker in REQUIRED_SPEC_MARKERS:
        if marker not in spec:
            failures.append(f"canonical_spec_missing_run261_contract:{marker}")
    for marker in FORBIDDEN_SPEC_MARKERS:
        if marker in spec:
            failures.append(f"canonical_spec_retains_obsolete_contract:{marker}")

    # Model-routing docs must describe the live entrypoint, not only Run260's original
    # direct `_call_model_pool` wrapper.
    for marker in (
        "_call_deep_dive_pool",
        'QUALITY_MODEL = "gemini-3.8-flash"',
        'PRIMARY_MODEL = "gemini-3.7-flash"',
        "pipeline_module._call_deep_dive_pool = call_deep_dive_pool_run261",
    ):
        if marker not in routing:
            failures.append(f"run261_live_routing_missing:{marker}")

    # Explicit fan-out is the sole direct ONE-SHOT downstream authority.
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

    # Direct targets must remain manually dispatchable and must not also subscribe
    # passively to ONE-SHOT, otherwise a future GitHub behavior change can double-write.
    for target, path in DIRECT_TARGETS.items():
        text = {
            "note-ready-sync.yml": note_ready,
            "subscriber-decision-brief.yml": subscriber,
            "cross-db-contract-guard.yml": cross_db,
        }[target]
        if not re.search(r"(?m)^\s{2}workflow_dispatch:\s*$", text):
            failures.append(f"one_shot_target_not_dispatchable:{target}")
        if UPSTREAM in _workflow_run_block(text):
            failures.append(f"one_shot_passive_duplicate_trigger:{target}")

    # Subscriber keeps only the independent Inventory apply completion path.
    subscriber_block = _workflow_run_block(subscriber)
    if "Subscriber Inventory Bootstrap" not in subscriber_block:
        failures.append("subscriber_inventory_trigger_missing")
    if "contains(github.event.workflow_run.display_title, '[apply]')" not in subscriber:
        failures.append("subscriber_inventory_apply_filter_missing")

    # Canonical supporting docs must both recognize Run261 as current.
    for marker in ("Run261", "_call_deep_dive_pool", "GH_PAT"):
        if marker not in run261_doc:
            failures.append(f"run261_reference_missing:{marker}")
    for marker in ("Run261", "3.8", "GH_PAT"):
        if marker not in quota_doc:
            failures.append(f"quota_doc_missing_run261_contract:{marker}")

    return list(dict.fromkeys(failures))


def audit(root: Path = ROOT) -> list[str]:
    return audit_texts(
        spec=(root / SPEC.relative_to(ROOT)).read_text(encoding="utf-8"),
        one_shot=(root / ONE_SHOT.relative_to(ROOT)).read_text(encoding="utf-8"),
        note_ready=(root / NOTE_READY.relative_to(ROOT)).read_text(encoding="utf-8"),
        subscriber=(root / SUBSCRIBER.relative_to(ROOT)).read_text(encoding="utf-8"),
        cross_db=(root / CROSS_DB.relative_to(ROOT)).read_text(encoding="utf-8"),
        routing=(root / ROUTING.relative_to(ROOT)).read_text(encoding="utf-8"),
        run261_doc=(root / RUN261_DOC.relative_to(ROOT)).read_text(encoding="utf-8"),
        quota_doc=(root / QUOTA_DOC.relative_to(ROOT)).read_text(encoding="utf-8"),
    )


def main() -> None:
    failures = audit()
    if failures:
        print("RUN262_DOCUMENTATION_CONTRACT_GUARD=FAIL")
        for item in failures:
            print("-", item)
        raise SystemExit(1)
    print("RUN262_DOCUMENTATION_CONTRACT_GUARD=PASS")


if __name__ == "__main__":
    main()
