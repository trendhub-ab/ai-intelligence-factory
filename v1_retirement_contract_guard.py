"""AIIF V1 retirement guard: standard-library, zero-provider verification."""
from __future__ import annotations
import ast
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
RETAINED_CI = {
    "integration-reconciliation-ci.yml": "zero-api-regression",
    "p0b-offline-verification.yml": "offline-verification",
    "repository-falsification.yml": "falsify-all-tracked-surfaces",
    "notion-access-policy-guard.yml": "notion-access-policy",
}
JOB = re.compile(r"^  ([A-Za-z][A-Za-z0-9_-]*):\s*(?:#.*)?$")
JOBS = re.compile(r"^jobs:\s*(?:#.*)?$")
FALSE_GUARD = "    if: ${{ false }} # V1 retired 2026-11-06"
# Narrow owner-authorized note-DRAFT rescue exception, NOT V1 Daily revival.
V04_NOTE_BRIDGE = "v04-single-note-draft-bridge.yml"
V04_NOTE_BRIDGE_JOBS = [
    "verify-private-input", "start-note-vm",
    "create-exact-draft", "inspect-draft-state", "stop-note-vm",
]
# Independent inspect-only ChatOps ingress; never a V1 reactivation.
V04_CHATOPS_BRIDGE = "v04-owner-chatops-inspect.yml"



def _jobs(text: str, label: str) -> list[tuple[str, list[str]]]:
    lines = text.splitlines()
    markers = [i for i, line in enumerate(lines) if JOBS.match(line)]
    assert len(markers) == 1, f"{label}: EXACTLY_ONE_JOBS_BLOCK_REQUIRED"
    jobs = []
    for line in lines[markers[0]+1:]:
        if line and not line.startswith((" ", "#")):
            break
        job = JOB.match(line)
        if job:
            jobs.append((job.group(1), []))
        elif jobs:
            jobs[-1][1].append(line)
    assert jobs, f"{label}: NO_JOBS"
    return jobs


