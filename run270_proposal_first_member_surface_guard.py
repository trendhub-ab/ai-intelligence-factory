#!/usr/bin/env python3
"""Run270 zero-network fail-closed historical Proposal-First compatibility guard.

Run307 supersedes Run270 as the current visible member-product framing. This guard keeps the
Run270 compatibility layer intact and verifies that Run307 installs after it rather than deleting
or silently bypassing the historical migration surface.
"""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE = "run270_proposal_first_member_surface.py"
WRAPPER = "run219_member_human_language_ui.py"
WORKFLOW = ".github/workflows/member-presentation-sync.yml"
FALSIFICATION = ".github/workflows/repository-falsification.yml"
PAID_CONTRACT = "PAID_PRODUCT_CONTRACT.md"
REFERENCE = "docs/reference/RUN270_PROPOSAL_FIRST_MEMBER_SURFACE.md"
SPEC = "AI_Intelligence_Factory_最終仕様書.md"


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _require(text: str, markers: tuple[str, ...], prefix: str) -> list[str]:
    return [f"{prefix}_missing:{marker}" for marker in markers if marker not in text]


def collect_errors(root: Path = ROOT) -> list[str]:
    texts = {
        MODULE: _read(root, MODULE),
        WRAPPER: _read(root, WRAPPER),
        WORKFLOW: _read(root, WORKFLOW),
        FALSIFICATION: _read(root, FALSIFICATION),
        PAID_CONTRACT: _read(root, PAID_CONTRACT),
        REFERENCE: _read(root, REFERENCE),
        SPEC: _read(root, SPEC),
    }
    errors: list[str] = []

    for filename in (MODULE, WRAPPER):
        try:
            ast.parse(texts[filename], filename=filename)
        except SyntaxError as exc:
            errors.append(f"python_syntax_error:{filename}:{exc.lineno}:{exc.msg}")

    module = texts[MODULE]
    errors += _require(
        module,
        (
            '"product_purpose": "proposal_first_decision_intelligence"',
            '"client_proposal_primary": True',
            '"internal_work_use_secondary": True',
            '"source_scores_preserved": True',
            '"decision_status_preserved": True',
            '"evidence_preserved": True',
            '"notion_schema_changed": False',
            '"zero_gemini_calls": True',
            'body._body_matches = _body_matches_proposal_first',
            'target._build_children = _build_children',
            '"顧客にどう答える？"',
            '"提案できる場面"',
            '"提案前に確認すること"',
            '"提案・検証の次の一手"',
        ),
        "run270_module",
    )
    for forbidden in (
        "import requests",
        "google.generativeai",
        "NOTION_TOKEN",
        "NOTION_DECISION_INTELLIGENCE_API_KEY",
    ):
        if forbidden in module:
            errors.append(f"run270_forbidden_surface:{forbidden}")

    wrapper = texts[WRAPPER]
    errors += _require(
        wrapper,
        (
            "import run250_member_client_action_product as run250",
            "import run270_proposal_first_member_surface as run270",
            "import run307_use_decision_member_surface as run307",
            "run250.install_navigation()",
            "run270.install_navigation()",
            "run307.install_navigation()",
            "run250.install_body(sys.modules[__name__])",
            "run270.install_body(sys.modules[__name__])",
            "run307.install_body(sys.modules[__name__])",
            'result["run270_proposal_first_member_surface"] = run270.contract()',
        ),
        "run219_wrapper",
    )
    for before, after, label in (
        ("run250.install_navigation()", "run270.install_navigation()", "navigation_after_run250"),
        ("run270.install_navigation()", "run307.install_navigation()", "navigation_before_run307"),
        ("run250.install_body(sys.modules[__name__])", "run270.install_body(sys.modules[__name__])", "body_after_run250"),
        ("run270.install_body(sys.modules[__name__])", "run307.install_body(sys.modules[__name__])", "body_before_run307"),
    ):
        if before in wrapper and after in wrapper and wrapper.index(before) > wrapper.index(after):
            errors.append(f"run270_compatibility_order_drifted:{label}")

    workflow = texts[WORKFLOW]
    errors += _require(
        workflow,
        (
            "run270_proposal_first_member_surface.py",
            "tests/test_run270_proposal_first_member_surface.py",
            "python -m unittest tests/test_run270_proposal_first_member_surface.py",
            "run307_use_decision_member_surface.py",
            "Use-Decision UI",
        ),
        "member_workflow",
    )

    paid = texts[PAID_CONTRACT]
    errors += _require(
        paid,
        (
            "Run307 current product contract",
            "Run270のProposal-First本文は歴史的互換層",
            "Run270 — Proposal-First member visible surface / static Notion surface alignment（歴史的互換層）",
        ),
        "paid_contract",
    )

    reference = texts[REFERENCE]
    errors += _require(
        reference,
        (
            "# Run270 — Proposal-First Member Surface",
            "3c5479ff-dca9-8103-bff0-f2d5f408d35f",
            "3d0479ff-dca9-81de-b614-fef528d2f32c",
            "3d3479ff-dca9-8119-b0d8-c014b068fe82",
            "顧客課題 / 提案シーン",
            "次の判断 / 提案更新日",
            "ZERO Gemini/model calls",
        ),
        "run270_reference",
    )

    spec = texts[SPEC]
    errors += _require(
        spec,
        (
            "Member Surface Baseline: **Run307",
            "Run270",
            "Proposal-First Member Surface",
            "docs/reference/RUN270_PROPOSAL_FIRST_MEMBER_SURFACE.md",
            "docs/reference/RUN307_GENERIC_USE_DECISION_PRODUCT.md",
        ),
        "canonical_spec",
    )

    falsification = texts[FALSIFICATION]
    errors += _require(
        falsification,
        (
            "Enforce Run270 Proposal-First member surface contract",
            "python run270_proposal_first_member_surface_guard.py",
            "tests.test_run270_proposal_first_member_surface_guard",
            "tests.test_run270_proposal_first_member_surface",
        ),
        "repository_falsification",
    )

    return list(dict.fromkeys(errors))


def main() -> int:
    errors = collect_errors(ROOT)
    if errors:
        print("RUN270_PROPOSAL_FIRST_MEMBER_SURFACE_GUARD=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("RUN270_PROPOSAL_FIRST_MEMBER_SURFACE_GUARD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
