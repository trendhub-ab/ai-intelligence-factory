from __future__ import annotations

import argparse
import ast
from pathlib import Path

EXPORTED_NAMES = (
    "_detect_title_language",
    "_japanese_product_descriptor",
    "_multilingual_display_name",
    "_notion_display_name",
    "_source_summary_with_original",
    "normalize_item",
)

IMPORT_BLOCK = '''from source_normalization import (\n    _detect_title_language,\n    _japanese_product_descriptor,\n    _multilingual_display_name,\n    _notion_display_name,\n    _source_summary_with_original,\n    normalize_item,\n)\n\n'''


def transform_source(source: str) -> str:
    tree = ast.parse(source)
    nodes = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in EXPORTED_NAMES
    ]
    names = tuple(node.name for node in nodes)
    if not nodes:
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "source_normalization":
                imported.update(alias.asname or alias.name for alias in node.names)
        if set(EXPORTED_NAMES).issubset(imported):
            return source
        raise RuntimeError("Stage3B source-normalization surface is neither legacy defs nor canonical imports")
    if names != EXPORTED_NAMES:
        raise RuntimeError(f"Unexpected Stage3B function order/surface: {names!r}")

    first, last = nodes[0], nodes[-1]
    between = [
        node for node in tree.body
        if getattr(node, "lineno", 0) >= first.lineno
        and getattr(node, "end_lineno", 0) <= last.end_lineno
    ]
    if tuple(node.name for node in between if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))) != EXPORTED_NAMES:
        raise RuntimeError("Unexpected statement inside Stage3B surgical span")
    if any(not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in between):
        raise RuntimeError("Non-function statement inside Stage3B surgical span")

    lines = source.splitlines(keepends=True)
    transformed = "".join(lines[: first.lineno - 1]) + IMPORT_BLOCK + "".join(lines[last.end_lineno :])
    ast.parse(transformed)
    return transformed


def main() -> int:
    parser = argparse.ArgumentParser(description="Run235 Stage3B deterministic source-normalization dedup migration")
    parser.add_argument("path", nargs="?", default="pipeline.py")
    parser.add_argument("--write", action="store_true", help="write the transformed source in place")
    parser.add_argument("--output", help="write transformed source to a separate path")
    args = parser.parse_args()

    path = Path(args.path)
    source = path.read_text(encoding="utf-8")
    transformed = transform_source(source)
    changed = transformed != source

    if args.output:
        Path(args.output).write_text(transformed, encoding="utf-8")
    if args.write and changed:
        path.write_text(transformed, encoding="utf-8")

    before = len(source.splitlines())
    after = len(transformed.splitlines())
    print(f"RUN235_STAGE3B changed={str(changed).lower()} lines_before={before} lines_after={after} delta={after-before}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
