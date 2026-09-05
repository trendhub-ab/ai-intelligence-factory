"""Fail-closed Run240 migration for editorial-naturalness ownership.

This utility performs one mechanical ownership move only. It never changes thresholds or
regex semantics. The current pipeline is expected to contain each pre-Run240 implementation
exactly once; unexpected structure aborts before writing.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

TARGET = Path("pipeline.py")

IMPORT_ANCHOR = "from reader_experience_signals import reader_experience_signals as _reader_experience_signals_impl\n"
IMPORT_BLOCK = """from editorial_naturalness import (\n    ai_style_composite_signals as _ai_style_composite_signals_impl,\n    classify_article_claims as _classify_article_claims_impl,\n    cross_article_naturalness_signals as _cross_article_naturalness_signals_impl,\n    find_fabricated_personal_experience as _find_fabricated_personal_experience_impl,\n    human_editorial_depth_signals as _human_editorial_depth_signals_impl,\n    jaccard as _jaccard_impl,\n    rhetorical_template_phrases as _rhetorical_template_phrases_impl,\n    sentence_shingles as _sentence_shingles_impl,\n    style_sequence as _style_sequence_impl,\n)\n"""

WRAPPERS = {
    "_classify_article_claims": '''def _classify_article_claims(parsed: dict) -> dict[str, int]:\n    """Bind canonical zero-API claim-role diagnostics."""\n    return _classify_article_claims_impl(parsed)\n''',
    "_find_fabricated_personal_experience": '''def _find_fabricated_personal_experience(text: str) -> list[str]:\n    """Bind canonical fabricated-persona diagnostics."""\n    return _find_fabricated_personal_experience_impl(text)\n''',
    "_ai_style_composite_signals": '''def _ai_style_composite_signals(text: str) -> dict:\n    """Bind canonical AI-style diagnostics to live display variants."""\n    return _ai_style_composite_signals_impl(text, ARTICLE_DISPLAY_VARIANTS)\n''',
    "_sentence_shingles": '''def _sentence_shingles(value: str, width: int = 5) -> set[str]:\n    return _sentence_shingles_impl(value, width)\n''',
    "_jaccard": '''def _jaccard(a: set[str], b: set[str]) -> float:\n    return _jaccard_impl(a, b)\n''',
    "_human_editorial_depth_signals": '''def _human_editorial_depth_signals(text: str) -> dict:\n    """Bind canonical human-editorial depth diagnostics."""\n    return _human_editorial_depth_signals_impl(text)\n''',
    "_style_sequence": '''def _style_sequence(article: str) -> tuple[str, ...]:\n    return _style_sequence_impl(article)\n''',
    "_rhetorical_template_phrases": '''def _rhetorical_template_phrases(article: str) -> set[str]:\n    return _rhetorical_template_phrases_impl(article)\n''',
    "_cross_article_naturalness_signals": '''def _cross_article_naturalness_signals(article: str, peers: list[dict] | None = None) -> dict:\n    """Bind canonical cross-article diagnostics to live peer memory/opening helper."""\n    peer_rows = peers if peers is not None else _RUN_ARTICLE_STYLE_MEMORY\n    return _cross_article_naturalness_signals_impl(article, peer_rows, _article_opening_excerpt)\n''',
}


def _top_level_functions(source: str) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(source)
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = node
    return out


def transform_source(source: str) -> str:
    functions = _top_level_functions(source)

    # Idempotent post-migration path.
    if IMPORT_BLOCK in source:
        missing = [name for name in WRAPPERS if name not in functions]
        if missing:
            raise RuntimeError(f"Run240 migrated surface incomplete: {missing}")
        return source

    if source.count(IMPORT_ANCHOR) != 1:
        raise RuntimeError("Run240 import anchor missing or duplicated")

    missing = [name for name in WRAPPERS if name not in functions]
    if missing:
        raise RuntimeError(f"Run240 target functions missing: {missing}")

    lines = source.splitlines(keepends=True)
    replacements = []
    for name, wrapper in WRAPPERS.items():
        node = functions[name]
        if not getattr(node, "end_lineno", None):
            raise RuntimeError(f"Run240 cannot determine function span: {name}")
        replacements.append((node.lineno - 1, node.end_lineno, name, wrapper))

    # Replace from bottom to top so source line offsets stay stable.
    for start, end, name, wrapper in sorted(replacements, reverse=True):
        original = "".join(lines[start:end])
        if len(original.splitlines()) < 2:
            raise RuntimeError(f"Run240 suspiciously small preimage: {name}")
        lines[start:end] = [wrapper + "\n"]

    migrated = "".join(lines)
    migrated = migrated.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORT_BLOCK, 1)
    ast.parse(migrated)
    return migrated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--path", default=str(TARGET))
    args = parser.parse_args()

    path = Path(args.path)
    source = path.read_text(encoding="utf-8")
    migrated = transform_source(source)
    changed = migrated != source
    print(f"RUN240_MIGRATION changed={str(changed).lower()} path={path}")
    if args.write and changed:
        path.write_text(migrated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
