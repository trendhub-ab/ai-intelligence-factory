#!/usr/bin/env python3
"""Run267: fail closed when the canonical specification drifts from current CI/dependency/eyecatch governance.

Run262 remains the focused guard for the Run261 live Gemini routing and GH_PAT fan-out
contract. Run267 adds the post-Run262 operational contracts that became current in
Run263-Run266 and the required-check trigger rule confirmed during canonical sync.

This guard is intentionally zero-network and zero-provider. GitHub branch protection is
external state, so the repository snapshots the currently required context names in the
canonical specification and guarantees that the corresponding workflows can emit those
contexts for every pull request to main. External ruleset changes still require direct
GitHub ruleset audit.
"""
from __future__ import annotations

import re
from pathlib import Path

import integration_stability_guard


ROOT = Path(__file__).resolve().parent
SPEC = "AI_Intelligence_Factory_最終仕様書.md"
REQUIREMENTS = "requirements.txt"
CONSTRAINTS = "requirements-ci-constraints.txt"
INTEGRATION = ".github/workflows/integration-reconciliation-ci.yml"
FALSIFICATION = ".github/workflows/repository-falsification.yml"
NOTION = ".github/workflows/notion-access-policy-guard.yml"
RUNTIME_LAYERS = "runtime_layers.py"
EYECATCH_SCALE = "run183_eyecatch_emphasis_scale.py"
RUN263_DOC = "docs/reference/RUN263_INTEGRATION_HERMETICITY_AND_STABILITY.md"
RUN264_DOC = "docs/reference/RUN264_STANDALONE_SYNTHETIC_HERMETICITY.md"
RUN267_DOC = "docs/reference/RUN267_CANONICAL_SPEC_SYNC.md"

REQUIRED_CONTEXTS = (
    "zero-api-regression",
    "falsify-all-tracked-surfaces",
    "notion-access-policy",
)

REQUIRED_SPEC_MARKERS = (
    "Core Reliability Baseline: **Run209",
    "Documentation Governance Baseline: **Run267",
    "Integration Determinism Baseline: **Run263",
    "Standalone Synthetic Baseline: **Run264",
    "Dependency Compatibility Baseline: **Run266",
    "Required PR Check Governance Baseline: **Run267",
    "Eyecatch Baseline: **Run183",
    "`Pillow>=12.1.0,<13.0.0`",
    "`Pillow==12.3.0`",
    "`requirements-ci-constraints.txt`",
    "required status checkに指定されたWorkflowは、対象PRで必ずcheck contextを生成できなければならない",
    "pull_requestのpath filterを置かない",
    "docs/reference/RUN263_INTEGRATION_HERMETICITY_AND_STABILITY.md",
    "docs/reference/RUN264_STANDALONE_SYNTHETIC_HERMETICITY.md",
    "docs/reference/RUN267_CANONICAL_SPEC_SYNC.md",
    "現在のDocumentation Contract Freshness正本はRun267",
)

FORBIDDEN_SPEC_MARKERS = (
    "現行Functional Baseline: **Run209",
    "Documentation Governance Baseline: **Run262",
    "Eyecatch Baseline: **Run181 current**",
    "Run181 currentを基準とする。",
)


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _pull_request_block(text: str) -> tuple[bool, str]:
    match = re.search(
        r"(?ms)^[ ]{2}pull_request:\s*\n(?P<body>.*?)(?=^[ ]{2}[A-Za-z_][A-Za-z0-9_-]*:\s*$|^permissions:|^concurrency:|^jobs:|\Z)",
        text,
    )
    if not match:
        return False, ""
    return True, match.group("body")


def spec_errors(spec: str) -> list[str]:
    errors: list[str] = []
    for marker in REQUIRED_SPEC_MARKERS:
        if marker not in spec:
            errors.append(f"canonical_spec_missing_current_contract:{marker}")
    for context in REQUIRED_CONTEXTS:
        if f"`{context}`" not in spec:
            errors.append(f"canonical_spec_missing_required_context:{context}")
    for marker in FORBIDDEN_SPEC_MARKERS:
        if marker in spec:
            errors.append(f"canonical_spec_retains_stale_marker:{marker}")
    return errors


def dependency_errors(requirements: str, constraints: str, spec: str) -> list[str]:
    errors: list[str] = []
    if "Pillow>=12.1.0,<13.0.0" not in requirements.splitlines():
        errors.append("production_pillow_range_must_be_12_1_to_pre13")
    if "Pillow==12.3.0" not in constraints.splitlines():
        errors.append("ci_known_green_pillow_pin_drifted")
    if "`Pillow>=12.1.0,<13.0.0`" not in spec:
        errors.append("canonical_spec_missing_production_pillow_range")
    if "`Pillow==12.3.0`" not in spec:
        errors.append("canonical_spec_missing_ci_pillow_pin")
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


def eyecatch_errors(runtime_layers: str, scale_layer: str, spec: str) -> list[str]:
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
            errors.append(f"run183_eyecatch_scale_contract_missing:{marker}")
    if "Eyecatch Baseline: **Run183" not in spec:
        errors.append("canonical_spec_eyecatch_baseline_not_run183")
    return errors


def reference_errors(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in (RUN263_DOC, RUN264_DOC, RUN267_DOC):
        if not (root / relative).is_file():
            errors.append(f"canonical_reference_missing:{relative}")
    return errors


def collect_errors(root: Path = ROOT) -> list[str]:
    spec = _read(root, SPEC)
    errors: list[str] = []
    errors.extend(spec_errors(spec))
    errors.extend(
        dependency_errors(
            _read(root, REQUIREMENTS),
            _read(root, CONSTRAINTS),
            spec,
        )
    )
    errors.extend(
        required_check_errors(
            {
                "zero-api-regression": (INTEGRATION, _read(root, INTEGRATION)),
                "falsify-all-tracked-surfaces": (FALSIFICATION, _read(root, FALSIFICATION)),
                "notion-access-policy": (NOTION, _read(root, NOTION)),
            }
        )
    )
    errors.extend(
        eyecatch_errors(
            _read(root, RUNTIME_LAYERS),
            _read(root, EYECATCH_SCALE),
            spec,
        )
    )
    errors.extend(reference_errors(root))
    errors.extend(f"integration_stability:{item}" for item in integration_stability_guard.collect_errors(root))
    return list(dict.fromkeys(errors))


def main() -> int:
    errors = collect_errors(ROOT)
    if errors:
        print("RUN267_DOCUMENTATION_CONTRACT_GUARD=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("RUN267_DOCUMENTATION_CONTRACT_GUARD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
