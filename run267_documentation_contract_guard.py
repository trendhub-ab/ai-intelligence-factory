#!/usr/bin/env python3
"""Repository governance guard for current machine-verifiable invariants.

Historical Run labels and exact prose in the canonical specification are deliberately
NOT guarded here. Documentation must describe the current implementation; it must not
be forced to preserve obsolete wording merely to satisfy CI.

This guard is zero-network and zero-provider. It protects only invariants that can
cause an operational regression: required PR checks remaining triggerable, dependency
compatibility, eyecatch runtime ordering/scale, and integration hermeticity.
"""
from __future__ import annotations

import re
from pathlib import Path

import integration_stability_guard

ROOT = Path(__file__).resolve().parent
REQUIREMENTS = "requirements.txt"
CONSTRAINTS = "requirements-ci-constraints.txt"
INTEGRATION = ".github/workflows/integration-reconciliation-ci.yml"
FALSIFICATION = ".github/workflows/repository-falsification.yml"
NOTION = ".github/workflows/notion-access-policy-guard.yml"
RUNTIME_LAYERS = "runtime_layers.py"
EYECATCH_SCALE = "run183_eyecatch_emphasis_scale.py"

REQUIRED_CONTEXTS = (
    "zero-api-regression",
    "falsify-all-tracked-surfaces",
    "notion-access-policy",
)


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _pull_request_block(text: str) -> tuple[bool, str]:
    match = re.search(
        r"(?ms)^[ ]{2}pull_request:\s*\n(?P<body>.*?)(?=^[ ]{2}[A-Za-z_][A-Za-z0-9_-]*:\s*$|^permissions:|^concurrency:|^jobs:|\Z)",
        text,
    )
    return (False, "") if not match else (True, match.group("body"))


def dependency_errors(requirements: str, constraints: str) -> list[str]:
    errors: list[str] = []
    if "Pillow>=12.1.0,<13.0.0" not in requirements.splitlines():
        errors.append("production_pillow_range_must_be_12_1_to_pre13")
    if "Pillow==12.3.0" not in constraints.splitlines():
        errors.append("ci_known_green_pillow_pin_drifted")
    return errors


def required_check_errors(workflows: dict[str, tuple[str, str]]) -> list[str]:
    errors: list[str] = []
    for context, (name, text) in workflows.items():
        present, block = _pull_request_block(text)
        if not present:
            errors.append(f"required_check_missing_pull_request_trigger:{name}:{context}")
            continue
        if re.search(r"(?m)^[ ]+(?:paths|paths-ignore):\s*$", block):
            errors.append(f"required_check_has_pull_request_path_filter:{name}:{context}")
        if re.search(rf"(?m)^[ ]{{2}}{re.escape(context)}:\s*$", text) is None:
            errors.append(f"required_check_job_context_missing:{name}:{context}")
    return errors


def eyecatch_errors(runtime_layers: str, scale_layer: str) -> list[str]:
    errors: list[str] = []
    ordered = (
        '"run181_eyecatch_visual_balance.install"',
        '"run182_eyecatch_conclusion_emphasis.install"',
        '"run183_eyecatch_emphasis_scale.install"',
    )
    try:
        positions = [runtime_layers.index(marker) for marker in ordered]
    except ValueError as exc:
        errors.append(f"eyecatch_runtime_layer_missing:{exc}")
    else:
        if positions != sorted(positions):
            errors.append("eyecatch_runtime_layer_order_drifted")
    for marker in ("HIGHLIGHT_FONT_SCALE = 1.20", "HIGHLIGHT_MAX_FONT = 96"):
        if marker not in scale_layer:
            errors.append(f"eyecatch_scale_contract_missing:{marker}")
    return errors


def collect_errors(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    errors.extend(dependency_errors(_read(root, REQUIREMENTS), _read(root, CONSTRAINTS)))
    errors.extend(required_check_errors({
        "zero-api-regression": (INTEGRATION, _read(root, INTEGRATION)),
        "falsify-all-tracked-surfaces": (FALSIFICATION, _read(root, FALSIFICATION)),
        "notion-access-policy": (NOTION, _read(root, NOTION)),
    }))
    errors.extend(eyecatch_errors(_read(root, RUNTIME_LAYERS), _read(root, EYECATCH_SCALE)))
    errors.extend(f"integration_stability:{item}" for item in integration_stability_guard.collect_errors(root))
    return list(dict.fromkeys(errors))


def main() -> int:
    errors = collect_errors(ROOT)
    if errors:
        print("REPOSITORY_GOVERNANCE_GUARD=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("REPOSITORY_GOVERNANCE_GUARD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
