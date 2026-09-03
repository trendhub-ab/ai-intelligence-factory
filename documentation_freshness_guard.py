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
RUN217_PATH = "docs/reference/RUN217_ZERO_API_MONETIZATION_READINESS.md"
RUN218_PATH = "docs/reference/RUN218_MEMBER_UX_RECONCILIATION.md"
RUN220_PATH = "docs/reference/RUN220_MEMBER_DB_CANONICAL_CUTOVER.md"

CANONICAL_MEMBER_HOME_ID = "3c5479ff-dca9-8103-bff0-f2d5f408d35f"
CANONICAL_MEMBER_HOME_TITLE = "AI Decision Intelligence｜会員ホーム"
SUPERSEDED_RUN217_HOME_ID = "3d0479ff-dca9-819e-9da0-c951225de6b3"
CURRENT_MEMBER_DB_ID = "b2787ee0-5b58-4ca7-b4eb-774f60237f1f"
CURRENT_MEMBER_DATA_SOURCE_ID = "7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404"
PRE_RUN220_MEMBER_DB_ID = "d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1"
PRE_RUN220_MEMBER_DATA_SOURCE_ID = "d1461b6f-0940-4bf9-803a-6686a37c4ba2"
LEGACY_MEMBER_DATA_SOURCE_ID = "ec2ac2b3-89b6-4242-89b9-e94060826fca"

FLASH_BUDGET_VARS = (
    "GEMINI_36_FLASH_DAILY_BUDGET",
    "GEMINI_37_FLASH_DAILY_BUDGET",
    "GEMINI_35_FLASH_DAILY_BUDGET",
)


def _read(root: Path, path: str) -> str:
    return (root / path).read_text(encoding="utf-8")


def active_runtime_modules(production_source: str) -> list[str]:
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
            errors.append(f"Canonical specification is stale: active runtime layer {marker} is undocumented")
    return errors


def baseline_errors(spec_text: str, readme_text: str) -> list[str]:
    errors: list[str] = []
    for marker in (
        "Run209", "Run210", "Run211", "Run218", "Run219", "Run220",
        "Daily workflowはPAUSED", "Documentation Freshness Guard",
    ):
        if marker not in spec_text:
            errors.append(f"Canonical specification missing current marker: {marker}")

    for marker in (
        "Run209", "Run210", "Run211", "Run218", "Run219", "Run220",
        "**Daily:** PAUSED", "Documentation Freshness Guard",
    ):
        if marker not in readme_text:
            errors.append(f"README missing current marker: {marker}")
    return errors


def quota_contract_errors(one_shot_text: str, daily_text: str, pending_retry_text: str, quota_text: str, spec_text: str) -> list[str]:
    errors: list[str] = []
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
    if "[PAUSED]" not in daily_text or "if: ${{ false }}" not in daily_text:
        errors.append("Daily workflow is no longer hard PAUSED; canonical docs must be reviewed")

    budget_match = re.search(r"FAST_LANE_PENDING_RETRY_REQUEST_BUDGET\s*=\s*(\d+)", pending_retry_text)
    cooldown_match = re.search(r"FAST_LANE_503_COOLDOWN_THRESHOLD\s*=\s*(\d+)", pending_retry_text)
    if not budget_match:
        errors.append("Pending Retry fast-lane request budget constant is missing")
    elif budget_match.group(1) != "3":
        errors.append("Pending Retry fast-lane request budget changed from 3; update canonical docs and guard deliberately")
    if not cooldown_match:
        errors.append("Pending Retry fast-lane 503 cooldown constant is missing")
    elif cooldown_match.group(1) != "1":
        errors.append("Pending Retry fast-lane 503 cooldown changed from 1; update canonical docs and guard deliberately")

    for marker in ("最大3 requests", "1回目のHTTP 503", "Reader Value repair"):
        if marker not in quota_text and marker not in spec_text:
            errors.append(f"Pending Retry canonical contract missing marker: {marker}")
    if "`daily.yml`では`GEMINI_PENDING_RETRY_REQUEST_BUDGET=2`" in quota_text:
        errors.append("Gemini quota specification still contains obsolete active-Daily Pending Retry wording")
    return errors


def _workflow_run_block(text: str) -> str:
    if "workflow_run:" not in text:
        return ""
    tail = text.split("workflow_run:", 1)[1]
    return tail.split("types: [completed]", 1)[0]


