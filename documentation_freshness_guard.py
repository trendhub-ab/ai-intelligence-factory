#!/usr/bin/env python3
"""Fail closed when canonical Production documentation drifts from live contracts."""
from __future__ import annotations

import ast
import re
from pathlib import Path


SPEC_PATH = "AI_Intelligence_Factory_最終仕様書.md"
README_PATH = "README.md"
QUOTA_PATH = "GEMINI_QUOTA_SETUP.md"
PRODUCTION_PATH = "production_pipeline.py"
ONE_SHOT_PATH = ".github/workflows/daily-one-shot.yml"
DAILY_PATH = ".github/workflows/daily.yml"
PENDING_RETRY_PATH = "pending_retry_validation.py"
INVENTORY_WORKFLOW_PATH = ".github/workflows/inventory-bootstrap.yml"
SUBSCRIBER_BRIEF_WORKFLOW_PATH = ".github/workflows/subscriber-decision-brief.yml"
MEMBER_PRESENTATION_WORKFLOW_PATH = ".github/workflows/member-presentation-sync.yml"

FLASH_BUDGET_VARS = (
    "GEMINI_36_FLASH_DAILY_BUDGET",
    "GEMINI_37_FLASH_DAILY_BUDGET",
    "GEMINI_35_FLASH_DAILY_BUDGET",
)


def _read(root: Path, path: str) -> str:
    return (root / path).read_text(encoding="utf-8")


