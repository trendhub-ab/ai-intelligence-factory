#!/usr/bin/env python3
"""Repository-wide fail-closed guard for cross-path production regressions.

This is intentionally zero-network and zero-provider. It scans the checked-out repository,
not a hand-picked subset, so a future file/workflow can fail CI as soon as it reintroduces a
bypass that ordinary unit tests may never import.

The guard distinguishes executable/live surfaces from docs/archive/history. Historical text
may describe old Runs; it is not a production bug unless a live workflow or root entrypoint can
execute it.
"""
from __future__ import annotations

import re
from pathlib import Path

import publication_contract

ROOT = Path(__file__).resolve().parent
WORKFLOWS = ROOT / ".github" / "workflows"
SELF = Path(__file__).resolve()

DERIVED_DAILY_WORKFLOWS = {
    "note-ready-sync.yml",
    "member-presentation-sync.yml",
    "subscriber-decision-brief.yml",
}

OLD_WORKFLOW_RUN_PATTERNS = (
    re.compile(r"^\s*run:\s*python\s+reader_value_review_bridge\.py\s*$", re.MULTILINE),
    re.compile(r"^\s*run:\s*xvfb-run\s+-a\s+python\s+run190_note_persistent_cloud\.py\s*$", re.MULTILINE),
    re.compile(r"^\s*run:\s*python\s+run185_note_ready_legacy_skip\.py\s*$", re.MULTILINE),
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
        if path.resolve() == SELF:
            continue
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
        for pattern in OLD_WORKFLOW_RUN_PATTERNS:
            if pattern.search(text):
                failures.append(f"old_workflow_entrypoint:{name}:{pattern.pattern}")

        # pipeline.py is allowed only for the intentionally isolated zero-Gemini Public DB mirror.
        if re.search(r"^\s*run:\s*\|?[\s\S]*?\bpython\s+pipeline\.py\b", text, re.MULTILINE):
            if name != "public-db-sync.yml" or "PUBLIC_DB_SYNC_MODE: \"true\"" not in text:
                failures.append(f"direct_pipeline_bypass:{name}")

        # Count only an active YAML env key, not comments saying "NO GEMINI_API_KEY".
        has_gemini_env = bool(re.search(r"^\s+GEMINI_API_KEY:\s*", text, re.MULTILINE))
        if has_gemini_env and "group: ai-intelligence-gemini-budget" not in text:
            failures.append(f"gemini_without_shared_budget_lock:{name}")

        # A derived view listening to Daily must also follow the operational ONE-SHOT.
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

    # Member Presentation and Decision Brief share the same Decision Intelligence integration
    # and write the same member product family. A ONE-SHOT/push fan-out must never run both
    # writers concurrently; Run195 live validation reproduced 76 Notion 429 failures without it.
    shared_member_notion_group = "group: member-derived-notion-writes"
    for name in ("member-presentation-sync.yml", "subscriber-decision-brief.yml"):
        text = _workflow_text(name)
        if shared_member_notion_group not in text:
            failures.append(f"member_notion_writer_not_shared_serialized:{name}")
        if "NOTION_DECISION_INTELLIGENCE_API_KEY:" not in text:
            failures.append(f"member_notion_writer_missing_expected_integration:{name}")

    subscriber_workflow = _workflow_text("subscriber-decision-brief.yml")
    for required in (
        'timeout-minutes: 30',
        'SUBSCRIBER_DECISION_BRIEF_PACING_SECONDS: "0.40"',
        'SUBSCRIBER_DECISION_BRIEF_REQUEST_MAX_ATTEMPTS: "8"',
        'SUBSCRIBER_DECISION_BRIEF_RETRY_AFTER_MAX_SECONDS: "120"',
    ):
        if required not in subscriber_workflow:
            failures.append(f"subscriber_brief_rate_limit_contract_missing:{required}")

    subscriber_source = (ROOT / "subscriber_decision_brief.py").read_text(encoding="utf-8")
    for required in ("def _response_retry_after(", "def _request(", "additional_data", "Retry-After"):
        if required not in subscriber_source:
            failures.append(f"subscriber_brief_retry_transport_missing:{required}")
    # All live GET/POST/PATCH/DELETE calls must pass through _request so retry/pacing policy
    # cannot be bypassed by a future helper added elsewhere in this module.
    if re.search(r"requests\.(?:get|post|patch|delete)\s*\(", subscriber_source):
        failures.append("subscriber_brief_direct_notion_transport_bypass")

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
    if OLD_WORKFLOW_RUN_PATTERNS[0].search(regression):
        failures.append("real_regression_uses_historical_partial_stack")

    # 6. Historical reader bridge remains importable, but standalone execution delegates to
    # the sole current production entrypoint. Avoid substring confusion with production_pipeline.
    bridge = (ROOT / "reader_value_review_bridge.py").read_text(encoding="utf-8")
    main_tail = bridge[bridge.rfind("def main()"):] if "def main()" in bridge else ""
    direct_pipeline_call = re.compile(r"(?<!production_)\bpipeline\.main\(\)")
    if "production_pipeline.main()" not in main_tail or direct_pipeline_call.search(main_tail):
        failures.append("reader_bridge_standalone_bypasses_current_stack")

    # 7. All root Python executables are scanned for a direct pipeline.main() bypass.
    for path, text in all_text:
        if path.resolve() == SELF or path.parent != ROOT or path.suffix != ".py":
            continue
        if path.name == "production_pipeline.py":
            continue
        if direct_pipeline_call.search(text):
            failures.append(f"root_python_direct_pipeline_main:{path.name}")

    # 8. Publication policy is auto-derived from real files; manifest must include every
    # installed Run layer named by production_pipeline.py plus reader/eyecatch cores.
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
    fixed_symbol = "CURRENT" + "_READY_CAPTION"
    for path, text in all_text:
        if path.resolve() == SELF:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix == ".py" and fixed_symbol in text:
            failures.append(f"fixed_publication_caption_reintroduced:{rel}")

    # Publication consumers outside the contract module must validate body + caption together.
    for path, text in all_text:
        if path.resolve() == SELF or path.parent != ROOT or path.suffix != ".py":
            continue
        if path.name == "publication_contract.py":
            continue
        if "is_current_ready_caption(" in text:
            failures.append(f"caption_only_publication_validation:{path.name}")

    # 10. No private/undocumented note API transport in executable code or workflows.
    for path, text in all_text:
        rel = path.relative_to(ROOT).as_posix()
        if path.resolve() == SELF or not (path.suffix in {".py", ".yml", ".yaml", ".sh"}):
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