#!/usr/bin/env python3
"""Repository-wide fail-closed guard for cross-path production regressions.

This is intentionally zero-network and zero-provider.  It scans the checked-out repository,
not a hand-picked subset, so a future file/workflow can fail CI as soon as it reintroduces a
bypass that ordinary unit tests may never import.

The guard distinguishes executable/live surfaces from docs/archive/history.  Historical text
may describe old Runs; it is not a production bug unless a live workflow or root entrypoint can
execute it.
"""
from __future__ import annotations

import re
from pathlib import Path

import publication_contract

ROOT = Path(__file__).resolve().parent
WORKFLOWS = ROOT / ".github" / "workflows"

DERIVED_DAILY_WORKFLOWS = {
    "note-ready-sync.yml",
    "member-presentation-sync.yml",
    "subscriber-decision-brief.yml",
}

OLD_WORKFLOW_ENTRYPOINTS = (
    "run: python reader_value_review_bridge.py",
    "xvfb-run -a python run190_note_persistent_cloud.py",
    "run: python run185_note_ready_legacy_skip.py",
)

HIGH_CONFIDENCE_SECRET_PATTERNS = (
    ("GitHub classic token", re.compile(r"\bghp_[A-Za-z0-9]{30,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)

TEXT_SUFFIXES = {
    ".py", ".yml", ".yaml", ".md", ".txt", ".json", ".toml", ".ini", ".cfg",
    ".sh", ".html", ".css", ".js", ".ts", ".csv",
}

EXCLUDED_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__"}


def _text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"Dockerfile", "Procfile"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        yield path, text


def _workflow_text(name: str) -> str:
    path = WORKFLOWS / name
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _has_trigger(text: str, trigger: str) -> bool:
    return bool(re.search(rf"^\s+{re.escape(trigger)}:\s*$", text, re.MULTILINE))


def audit() -> list[str]:
    failures: list[str] = []
    all_text = list(_text_files())

    # 1. High-confidence credential leakage anywhere in the tracked text surface.
    for path, text in all_text:
        rel = path.relative_to(ROOT).as_posix()
        for label, pattern in HIGH_CONFIDENCE_SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(f"secret_leak:{rel}:{label}")

    # 2. Every live Workflow is checked, not only known production files.
    workflow_items = sorted(
        (path, text) for path, text in all_text if path.parent == WORKFLOWS and path.suffix in {".yml", ".yaml"}
    )
    for path, text in workflow_items:
        name = path.name
        for old in OLD_WORKFLOW_ENTRYPOINTS:
            if old in text:
                failures.append(f"old_workflow_entrypoint:{name}:{old}")

        # pipeline.py is allowed only for the intentionally isolated zero-Gemini Public DB mirror.
        if re.search(r"\bpython\s+pipeline\.py\b", text):
            if name != "public-db-sync.yml" or "PUBLIC_DB_SYNC_MODE: \"true\"" not in text:
                failures.append(f"direct_pipeline_bypass:{name}")

        # Any workflow that can spend Gemini must share the persistent budget lock.
        if "GEMINI_API_KEY" in text and "group: ai-intelligence-gemini-budget" not in text:
            failures.append(f"gemini_without_shared_budget_lock:{name}")

        # A derived view listening to normal Daily must also follow the operational ONE-SHOT.
        if "Daily Intelligence & Content Pipeline" in text and "workflow_run:" in text:
            if "Daily Intelligence & Content Pipeline [ONE-SHOT]" not in text:
                failures.append(f"daily_listener_missing_one_shot:{name}")

    # 3. Explicit contracts for the three production-derived Notion views.
    for name in DERIVED_DAILY_WORKFLOWS:
        text = _workflow_text(name)
        if not text:
            failures.append(f"missing_derived_workflow:{name}")
            continue
        if "Daily Intelligence & Content Pipeline [ONE-SHOT]" not in text:
            failures.append(f"derived_workflow_missing_one_shot:{name}")
        if "github.event.workflow_run.head_branch == 'main'" not in text:
            failures.append(f"derived_workflow_missing_main_guard:{name}")
        if "cancel-in-progress: false" not in text:
            failures.append(f"derived_workflow_not_serialized_safely:{name}")

    note_sync = _workflow_text("note-ready-sync.yml")
    if "group: note-ready-article-sync" not in note_sync:
        failures.append("note_ready_sync_missing_single_writer_lock")

    # 4. Scheduled Daily remains impossible until explicitly redesigned/resumed.
    daily = _workflow_text("daily.yml")
    if not daily:
        failures.append("daily_workflow_missing")
    else:
        if _has_trigger(daily, "schedule"):
            failures.append("paused_daily_has_schedule")
        if "if: ${{ false }}" not in daily:
            failures.append("paused_daily_not_hard_disabled")
        if "python production_pipeline.py" not in daily:
            failures.append("paused_daily_missing_current_entrypoint_contract")

    one_shot = _workflow_text("daily-one-shot.yml")
    if not one_shot:
        failures.append("one_shot_workflow_missing")
    else:
        if _has_trigger(one_shot, "push") or _has_trigger(one_shot, "schedule"):
            failures.append("one_shot_has_automatic_trigger")
        if "inputs.confirm == 'RUN_ONCE'" not in one_shot:
            failures.append("one_shot_missing_explicit_confirmation")
        if "python production_pipeline.py" not in one_shot:
            failures.append("one_shot_bypasses_current_production_entrypoint")

    # 5. Real Article Regression must exercise the same installed stack as production.
    regression = _workflow_text("regression-test.yml")
    if "REGEN_TEST_MODE: \"true\"" not in regression:
        failures.append("real_regression_missing_non_persist_mode")
    if "run: python production_pipeline.py" not in regression:
        failures.append("real_regression_not_using_current_production_stack")
    if "run: python reader_value_review_bridge.py" in regression:
        failures.append("real_regression_uses_historical_partial_stack")

    # 6. The historical reader bridge may remain importable, but standalone execution must
    # delegate to the sole current production entrypoint.
    bridge = (ROOT / "reader_value_review_bridge.py").read_text(encoding="utf-8")
    main_tail = bridge[bridge.rfind("def main()"):] if "def main()" in bridge else ""
    if "production_pipeline.main()" not in main_tail or "pipeline.main()" in main_tail:
        failures.append("reader_bridge_standalone_bypasses_current_stack")

    # 7. All root Python executables are scanned for a direct pipeline.main() bypass.
    # production_pipeline.py is the only allowed owner of that call.
    for path, text in all_text:
        if path.parent != ROOT or path.suffix != ".py":
            continue
        if path.name == "production_pipeline.py":
            continue
        if "pipeline.main()" in text:
            failures.append(f"root_python_direct_pipeline_main:{path.name}")

    # 8. Publication policy is auto-derived from real files; the manifest must include every
    # installed Run layer named by production_pipeline.py plus its reader bridge.
    try:
        publication_contract.policy_sha256()
    except Exception as exc:
        failures.append(f"publication_policy_unhashable:{exc}")
    production = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
    manifest = set(publication_contract.PUBLICATION_POLICY_FILES)
    installed_run_modules = set(
        re.findall(r"\b(run\d+_[A-Za-z0-9_]+)\.install\(pipeline_module\)", production)
    )
    for module in sorted(installed_run_modules):
        filename = module + ".py"
        if filename not in manifest:
            failures.append(f"publication_manifest_missing_installed_layer:{filename}")
    if "reader_value_review_bridge.py" not in manifest or "editorial_eyecatch.py" not in manifest:
        failures.append("publication_manifest_missing_reader_or_eyecatch_core")

    # 9. Removed fixed-caption API must not creep back into executable Python/tests.
    for path, text in all_text:
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix == ".py" and "CURRENT_READY_CAPTION" in text:
            failures.append(f"fixed_publication_caption_reintroduced:{rel}")

    # 10. No private/undocumented note API transport in executable code or workflows.
    for path, text in all_text:
        rel = path.relative_to(ROOT).as_posix()
        if not (path.suffix in {".py", ".yml", ".yaml", ".sh"}):
            continue
        if re.search(r"https?://(?:www\.)?note\.com/(?:api|api/|api/v\d)", text, re.I):
            failures.append(f"private_note_api_reference:{rel}")

    return list(dict.fromkeys(failures))


def main() -> None:
    failures = audit()
    if failures:
        print("REPOSITORY_FALSIFICATION_GUARD=FAIL")
        for item in failures:
            print("-", item)
        raise SystemExit(1)
    print("REPOSITORY_FALSIFICATION_GUARD=PASS")
    print(f"publication_policy_sha256={publication_contract.policy_sha256()}")


if __name__ == "__main__":
    main()
