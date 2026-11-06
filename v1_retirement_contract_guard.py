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
    assert len(files) == 85, f"WORKFLOW_COUNT_DRIFT: {len(files)}"
    assert set(RETAINED_CI) <= {f.name for f in files}, "OFFLINE_CI_MISSING"
    disabled_count = 0
    job_count = 0
    for path in files:
        src = path.read_text(encoding="utf-8")
        jobs = _jobs(src, path.name)
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
