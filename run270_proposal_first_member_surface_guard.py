#!/usr/bin/env python3
"""Fail closed if the historical member-surface compatibility layer becomes unsafe.

Run270 is not current product authority; Run307 supersedes its visible framing.
This guard therefore protects only compatibility invariants that still matter at runtime:
- the historical layer remains deterministic and zero-provider/zero-network;
- source scores, decision status, evidence and Notion schema are preserved;
- the compatibility layer stays between the older Run250 layer and current Run307 layer.

Historical copy, UUIDs, reference documents and canonical-spec wording are intentionally
not executable CI contracts.
"""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE = "run270_proposal_first_member_surface.py"
WRAPPER = "run219_member_human_language_ui.py"


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _require(text: str, markers: tuple[str, ...], prefix: str) -> list[str]:
    return [f"{prefix}_missing:{marker}" for marker in markers if marker not in text]


def collect_errors(root: Path = ROOT) -> list[str]:
    module = _read(root, MODULE)
    wrapper = _read(root, WRAPPER)
    errors: list[str] = []

    for filename, text in ((MODULE, module), (WRAPPER, wrapper)):
        try:
            ast.parse(text, filename=filename)
        except SyntaxError as exc:
            errors.append(f"python_syntax_error:{filename}:{exc.lineno}:{exc.msg}")

    errors += _require(
        module,
        (
            '"source_scores_preserved": True',
            '"decision_status_preserved": True',
            '"evidence_preserved": True',
            '"notion_schema_changed": False',
            '"zero_gemini_calls": True',
            'body._body_matches = _body_matches_proposal_first',
            'target._build_children = _build_children',
        ),
        "run270_compatibility",
    )
    for forbidden in (
        "import requests",
        "google.generativeai",
        "NOTION_TOKEN",
        "NOTION_DECISION_INTELLIGENCE_API_KEY",
    ):
        if forbidden in module:
            errors.append(f"run270_forbidden_surface:{forbidden}")

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
        ),
        "member_wrapper",
    )
    for before, after, label in (
        ("run250.install_navigation()", "run270.install_navigation()", "navigation_after_run250"),
        ("run270.install_navigation()", "run307.install_navigation()", "navigation_before_run307"),
        ("run250.install_body(sys.modules[__name__])", "run270.install_body(sys.modules[__name__])", "body_after_run250"),
        ("run270.install_body(sys.modules[__name__])", "run307.install_body(sys.modules[__name__])", "body_before_run307"),
    ):
        if before in wrapper and after in wrapper and wrapper.index(before) > wrapper.index(after):
            errors.append(f"run270_compatibility_order_drifted:{label}")

    return list(dict.fromkeys(errors))


def main() -> int:
    errors = collect_errors(ROOT)
    if errors:
        print("MEMBER_COMPATIBILITY_GUARD=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("MEMBER_COMPATIBILITY_GUARD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
