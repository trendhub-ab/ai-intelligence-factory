#!/usr/bin/env python3
"""Fail closed when deterministic CI regains known nondeterministic failure modes."""
from __future__ import annotations

import ast
import re
from pathlib import Path


INTEGRATION_WORKFLOW = ".github/workflows/integration-reconciliation-ci.yml"
STANDALONE_REGRESSION_WORKFLOW = ".github/workflows/regression.yml"
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
        "- '.github/workflows/regression.yml'",
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


def standalone_regression_errors(text: str) -> list[str]:
    """Keep the push/dispatch Synthetic workflow on the same hermetic test contract."""
    errors: list[str] = []
    required = (
        "runs-on: ubuntu-24.04",
        "python-version: '3.11.16'",
        "GEMINI_PERSISTENT_DAILY_COUNTER: 'false'",
        "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
        "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1",
        "pip install -r requirements.txt -c requirements-ci-constraints.txt",
        "pip install 'pytest==8.4.2' -c requirements-ci-constraints.txt",
        "python -m pip check",
        "python integration_stability_guard.py",
        "python -m pytest -q tests",
        "python regression_suite.py --self-test",
        "python regression_suite.py --bootstrap --${{ github.event.inputs.suite || 'smoke' }}",
    )
    for marker in required:
        if marker not in text:
            errors.append(f"Standalone Synthetic workflow missing hermetic contract: {marker}")

    forbidden = (
        "python -m unittest discover -s tests -v",
        "uses: actions/checkout@v6",
        "uses: actions/setup-python@v6",
        "pip install 'pytest>=8,<9'",
    )
    for marker in forbidden:
        if marker in text:
            errors.append(f"Standalone Synthetic workflow reintroduced nondeterministic contract: {marker}")
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


def _string_membership_assertions(text: str) -> tuple[set[str], set[str]]:
    """Return literal strings protected by unittest assertIn/assertNotIn calls."""
    included: set[str] = set()
    excluded: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return included, excluded
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"assertIn", "assertNotIn"} or not node.args:
            continue
        first = node.args[0]
        if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
            continue
        if node.func.attr == "assertIn":
            included.add(first.value)
        else:
            excluded.add(first.value)
    return included, excluded


def ci_collection_test_errors(text: str) -> list[str]:
    errors: list[str] = []
    broad = "pip install 'pytest>=8,<9'"
    required_positive = (
        "requirements-ci-constraints.txt",
        "pip install 'pytest==8.4.2' -c requirements-ci-constraints.txt",
        "python -m pip check",
        "python -m pytest -q tests",
    )
    included, excluded = _string_membership_assertions(text)

    if broad in included:
        errors.append("CI collection integrity test positively requires the obsolete broad pytest range")
    if broad not in excluded:
        errors.append("CI collection integrity test must explicitly reject the obsolete broad pytest range")
    for marker in required_positive:
        if marker not in included:
            errors.append(f"CI collection integrity test missing deterministic assertion: {marker}")
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
        (STANDALONE_REGRESSION_WORKFLOW, standalone_regression_errors),
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
