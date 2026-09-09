#!/usr/bin/env python3
"""Run307 zero-network fail-closed generic use-decision product guard."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE = "run307_use_decision_member_surface.py"
WRAPPER = "run219_member_human_language_ui.py"
WORKFLOW = ".github/workflows/member-presentation-sync.yml"
FALSIFICATION = ".github/workflows/repository-falsification.yml"
NOTE_FORMAT = "run296_editorial_format_v2.py"
PAID_CONTRACT = "PAID_PRODUCT_CONTRACT.md"
REFERENCE = "docs/reference/RUN307_GENERIC_USE_DECISION_PRODUCT.md"
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
        NOTE_FORMAT: _read(root, NOTE_FORMAT),
        PAID_CONTRACT: _read(root, PAID_CONTRACT),
        REFERENCE: _read(root, REFERENCE),
        SPEC: _read(root, SPEC),
    }
    errors: list[str] = []

    for filename in (MODULE, WRAPPER, NOTE_FORMAT):
        try:
            ast.parse(texts[filename], filename=filename)
        except SyntaxError as exc:
            errors.append(f"python_syntax_error:{filename}:{exc.lineno}:{exc.msg}")

    module = texts[MODULE]
    errors += _require(
        module,
        (
            '"product_purpose": "use_decision_intelligence"',
            '"self_development_supported": True',
            '"internal_work_use_supported": True',
            '"client_proposal_supported": True',
            '"client_proposal_primary": False',
            '"source_scores_preserved": True',
            '"decision_status_preserved": True',
            '"evidence_preserved": True',
            '"notion_schema_changed": False',
            '"zero_gemini_calls": True',
            'body._body_matches = _body_matches_use_decision',
            'target._build_children = _build_children',
            '"いま、使える？"',
            '"使える場面"',
            '"使う前に確認すること"',
            '"試す・導入する次の一手"',
            '"Decision Update｜判断を変える必要がある？"',
            '「このAI、使える！」を、根拠付きで判断できる。',
        ),
        "run307_module",
    )
    for forbidden in (
        "import requests",
        "google.generativeai",
        "NOTION_TOKEN",
        "NOTION_DECISION_INTELLIGENCE_API_KEY",
    ):
        if forbidden in module:
            errors.append(f"run307_forbidden_surface:{forbidden}")

    wrapper = texts[WRAPPER]
    errors += _require(
        wrapper,
        (
            "import run270_proposal_first_member_surface as run270",
            "import run307_use_decision_member_surface as run307",
            "run270.install_navigation()",
            "run307.install_navigation()",
            "run270.install_body(sys.modules[__name__])",
            "run307.install_body(sys.modules[__name__])",
            'result["run307_use_decision_member_surface"] = run307.contract()',
            '"いま、使える？"',
            '"試す・導入する次の一手"',
        ),
        "run219_wrapper",
    )
    for before, after, label in (
        ("run270.install_navigation()", "run307.install_navigation()", "navigation"),
        ("run270.install_body(sys.modules[__name__])", "run307.install_body(sys.modules[__name__])", "body"),
    ):
        if before in wrapper and after in wrapper and wrapper.index(before) > wrapper.index(after):
            errors.append(f"run307_must_install_after_run270:{label}")

    workflow = texts[WORKFLOW]
    errors += _require(
        workflow,
        (
            "run307_use_decision_member_surface.py",
            "tests/test_run307_use_decision_member_surface.py",
            "python -m unittest tests/test_run307_use_decision_member_surface.py",
            "Use-Decision UI",
            "general use decisions",
        ),
        "member_workflow",
    )

    note_format = texts[NOTE_FORMAT]
    errors += _require(
        note_format,
        (
            "このAI、使える！",
            "Decision Brief",
            'CTA_LINK_LABEL = "月額1,980円の内容を見る"',
        ),
        "note_paid_funnel",
    )

    paid = texts[PAID_CONTRACT]
    errors += _require(
        paid,
        (
            "Run307 current product contract",
            "「このAI、使える！」を、根拠付きで判断できる",
            "フリーランス／個人事業主／1〜3名規模の小規模事業者",
            "自分の開発",
            "業務利用",
            "顧客提案は利用場面の一つ",
            "Run307以降の最終可視本文はUse-Decisionを正本とする",
            "Run270のProposal-First本文は歴史的互換層",
        ),
        "paid_contract",
    )

    reference = texts[REFERENCE]
    errors += _require(
        reference,
        (
            "# Run307 — Generic Use-Decision Product",
            "「このAI、使える！」を、根拠付きで判断できる",
            "個人事業主",
            "月額1,980円",
            "無料note → 固定LP → noteメンバーシップ",
            "ZERO Gemini/model calls",
        ),
        "run307_reference",
    )

    spec = texts[SPEC]
    errors += _require(
        spec,
        (
            "Member Surface Baseline: **Run307",
            "Paid Product Messaging Baseline: **Run307",
            "「このAI、使える！」を、根拠付きで判断できる",
            "docs/reference/RUN307_GENERIC_USE_DECISION_PRODUCT.md",
            "現在のMember Surface正本はRun307",
        ),
        "canonical_spec",
    )

    falsification = texts[FALSIFICATION]
    errors += _require(
        falsification,
        (
            "Enforce Run307 generic use-decision product contract",
            "python run307_use_decision_product_guard.py",
            "tests.test_run307_use_decision_product_guard",
            "tests.test_run307_use_decision_member_surface",
        ),
        "repository_falsification",
    )

    return list(dict.fromkeys(errors))


def main() -> int:
    errors = collect_errors(ROOT)
    if errors:
        print("RUN307_USE_DECISION_PRODUCT_GUARD=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("RUN307_USE_DECISION_PRODUCT_GUARD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