def active_runtime_modules(production_source: str) -> list[str]:
    """Return local modules imported by install_runtime_layers in source order."""
    tree = ast.parse(production_source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "install_runtime_layers":
            modules: list[str] = []
            for child in node.body:
                if isinstance(child, ast.Import):
                    modules.extend(alias.name for alias in child.names)
            return modules
    raise ValueError("install_runtime_layers() not found in production_pipeline.py")


def runtime_layer_errors(production_source: str, spec_text: str) -> list[str]:
    errors: list[str] = []
    for module in active_runtime_modules(production_source):
        marker = f"`{module}.py`"
        if marker not in spec_text:
            errors.append(
                f"Canonical specification is stale: active runtime layer {marker} is undocumented"
            )
    return errors


def baseline_errors(spec_text: str, readme_text: str) -> list[str]:
    errors: list[str] = []
    for marker in (
        "Run209",
        "Run210",
        "Run211",
        "Daily workflowはPAUSED",
        "Documentation Freshness Guard",
    ):
        if marker not in spec_text:
            errors.append(f"Canonical specification missing current marker: {marker}")

    for marker in (
        "Run209",
        "Run210",
        "Run211",
        "**Daily:** PAUSED",
        "Documentation Freshness Guard",
    ):
        if marker not in readme_text:
            errors.append(f"README missing current marker: {marker}")
    return errors


def quota_contract_errors(
    one_shot_text: str,
    daily_text: str,
    pending_retry_text: str,
    quota_text: str,
    spec_text: str,
) -> list[str]:
    errors: list[str] = []

    # The 18/20 margin is a safety ceiling. Canonical docs may never silently
    # drift toward the provider limit when workflow still caps at 18.
    for var in FLASH_BUDGET_VARS:
        expected = f'{var}: "18"'
        if expected not in one_shot_text:
            errors.append(f"ONE-SHOT Flash safety ceiling changed or missing: {expected}")

    if "18 requests/day" not in quota_text or "18/20" not in quota_text:
        errors.append("Gemini quota specification no longer documents the 18/20 safety margin")
    if "pre-send reservationを巻き戻さない" not in spec_text:
        errors.append("Canonical specification missing Run209 timeout fail-closed contract")
    if "timeoutだからといって巻き戻しません" not in quota_text:
        errors.append("Gemini quota specification missing timeout reservation fail-closed wording")
    if "Google AI Studio Rate Limits" not in quota_text:
        errors.append("Gemini quota specification must keep AI Studio Rate Limits as external source of truth")

    # Daily is intentionally a hard-disabled stub; do not infer full Production
    # values from it or allow a docs update to accidentally imply it is active.
    if "[PAUSED]" not in daily_text or "if: ${{ false }}" not in daily_text:
        errors.append("Daily workflow is no longer hard PAUSED; canonical docs must be reviewed")

    budget_match = re.search(
        r"FAST_LANE_PENDING_RETRY_REQUEST_BUDGET\s*=\s*(\d+)",
        pending_retry_text,
    )
    cooldown_match = re.search(
        r"FAST_LANE_503_COOLDOWN_THRESHOLD\s*=\s*(\d+)",
        pending_retry_text,
    )
    if not budget_match:
        errors.append("Pending Retry fast-lane request budget constant is missing")
    elif budget_match.group(1) != "3":
        errors.append(
            "Pending Retry fast-lane request budget changed from 3; update canonical docs and guard deliberately"
        )
    if not cooldown_match:
        errors.append("Pending Retry fast-lane 503 cooldown constant is missing")
    elif cooldown_match.group(1) != "1":
        errors.append(
            "Pending Retry fast-lane 503 cooldown changed from 1; update canonical docs and guard deliberately"
        )

    for marker in (
        "最大3 requests",
        "1回目のHTTP 503",
        "Reader Value repair",
    ):
        if marker not in quota_text and marker not in spec_text:
            errors.append(f"Pending Retry canonical contract missing marker: {marker}")

    stale_phrase = "`daily.yml`では`GEMINI_PENDING_RETRY_REQUEST_BUDGET=2`"
    if stale_phrase in quota_text:
        errors.append("Gemini quota specification still contains obsolete active-Daily Pending Retry wording")

    return errors


def _workflow_run_block(text: str) -> str:
    if "workflow_run:" not in text:
        return ""
    tail = text.split("workflow_run:", 1)[1]
    return tail.split("types: [completed]", 1)[0]


def member_product_sync_errors(
    inventory_text: str,
    subscriber_brief_text: str,
    member_presentation_text: str,
    spec_text: str,
    readme_text: str,
) -> list[str]:
    """Protect the zero-Gemini source -> brief -> presentation ordering contract."""
    errors: list[str] = []

    if "run-name: Subscriber Inventory Bootstrap [${{ inputs.mode }}]" not in inventory_text:
        errors.append("Inventory workflow must expose plan/apply in run-name for safe downstream filtering")

    subscriber_block = _workflow_run_block(subscriber_brief_text)
    for upstream in (
        "Daily Intelligence & Content Pipeline",
        "Daily Intelligence & Content Pipeline [ONE-SHOT]",
        "Subscriber Inventory Bootstrap",
    ):
        if upstream not in subscriber_block:
            errors.append(f"Subscriber Decision Brief missing upstream workflow_run source: {upstream}")

    if "github.event.workflow_run.name != 'Subscriber Inventory Bootstrap'" not in subscriber_brief_text:
        errors.append("Subscriber Decision Brief no longer distinguishes Inventory Bootstrap from other upstream runs")
    if "contains(github.event.workflow_run.display_title, '[apply]')" not in subscriber_brief_text:
        errors.append("Inventory plan could fan out into writes; apply-only downstream filter is missing")

    presentation_block = _workflow_run_block(member_presentation_text)
    if "Subscriber Decision Brief Sync" not in presentation_block:
        errors.append("Member Presentation must run after Subscriber Decision Brief Sync")
    for forbidden in (
        "Daily Intelligence & Content Pipeline",
        "Subscriber Inventory Bootstrap",
    ):
        if forbidden in presentation_block:
            errors.append(
                f"Member Presentation is racing its source again; direct workflow_run trigger found: {forbidden}"
            )

    lock_marker = "group: member-derived-notion-writes"
    if lock_marker not in subscriber_brief_text or lock_marker not in member_presentation_text:
        errors.append("Derived member Notion writers must share the member-derived-notion-writes lock")

    if "GEMINI_API_KEY" in subscriber_brief_text or "GEMINI_API_KEY" in member_presentation_text:
        errors.append("Derived member sync workflows must remain zero-Gemini")

    for marker in (
        "Run211",
        "Subscriber Decision Brief Sync",
        "Member Presentation Sync",
        "Inventory plan",
    ):
        if marker not in spec_text:
            errors.append(f"Canonical specification missing member sync marker: {marker}")
    for marker in ("Run211", "Subscriber Decision Brief Sync", "Member Presentation Sync"):
        if marker not in readme_text:
            errors.append(f"README missing member sync marker: {marker}")

    return errors


def validate(root: str | Path = ".") -> list[str]:
    root_path = Path(root)
    spec_text = _read(root_path, SPEC_PATH)
    readme_text = _read(root_path, README_PATH)
    quota_text = _read(root_path, QUOTA_PATH)
    production_source = _read(root_path, PRODUCTION_PATH)
    one_shot_text = _read(root_path, ONE_SHOT_PATH)
    daily_text = _read(root_path, DAILY_PATH)
    pending_retry_text = _read(root_path, PENDING_RETRY_PATH)
    inventory_text = _read(root_path, INVENTORY_WORKFLOW_PATH)
    subscriber_brief_text = _read(root_path, SUBSCRIBER_BRIEF_WORKFLOW_PATH)
    member_presentation_text = _read(root_path, MEMBER_PRESENTATION_WORKFLOW_PATH)

    errors: list[str] = []
    errors.extend(runtime_layer_errors(production_source, spec_text))
    errors.extend(baseline_errors(spec_text, readme_text))
    errors.extend(
        quota_contract_errors(
            one_shot_text,
            daily_text,
            pending_retry_text,
            quota_text,
            spec_text,
        )
    )
    errors.extend(
        member_product_sync_errors(
            inventory_text,
            subscriber_brief_text,
            member_presentation_text,
            spec_text,
            readme_text,
        )
    )
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("[DOCUMENTATION FRESHNESS] FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("[DOCUMENTATION FRESHNESS] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