def member_product_sync_errors(inventory_text: str, subscriber_brief_text: str, member_presentation_text: str, spec_text: str, readme_text: str) -> list[str]:
    errors: list[str] = []
    if "run-name: Subscriber Inventory Bootstrap [${{ inputs.mode }}]" not in inventory_text:
        errors.append("Inventory workflow must expose plan/apply in run-name for safe downstream filtering")

    subscriber_block = _workflow_run_block(subscriber_brief_text)
    for upstream in ("Daily Intelligence & Content Pipeline", "Daily Intelligence & Content Pipeline [ONE-SHOT]", "Subscriber Inventory Bootstrap"):
        if upstream not in subscriber_block:
            errors.append(f"Subscriber Decision Brief missing upstream workflow_run source: {upstream}")
    if "github.event.workflow_run.name != 'Subscriber Inventory Bootstrap'" not in subscriber_brief_text:
        errors.append("Subscriber Decision Brief no longer distinguishes Inventory Bootstrap from other upstream runs")
    if "contains(github.event.workflow_run.display_title, '[apply]')" not in subscriber_brief_text:
        errors.append("Inventory plan could fan out into writes; apply-only downstream filter is missing")

    presentation_block = _workflow_run_block(member_presentation_text)
    if "Subscriber Decision Brief Sync" not in presentation_block:
        errors.append("Member Presentation must run after Subscriber Decision Brief Sync")
    for forbidden in ("Daily Intelligence & Content Pipeline", "Subscriber Inventory Bootstrap"):
        if forbidden in presentation_block:
            errors.append(f"Member Presentation is racing its source again; direct workflow_run trigger found: {forbidden}")

    if "group: member-derived-notion-writes" not in subscriber_brief_text or "group: member-derived-notion-writes" not in member_presentation_text:
        errors.append("Derived member Notion writers must share the member-derived-notion-writes lock")
    if "GEMINI_API_KEY" in subscriber_brief_text or "GEMINI_API_KEY" in member_presentation_text:
        errors.append("Derived member sync workflows must remain zero-Gemini")

    for marker in ("Run211", "Subscriber Decision Brief Sync", "Member Presentation Sync", "Inventory plan"):
        if marker not in spec_text:
            errors.append(f"Canonical specification missing member sync marker: {marker}")
    for marker in ("Run211", "Subscriber Decision Brief Sync", "Member Presentation Sync"):
        if marker not in readme_text:
            errors.append(f"README missing member sync marker: {marker}")
    return errors


