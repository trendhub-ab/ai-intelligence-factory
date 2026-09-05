from __future__ import annotations

import argparse
import ast
from pathlib import Path

PIPELINE_PATH = Path("pipeline.py")
MODULE_PATH = Path("content_generation_protocol.py")
EXPECTED_PREIMAGE_LINES = 11172
EXPECTED_TARGET_LINES = {
    "build_monthly_digest_markdown": 66,
    "_source_fact_discipline": 61,
    "_human_editorial_style_rules": 73,
    "_parse_gemini_response": 99,
    "_promote_plaintext_section_titles": 63,
}

IMPORT_BLOCK = '''from content_generation_protocol import (
    _source_fact_discipline as _source_fact_discipline_impl,
    _human_editorial_style_rules as _human_editorial_style_rules_impl,
    _parse_gemini_response as _parse_gemini_response_impl,
    _promote_plaintext_section_titles as _promote_plaintext_section_titles_impl,
    build_monthly_digest_markdown as _build_monthly_digest_markdown_impl,
)
'''
IMPORT_MARKER = "from content_generation_protocol import ("
IMPORT_ANCHOR = '''from deferred_queue_policy import (
    deferred_ttl_days as _deferred_ttl_days_impl, deferred_key as _deferred_key_impl,
    deferred_serializable as _deferred_serializable_impl, valid_deferred_items as _valid_deferred_items_impl,
    build_deferred_payload as _build_deferred_payload_impl, merge_rank_deferred_candidates as _merge_rank_deferred_candidates_impl,
    pop_deferred_candidates as _pop_deferred_candidates_impl,
)
'''

MODULE_PREAMBLE = '''from __future__ import annotations

import re

# Run243: canonical deterministic article-generation / presentation protocol.
# No provider SDK, network, persistence, environment or credential access is allowed here.

'''


def _top_level_functions(source: str) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(source)
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def _segment(source_lines: list[str], node: ast.FunctionDef) -> str:
    return "".join(source_lines[node.lineno - 1 : node.end_lineno])


def _replace_header(segment: str, old: str, new: str, label: str) -> str:
    if not segment.startswith(old):
        raise RuntimeError(f"{label}: unexpected function header")
    if segment.count(old) != 1:
        raise RuntimeError(f"{label}: header ambiguity")
    return new + segment[len(old):]


def _build_module(source: str) -> str:
    lines = source.splitlines(keepends=True)
    funcs = _top_level_functions(source)
    missing = [name for name in EXPECTED_TARGET_LINES if name not in funcs]
    if missing:
        raise RuntimeError(f"Run243 target functions missing: {missing}")
    for name, expected in EXPECTED_TARGET_LINES.items():
        node = funcs[name]
        actual = node.end_lineno - node.lineno + 1
        if actual != expected:
            raise RuntimeError(f"{name}: expected {expected} lines, found {actual}")

    parts: list[str] = []
    order = [
        "build_monthly_digest_markdown",
        "_source_fact_discipline",
        "_human_editorial_style_rules",
        "_parse_gemini_response",
        "_promote_plaintext_section_titles",
    ]
    for name in order:
        seg = _segment(lines, funcs[name])
        if name == "build_monthly_digest_markdown":
            seg = _replace_header(
                seg,
                "def build_monthly_digest_markdown(target_date, items: list[dict]) -> str:",
                "def build_monthly_digest_markdown(target_date, items: list[dict], *, STATUS_DEEP_DIVE, ARTICLE_STATUS_READY, STATUS_STOCKED) -> str:",
                name,
            )
        elif name == "_parse_gemini_response":
            seg = _replace_header(
                seg,
                "def _parse_gemini_response(full_text: str) -> dict:",
                "def _parse_gemini_response(full_text: str, *, SECTION_SPLIT_TOKEN, _display_heading_aliases, _extract_any_markdown_section, _extract_note_title, _is_meaningful_field, _normalize_decision, _strip_internal_note_control_lines) -> dict:",
                name,
            )
        parts.append(seg.rstrip() + "\n\n\n")
    module_source = MODULE_PREAMBLE + "".join(parts).rstrip() + "\n"
    compile(module_source, str(MODULE_PATH), "exec")
    return module_source


def _pipeline_replacement(name: str) -> str:
    if name == "build_monthly_digest_markdown":
        return '''def build_monthly_digest_markdown(target_date, items: list[dict]) -> str:
    return _build_monthly_digest_markdown_impl(
        target_date,
        items,
        STATUS_DEEP_DIVE=STATUS_DEEP_DIVE,
        ARTICLE_STATUS_READY=ARTICLE_STATUS_READY,
        STATUS_STOCKED=STATUS_STOCKED,
    )
'''
    if name == "_source_fact_discipline":
        return "_source_fact_discipline = _source_fact_discipline_impl\n"
    if name == "_human_editorial_style_rules":
        return "_human_editorial_style_rules = _human_editorial_style_rules_impl\n"
    if name == "_parse_gemini_response":
        return '''def _parse_gemini_response(full_text: str) -> dict:
    return _parse_gemini_response_impl(
        full_text,
        SECTION_SPLIT_TOKEN=SECTION_SPLIT_TOKEN,
        _display_heading_aliases=_display_heading_aliases,
        _extract_any_markdown_section=_extract_any_markdown_section,
        _extract_note_title=_extract_note_title,
        _is_meaningful_field=_is_meaningful_field,
        _normalize_decision=_normalize_decision,
        _strip_internal_note_control_lines=_strip_internal_note_control_lines,
    )
'''
    if name == "_promote_plaintext_section_titles":
        return "_promote_plaintext_section_titles = _promote_plaintext_section_titles_impl\n"
    raise KeyError(name)


