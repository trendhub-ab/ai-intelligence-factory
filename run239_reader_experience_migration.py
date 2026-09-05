#!/usr/bin/env python3
"""Fail-closed one-shot migration for Run239 reader-experience extraction."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIPELINE = ROOT / "pipeline.py"
MODULE = ROOT / "reader_experience_signals.py"
TARGET = "_reader_experience_signals"
PUBLIC = "reader_experience_signals"
ALIAS = "_reader_experience_signals_impl"
EXPECTED_OPENING_CALL = "intro = _article_opening_excerpt(body, 700)"
REPLACEMENT_OPENING_CALL = "intro = article_opening_excerpt_fn(body, 700)"


def _top_level_function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _deep_dive_import(tree: ast.Module) -> ast.ImportFrom:
    matches = [
        node for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "deep_dive_portfolio"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one deep_dive_portfolio import, found {len(matches)}")
    return matches[0]


def _canonical_import_present(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.module != "reader_experience_signals":
            continue
        for alias in node.names:
            if alias.name == PUBLIC and alias.asname == ALIAS:
                return True
    return False


def _wrapper_is_exact(node: ast.FunctionDef | None) -> bool:
    if node is None or len(node.args.args) != 1 or node.args.args[0].arg != "article":
        return False
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    if len(body) != 1 or not isinstance(body[0], ast.Return):
        return False
    call = body[0].value
    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != ALIAS:
        return False
    return (
        len(call.args) == 2
        and isinstance(call.args[0], ast.Name) and call.args[0].id == "article"
        and isinstance(call.args[1], ast.Name) and call.args[1].id == "_article_opening_excerpt"
        and not call.keywords
    )


def _build_module(function_source: str) -> str:
    expected_header = "def _reader_experience_signals(article: str) -> dict:"
    if function_source.count(expected_header) != 1:
        raise RuntimeError("reader experience function header changed; refusing migration")
    if function_source.count(EXPECTED_OPENING_CALL) != 1:
        raise RuntimeError("opening excerpt binding changed; refusing migration")
    transformed = function_source.replace(
        expected_header,
        "def reader_experience_signals(article: str, article_opening_excerpt_fn) -> dict:",
        1,
    ).replace(EXPECTED_OPENING_CALL, REPLACEMENT_OPENING_CALL, 1)
    if "_article_opening_excerpt" in transformed:
        raise RuntimeError("unexpected live pipeline helper remained in extracted module")
    return (
        "\"\"\"Canonical zero-API reader-experience diagnostics extracted from pipeline.py.\"\"\"\n\n"
        "from __future__ import annotations\n\n"
        "import re\n\n\n"
        + transformed.rstrip()
        + "\n"
    )


def transform(source: str) -> tuple[str, str | None]:
    tree = ast.parse(source)
    node = _top_level_function(tree, TARGET)

    if _wrapper_is_exact(node) and _canonical_import_present(tree):
        if not MODULE.exists():
            raise RuntimeError("pipeline already migrated but canonical module is missing")
        return source, None

    if node is None:
        raise RuntimeError("reader experience function missing; refusing migration")
    if getattr(node, "end_lineno", None) is None:
        raise RuntimeError("Python AST end_lineno unavailable")
    if node.end_lineno - node.lineno + 1 < 350:
        raise RuntimeError("target no longer has the expected heavy implementation; refusing migration")
    if _canonical_import_present(tree):
        raise RuntimeError("canonical import exists while heavy implementation remains")

    lines = source.splitlines(keepends=True)
    function_source = "".join(lines[node.lineno - 1: node.end_lineno])
    module_source = _build_module(function_source)

    wrapper = (
        "def _reader_experience_signals(article: str) -> dict:\n"
        "    \"\"\"Bind canonical zero-API diagnostics to the live opening-excerpt helper.\"\"\"\n"
        "    return _reader_experience_signals_impl(article, _article_opening_excerpt)\n"
    )
    lines[node.lineno - 1: node.end_lineno] = [wrapper]
    migrated = "".join(lines)

    migrated_tree = ast.parse(migrated)
    import_node = _deep_dive_import(migrated_tree)
    migrated_lines = migrated.splitlines(keepends=True)
    import_line = (
        "from reader_experience_signals import "
        "reader_experience_signals as _reader_experience_signals_impl\n"
    )
    migrated_lines.insert(import_node.end_lineno, import_line)
    migrated = "".join(migrated_lines)

    final_tree = ast.parse(migrated)
    if not _canonical_import_present(final_tree):
        raise RuntimeError("failed to install canonical reader experience import")
    if not _wrapper_is_exact(_top_level_function(final_tree, TARGET)):
        raise RuntimeError("failed to install exact thin reader experience wrapper")
    return migrated, module_source


def main() -> int:
    before = PIPELINE.read_text(encoding="utf-8")
    after, module_source = transform(before)
    if after == before and module_source is None:
        print("Run239 migration already applied")
        return 0
    if module_source is None:
        raise RuntimeError("migration changed pipeline without producing canonical module")
    if MODULE.exists():
        raise RuntimeError("reader_experience_signals.py already exists unexpectedly")
    PIPELINE.write_text(after, encoding="utf-8")
    MODULE.write_text(module_source, encoding="utf-8")
    print(
        "Run239 reader-experience migration applied: "
        f"pipeline_lines={len(before.splitlines())}->{len(after.splitlines())}; "
        f"module_lines={len(module_source.splitlines())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