def member_navigation_ux_errors(spec_text: str, readme_text: str, run217_text: str, run218_text: str, run220_text: str) -> list[str]:
    """Protect current home, PC-first IA, human DB destination and legacy quarantine."""
    errors: list[str] = []

    current_docs = (("spec", spec_text), ("README", readme_text), ("Run218", run218_text), ("Run220", run220_text))
    for marker in (CANONICAL_MEMBER_HOME_ID, CANONICAL_MEMBER_HOME_TITLE, CURRENT_MEMBER_DB_ID, CURRENT_MEMBER_DATA_SOURCE_ID):
        for name, text in current_docs:
            if marker not in text:
                errors.append(f"{name} missing current member-navigation marker: {marker}")

    if "Paid Member Navigation/UI Baseline: **Run218" not in spec_text:
        errors.append("Canonical specification no longer labels Run218 as the Navigation/UI baseline")
    if "paid member navigation/UI baseline:** Run218" not in readme_text:
        errors.append("README no longer labels Run218 as the Navigation/UI baseline")
    if "Paid Member Database Destination Baseline: **Run220" not in spec_text:
        errors.append("Canonical specification no longer labels Run220 as the DB destination baseline")
    if "paid member DB destination baseline:** Run220" not in readme_text:
        errors.append("README no longer labels Run220 as the DB destination baseline")

    forbidden_current_phrase = "正規会員入口は`AI Intelligence｜会員ホーム`"
    if forbidden_current_phrase in spec_text or forbidden_current_phrase in run218_text:
        errors.append("Superseded Run217 home was promoted back to current canonical navigation")

    if SUPERSEDED_RUN217_HOME_ID not in run217_text or SUPERSEDED_RUN217_HOME_ID not in run218_text:
        errors.append("Run217 superseded home ID is no longer documented for regression safety")
    if "superseded by Run218" not in run217_text:
        errors.append("Run217 history no longer states that its member-home navigation was superseded")
    if "【旧・統合済み】AI Intelligence｜会員ホーム" not in run217_text:
        errors.append("Run217 superseded home is not visibly quarantined in operator history")

    for marker in ("PC-first", "live Top3"):
        if marker not in spec_text or marker not in readme_text:
            errors.append(f"PC-first member UX contract missing from canonical docs: {marker}")
    for marker in ("PC is the primary member experience", "Mobile/simple views are secondary fallback surfaces only", "注目順位 <= 3", "presentation-only fallback", "does not modify the monthly checkbox", "blank table"):
        if marker not in run218_text:
            errors.append(f"Run218 operator contract missing UX safety marker: {marker}")

    for old_marker in (PRE_RUN220_MEMBER_DB_ID, PRE_RUN220_MEMBER_DATA_SOURCE_ID, LEGACY_MEMBER_DATA_SOURCE_ID):
        if old_marker not in spec_text or old_marker not in readme_text or old_marker not in run220_text:
            errors.append(f"Legacy member destination is no longer explicitly documented: {old_marker}")
    if "旧版・使用禁止" not in spec_text or "旧版・使用禁止" not in readme_text or "旧版・使用禁止" not in run220_text:
        errors.append("Legacy member database lost its visible do-not-use contract")

    if "今月の重要変化" not in spec_text or "今月の重要変化" not in run218_text:
        errors.append("Important-change source semantics are no longer documented")
    if "評価の変化 >= 20" not in spec_text or "<= -20" not in spec_text:
        errors.append("Canonical spec lost the Run218 recent-large-change presentation fallback")
    if "評価の変化 >= 20" not in run218_text or "評価の変化 <= -20" not in run218_text:
        errors.append("Run218 operator contract lost the authoritative large-change thresholds")

    if "Gemini/model requests used for this run: **0**" not in run218_text:
        errors.append("Run218 no longer explicitly records zero model requests")
    if "GEMINI_API_KEY" in run218_text or "generate_content(" in run218_text:
        errors.append("Run218 navigation/UI contract unexpectedly contains a model invocation path")

    for marker in ("MEMBER_PRESENTATION_ALLOW_CREATE=false", "fail closed", CURRENT_MEMBER_DB_ID, CURRENT_MEMBER_DATA_SOURCE_ID):
        if marker not in run220_text:
            errors.append(f"Run220 operator contract missing canonical DB safety marker: {marker}")
    if "MEMBER_PRESENTATION_ALLOW_CREATE: 'false'" not in spec_text:
        errors.append("Canonical spec lost the Run220 no-auto-create Production contract")
    return errors


def member_destination_workflow_errors(member_presentation_text: str, spec_text: str, readme_text: str, run220_text: str) -> list[str]:
    """Protect one exact production destination; never silently create/select another DB."""
    errors: list[str] = []
    for marker in (CURRENT_MEMBER_DB_ID, CURRENT_MEMBER_DATA_SOURCE_ID):
        if marker not in member_presentation_text:
            errors.append(f"Member Presentation workflow missing canonical destination: {marker}")
    if "MEMBER_PRESENTATION_ALLOW_CREATE: 'false'" not in member_presentation_text:
        errors.append("Member Presentation workflow must keep automatic DB creation disabled")
    if "Resolve canonical member DB" not in member_presentation_text:
        errors.append("Member Presentation workflow no longer declares canonical DB resolution")
    for marker in ("Run220", CURRENT_MEMBER_DB_ID, CURRENT_MEMBER_DATA_SOURCE_ID):
        if marker not in spec_text or marker not in readme_text or marker not in run220_text:
            errors.append(f"Run220 current destination contract missing marker: {marker}")
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
    run217_text = _read(root_path, RUN217_PATH)
    run218_text = _read(root_path, RUN218_PATH)
    run220_text = _read(root_path, RUN220_PATH)

    errors: list[str] = []
    errors.extend(runtime_layer_errors(production_source, spec_text))
    errors.extend(baseline_errors(spec_text, readme_text))
    errors.extend(quota_contract_errors(one_shot_text, daily_text, pending_retry_text, quota_text, spec_text))
    errors.extend(member_product_sync_errors(inventory_text, subscriber_brief_text, member_presentation_text, spec_text, readme_text))
    errors.extend(member_navigation_ux_errors(spec_text, readme_text, run217_text, run218_text, run220_text))
    errors.extend(member_destination_workflow_errors(member_presentation_text, spec_text, readme_text, run220_text))
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