def _migrate_pipeline(source: str) -> str:
    if len(source.splitlines()) != EXPECTED_PREIMAGE_LINES:
        raise RuntimeError(
            f"Run243 preimage line guard failed: expected {EXPECTED_PREIMAGE_LINES}, found {len(source.splitlines())}"
        )
    if IMPORT_MARKER in source:
        raise RuntimeError("Run243 canonical import already present in guarded preimage path")
    if source.count(IMPORT_ANCHOR) != 1:
        raise RuntimeError("Run243 import anchor changed or became ambiguous")

    lines = source.splitlines(keepends=True)
    funcs = _top_level_functions(source)
    for name, expected in EXPECTED_TARGET_LINES.items():
        node = funcs.get(name)
        if node is None:
            raise RuntimeError(f"Run243 target missing: {name}")
        actual = node.end_lineno - node.lineno + 1
        if actual != expected:
            raise RuntimeError(f"{name}: expected {expected} lines, found {actual}")

    replacements = []
    for name in EXPECTED_TARGET_LINES:
        node = funcs[name]
        replacements.append((node.lineno - 1, node.end_lineno, _pipeline_replacement(name)))
    for start, end, replacement in sorted(replacements, reverse=True):
        lines[start:end] = [replacement]
    migrated = "".join(lines)
    migrated = migrated.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORT_BLOCK + "\n", 1)
    compile(migrated, str(PIPELINE_PATH), "exec")
    return migrated


def _validate_postimage(pipeline_source: str, module_source: str) -> None:
    if IMPORT_MARKER not in pipeline_source:
        raise RuntimeError("Run243 postimage missing canonical import")
    funcs = _top_level_functions(pipeline_source)
    for moved in ("_source_fact_discipline", "_human_editorial_style_rules", "_promote_plaintext_section_titles"):
        if moved in funcs:
            raise RuntimeError(f"Run243 heavy implementation still owned by pipeline: {moved}")
    for wrapper, max_lines in (("_parse_gemini_response", 13), ("build_monthly_digest_markdown", 9)):
        node = funcs.get(wrapper)
        if node is None:
            raise RuntimeError(f"Run243 wrapper missing: {wrapper}")
        size = node.end_lineno - node.lineno + 1
        if size > max_lines:
            raise RuntimeError(f"Run243 wrapper too large: {wrapper}={size}")
    if "【GitHub専用 Fact Discipline】" in pipeline_source:
        raise RuntimeError("Run243 Fact Discipline body still present in pipeline")
    if "【Human Editorial Style｜最重要】" in pipeline_source:
        raise RuntimeError("Run243 Human Editorial Style body still present in pipeline")
    if "【GitHub専用 Fact Discipline】" not in module_source or "【Human Editorial Style｜最重要】" not in module_source:
        raise RuntimeError("Run243 canonical prompt bodies missing from module")
    module_funcs = _top_level_functions(module_source)
    missing = [name for name in EXPECTED_TARGET_LINES if name not in module_funcs]
    if missing:
        raise RuntimeError(f"Run243 module functions missing: {missing}")
    if len(pipeline_source.splitlines()) >= 10900:
        raise RuntimeError(f"Run243 physical slimming insufficient: {len(pipeline_source.splitlines())} lines")
    compile(pipeline_source, str(PIPELINE_PATH), "exec")
    compile(module_source, str(MODULE_PATH), "exec")


def transform(pipeline_source: str, existing_module_source: str | None = None) -> tuple[str, str, bool]:
    if IMPORT_MARKER in pipeline_source:
        if not existing_module_source:
            raise RuntimeError("Run243 pipeline is migrated but canonical module is missing")
        _validate_postimage(pipeline_source, existing_module_source)
        return pipeline_source, existing_module_source, False
    module_source = _build_module(pipeline_source)
    migrated = _migrate_pipeline(pipeline_source)
    _validate_postimage(migrated, module_source)
    return migrated, module_source, True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    pipeline_source = PIPELINE_PATH.read_text()
    existing_module = MODULE_PATH.read_text() if MODULE_PATH.exists() else None
    migrated, module_source, changed = transform(pipeline_source, existing_module)
    print(f"Run243 migration preview: {len(pipeline_source.splitlines())} -> {len(migrated.splitlines())} lines")
    if not changed:
        print("Run243 migration: already canonical / idempotent PASS")
        return 0
    if args.write:
        MODULE_PATH.write_text(module_source)
        PIPELINE_PATH.write_text(migrated)
        print("Run243 migration write: PASS")
    else:
        print("Run243 migration dry-run: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
