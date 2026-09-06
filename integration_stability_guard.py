#!/usr/bin/env python3
"""Fail closed when Integration CI regains known nondeterministic failure modes."""
from __future__ import annotations

import re
from pathlib import Path


INTEGRATION_WORKFLOW = ".github/workflows/integration-reconciliation-ci.yml"
RUN130_TEST = "tests/test_run130_fresh_article_regression_reconciliation.py"
RUNTIME_MANIFEST_TEST = "tests/test_run231_pipeline_slim.py"
CI_COLLECTION_TEST = "tests/test_run233_ci_collection_integrity.py"
NETWORK_GUARD = "tests/conftest.py"
CONSTRAINTS = "requirements-ci-constraints.txt"

KNOWN_GREEN_PINS = {
    "google-genai": "1.75.0",
    "Pillow": "12.3.0",
    "requests": "2.34.2",
    "pypdf": "6.17.0",
    "pytest": "8.4.2",
}


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def workflow_errors(text: str) -> list[str]:
    errors: list[str] = []
    required = (
        "runs-on: ubuntu-24.04",
        "python-version: '3.11.16'",
        "GEMINI_PERSISTENT_DAILY_COUNTER: 'false'",
        "requirements-ci-constraints.txt",
        "python -m pip check",
        "python integration_stability_guard.py",
        "python -m pytest -q tests",
    )
    for marker in required:
        if marker not in text:
            errors.append(f"Integration workflow missing deterministic contract: {marker}")

    forbidden = (
        "pip install 'pytest>=8,<9'",
        "Run article quality reconciliation tests",
        "Run Run134 reconciliation tests",
        "Run adjacent product and context regressions",
    )
    for marker in forbidden:
        if marker in text:
            errors.append(f"Integration workflow reintroduced redundant/drifting contract: {marker}")

    if "pip install -r requirements.txt -c requirements-ci-constraints.txt" not in text:
        errors.append("Integration workflow must install production requirements through the CI constraint lock")
    if "pip install 'pytest==8.4.2' -c requirements-ci-constraints.txt" not in text:
        errors.append("Integration workflow must install the known-green pytest version through the CI constraint lock")
    return errors


def run130_errors(text: str) -> list[str]:
    errors: list[str] = []
    marker = 'os.environ.setdefault("GEMINI_PERSISTENT_DAILY_COUNTER", "false")'
    if marker not in text:
        errors.append("Run130 regression test does not disable the persistent remote Gemini counter")
    elif text.index(marker) > text.index("import pipeline"):
        errors.append("Run130 persistent counter disable must occur before importing pipeline")
    return errors


def runtime_manifest_test_errors(text: str) -> list[str]:
    errors: list[str] = []
    if re.search(r"EXPECTED_RUNTIME_LAYER_ORDER\s*=\s*\(", text):
        errors.append("Runtime layer order is duplicated in the test instead of using runtime_layers.RUNTIME_LAYER_ORDER")
    if "runtime_layers.RUNTIME_LAYER_ORDER" not in text:
        errors.append("Runtime manifest test no longer reads the canonical runtime_layers.RUNTIME_LAYER_ORDER")
    for marker in (
        "assertLess",
        '"run203_runtime_state_channel.install"',
        '"run194_publication_contract.install"',
    ):
        if marker not in text:
            errors.append(f"Runtime manifest semantic-order protection missing: {marker}")
    return errors


def ci_collection_test_errors(text: str) -> list[str]:
    errors: list[str] = []
    if "pip install 'pytest>=8,<9'" in text:
        errors.append("CI collection integrity test still requires the obsolete broad pytest range")
    if "requirements-ci-constraints.txt" not in text:
        errors.append("CI collection integrity test does not protect the deterministic CI constraint lock")
    return errors


def network_guard_errors(text: str) -> list[str]:
    errors: list[str] = []
    for marker in (
        "@pytest.fixture(autouse=True)",
        'monkeypatch.setattr(socket.socket, "connect", guarded_connect)',
        "Unexpected external network access during pytest",
    ):
        if marker not in text:
            errors.append(f"Pytest external-network fail-closed guard missing: {marker}")
    return errors


def constraints_errors(text: str) -> list[str]:
    errors: list[str] = []
    pins: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, version = line.split("==", 1)
        pins[name.strip()] = version.strip()
    for name, expected in KNOWN_GREEN_PINS.items():
        if pins.get(name) != expected:
            errors.append(f"CI lock drifted from known-green {name}=={expected}")
    return errors


def collect_errors(root: Path) -> list[str]:
    errors: list[str] = []
    checks = (
        (INTEGRATION_WORKFLOW, workflow_errors),
        (RUN130_TEST, run130_errors),
        (RUNTIME_MANIFEST_TEST, runtime_manifest_test_errors),
        (CI_COLLECTION_TEST, ci_collection_test_errors),
        (NETWORK_GUARD, network_guard_errors),
        (CONSTRAINTS, constraints_errors),
    )
    for relative, checker in checks:
        path = root / relative
        if not path.is_file():
            errors.append(f"Integration stability contract file missing: {relative}")
            continue
        errors.extend(checker(_read(root, relative)))
    return errors


def main() -> int:
    root = Path(__file__).resolve().parent
    errors = collect_errors(root)
    if errors:
        print("INTEGRATION_STABILITY_GUARD=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("INTEGRATION_STABILITY_GUARD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