def audit_v1_retirement(root: Path = ROOT) -> dict:
    files = sorted((p for p in (root / ".github/workflows").iterdir()
                    if p.is_file() and p.suffix in {".yml", ".yaml"}),
                   key=lambda p: p.name)
    assert len(files) == 87, f"WORKFLOW_COUNT_DRIFT: {len(files)}"
    assert set(RETAINED_CI) <= {f.name for f in files}, "OFFLINE_CI_MISSING"
    disabled_count = 0
    job_count = 0
    one_draft_bridge_count = 0
    inspect_chatops_count = 0
    for path in files:
        src = path.read_text(encoding="utf-8")
        jobs = _jobs(src, path.name)
        if path.name == V04_NOTE_BRIDGE:
            # A fresh workflow is allowed only for a single manually confirmed
            # owner-authenticated PRIVATE note DRAFT. No model or public release.
            assert [name for name, _ in jobs] == V04_NOTE_BRIDGE_JOBS, (
                "V04_NOTE_BRIDGE_JOB_DRIFT"
            )
            assert src.count("workflow_dispatch:") == 1, "V04_NOTE_BRIDGE_DISPATCH_INVALID"
            for forbidden in (
                "schedule:", "issue_comment:", "issues:", "pull_request:",
                "AIIF_NEXT_GEMINI_API_KEY", "production_pipeline.py",
                "publish_note", "note-publication", "secrets.NOTION_API_KEY",
            ):
                assert forbidden not in src, (
                    f"V04_NOTE_BRIDGE_FORBIDDEN: {forbidden}"
                )
            for required in (
                "github.actor == 'trendhub-ab'",
                "github.ref == 'refs/heads/main'",
                "github.run_attempt == 1",
                "CREATE_V04_SINGLE_PRIVATE_NOTE_DRAFT",
                "note-draft-create-v2",
                "run_v04_note_single_draft_bridge.py",
                "inputs.operation == 'recover'",
                "options: [create, inspect, recover, recover-final]",
                "inputs.operation == 'recover-final'",
                "OWNER_CONFIRMS_AGENT_SKILLS_204_ABSENT_FINAL_ONCE",
                "tests.test_run_v04_note_body_locator",
                "tests.test_run_v04_historical_edit_proof",
                "test \"$INPUT_ISSUE\" = \"205\"",
                "test \"$INPUT_SHA\" = \"d65a7e9a798f86a31980686483870a1bd6a651ac8f58b12a4fe9ea62427a6650\"",
                "OWNER_CONFIRMS_AGENT_SKILLS_204_ABSENT_RETRY_ONCE",
                "GCP_WORKLOAD_IDENTITY_PROVIDER",
                "NOTE_STORAGE_STATE_B64",
                "stop-note-vm:",
                "persist-credentials: false",
            ):
                assert required in src, (
                    f"V04_NOTE_BRIDGE_SAFETY_CONTRACT_MISSING: {required}"
                )
            assert (root / "tests/test_run_v04_note_single_draft_bridge.py").is_file(), (
                "V04_NOTE_BRIDGE_TESTS_MISSING"
            )
            for dependency in (
                "run_v04_note_body_locator.py",
                "tests/test_run_v04_note_body_locator.py",
                "run_v04_historical_edit_proof.py",
                "tests/test_run_v04_historical_edit_proof.py",
            ):
                assert (root / dependency).is_file(), (
                    f"V04_BODY_LOCATOR_DEPENDENCY_MISSING: {dependency}"
                )
            one_draft_bridge_count += 1
            continue
        if path.name == V04_CHATOPS_BRIDGE:
            assert [name for name, _ in jobs] == ["authorize-and-dispatch"], (
                "V04_CHATOPS_JOB_DRIFT"
            )
            assert src.count("issue_comment:") == 1, "V04_CHATOPS_TRIGGER_INVALID"
            for forbidden in (
                "schedule:", "push:", "workflow_dispatch:", "pull_request:",
                "daily-one-shot.yml/dispatches",
                "note-create-draft.yml/dispatches",
                "AIIF_NEXT_GEMINI_API_KEY", "production_pipeline.py",
                "publish_note", "note-publication", "secrets.NOTION_API_KEY",
            ):
                assert forbidden not in src, f"V04_CHATOPS_FORBIDDEN: {forbidden}"
            for required in (
                "github.repository == 'trendhub-ab/ai-intelligence-factory'",
                "github.actor == 'trendhub-ab'",
                "github.ref == 'refs/heads/main'",
                "github.event.issue.number == 71",
                "github.event.comment.user.login == 'trendhub-ab'",
                "github.event.comment.body == '/aiif v04 inspect 204'",
                "github.event.comment.body == '/aiif v04 recover 204'",
                "github.event.comment.body == '/aiif v04 recover-final 204'",
                "github.event.comment.body == '/aiif v04 create 205'",
                "github.run_attempt == 1",
                "issues: write", "actions: write",
                "run_v04_chatops_control.py",
                "tests.test_run_v04_chatops_control",
                "content=eyes",
                "GH_TOKEN: ${{ secrets.GH_PAT }}",
                "v04-single-note-draft-bridge.yml/dispatches",
                '"operation":"inspect"',
                '"operation":"recover"',
                '"operation":"recover-final"',
                '"operation":"create"',
                '"source_issue_number":"205"',
                "d65a7e9a798f86a31980686483870a1bd6a651ac8f58b12a4fe9ea62427a6650",
                "create-fresh)",
                '"recovery_approval":"OWNER_CONFIRMS_AGENT_SKILLS_204_ABSENT_FINAL_ONCE"',
                '"recovery_approval":"OWNER_CONFIRMS_AGENT_SKILLS_204_ABSENT_RETRY_ONCE"',
                '"source_issue_number":"204"',
                "1f39788f6c1c9dc9e9ca93af5c260e0c396374f76b5dc33c3ece0def3cffb690",
            ):
                assert required in src, (
                    f"V04_CHATOPS_SAFETY_CONTRACT_MISSING: {required}"
                )
            assert src.count('"operation":"create"') == 1, (
                "V04_CHATOPS_CREATE_MUST_BE_EXACTLY_ONE_FRESH")
            for dependency in (
                "run_v04_chatops_control.py",
                "tests/test_run_v04_chatops_control.py",
            ):
                assert (root / dependency).is_file(), (
                    f"V04_CHATOPS_DEPENDENCY_MISSING: {dependency}"
                )
            inspect_chatops_count += 1
            continue
        if path.name in RETAINED_CI:
            assert [name for name, _ in jobs] == [RETAINED_CI[path.name]], (
                f"UNEXPECTED_CI_JOB: {path.name}"
            )
            assert all(token not in src for token in (
                "workflow_dispatch:", "issue_comment:", "schedule:", "secrets.", "vars."
            )), f"CI_HAS_LIVE_TRIGGER_OR_CREDENTIALS: {path.name}"
            assert src.count("python v1_retirement_contract_guard.py") == 1, (
                f"CI_DOES_NOT_EXECUTE_RETIREMENT_GUARD: {path.name}"
            )
            assert "uses: actions/checkout@" in src, f"CI_CHECKOUT_MISSING: {path.name}"
            continue
        for name, lines in jobs:
            statements = [line for line in lines if line.strip()
                          and not line.lstrip().startswith("#")]
            assert statements and statements[0] == FALSE_GUARD, (
                f"V1_OPERATIONAL_JOB_CAN_RUN: {path.name}:{name}"
            )
            assert sum(line.startswith("    if:") for line in lines) == 1, (
                f"V1_DUPLICATE_JOB_IF: {path.name}:{name}"
            )
            job_count += 1
        disabled_count += 1
    assert one_draft_bridge_count == 1, "V04_NOTE_BRIDGE_MISSING_OR_DUPLICATED"
    assert inspect_chatops_count == 1, "V04_CHATOPS_BRIDGE_MISSING_OR_DUPLICATED"
    assert disabled_count == 81, f"UNEXPECTED_OPERATIONAL_WORKFLOWS: {disabled_count}"
    assert job_count >= 81, f"OPERATIONAL_JOBS_NOT_DISABLED: {job_count}"

    for name in ("production_pipeline.py", "pipeline.py"):
        source = (root / name).read_text(encoding="utf-8")
        module = ast.parse(source)
        mains = [node for node in module.body if isinstance(node, ast.FunctionDef)
                 and node.name == "main"]
        assert len(mains) == 1, f"MAIN_NOT_UNIQUE: {name}"
        first = mains[0].body[0]
        assert isinstance(first, ast.Raise), f"MAIN_NOT_FAIL_CLOSED: {name}"
        exc = first.exc
        assert isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name), (
            f"MAIN_NOT_EXPLICIT_RAISE: {name}"
        )
        assert exc.func.id == "RuntimeError", f"MAIN_NOT_RUNTIME_ERROR: {name}"
        assert exc.args and isinstance(exc.args[0], ast.Constant) and (
            "AIIF_V1_RETIRED" in str(exc.args[0].value)
        ), f"MAIN_RETIREMENT_TOKEN_MISSING: {name}"
    assert (root / "V1_RETIRED.md").is_file(), "RETIREMENT_RECORD_MISSING"
    return {
        "retirement": "PASS",
        "operational_workflows_disabled": disabled_count,
        "operational_jobs_disabled": job_count,
        "retained_offline_ci": len(RETAINED_CI),
        "owner_manual_private_note_draft_exception": one_draft_bridge_count,
        "owner_v04_read_only_chatops_exception": inspect_chatops_count,
        "entrypoints_blocked": 2,
        "model_calls": 0,
        "publication_mutations": 0,
    }


def main() -> int:
    try:
        result = audit_v1_retirement()
    except (AssertionError, OSError, SyntaxError) as exc:
        print(f"V1_RETIREMENT_GUARD=FAIL: {exc}", file=sys.stderr)
        return 1
    print("V1_RETIREMENT_GUARD=PASS")
    for key, value in result.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
