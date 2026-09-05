from __future__ import annotations

import ast
from pathlib import Path


PIPELINE = Path("pipeline.py")
SPEC = Path("AI_Intelligence_Factory_最終仕様書.md")
EXPECTED = [
    "_truncate_text_context",
    "_truncate_source_context",
    "_verification_excerpt",
    "_truncate_verification_context",
    "_merge_verification_context",
]


def patch_pipeline() -> None:
    text = PIPELINE.read_text(encoding="utf-8")
    start_token = "def _truncate_text_context(text: str, max_chars: int) -> str:"
    end_token = "def fetch_github_readme_context(repo_name: str) -> str:"
    if start_token not in text or end_token not in text:
        raise SystemExit("Run236 guard failed: expected evidence-context block anchors are missing")
    start = text.index(start_token)
    end = text.index(end_token, start)
    block = text[start:end]
    parsed = ast.parse(block)
    names = [node.name for node in parsed.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if names != EXPECTED:
        raise SystemExit(f"Run236 guard failed: unexpected top-level functions in migration block: {names!r}")
    required_fragments = [
        'marker = "\\n\\n[...verification context omitted...]\\n\\n"',
        'head = int(payload * 0.68)',
        'new_budget = min(len(new), int(payload * 0.60))',
        'return _verification_excerpt(old, old_budget) + separator + _verification_excerpt(new, new_budget)',
    ]
    for fragment in required_fragments:
        if fragment not in block:
            raise SystemExit(f"Run236 guard failed: historical behavior fragment missing: {fragment}")

    replacement = '''from evidence_context import (\n    merge_verification_context as _merge_verification_context_impl,\n    truncate_text_context as _truncate_text_context,\n    verification_excerpt as _verification_excerpt,\n)\n\n\ndef _truncate_source_context(text: str) -> str:\n    """Bind the pure helper to the current runtime source-context ceiling."""\n    return _truncate_text_context(text, SOURCE_CONTEXT_MAX_CHARS)\n\n\ndef _truncate_verification_context(text: str) -> str:\n    """Bind the pure excerpt helper to the current verification ceiling."""\n    return _verification_excerpt(text, VERIFICATION_CONTEXT_MAX_CHARS)\n\n\ndef _merge_verification_context(existing: str, new_evidence: str) -> str:\n    """Bind the pure merge helper to the current verification ceiling."""\n    return _merge_verification_context_impl(existing, new_evidence, VERIFICATION_CONTEXT_MAX_CHARS)\n\n\n'''
    updated = text[:start] + replacement + text[end:]
    if updated == text:
        raise SystemExit("Run236 guard failed: pipeline patch made no change")
    ast.parse(updated)
    PIPELINE.write_text(updated, encoding="utf-8")


def patch_spec() -> None:
    text = SPEC.read_text(encoding="utf-8")
    old = "Pipeline Modularization Baseline: **Run231 — zero-quality-change runtime separation / performance telemetry / staged legacy renderer extraction**"
    new = "Pipeline Modularization Baseline: **Run236 — source-normalization + pure evidence-context extraction / zero-quality-change strangler modularization**"
    if old not in text:
        if new in text:
            return
        raise SystemExit("Run236 guard failed: canonical modularization baseline anchor is missing")
    text = text.replace(old, new, 1)
    anchor = "Run231詳細: `docs/reference/RUN231_PIPELINE_MODULARIZATION.md`\n"
    addition = (
        anchor
        + "\n"
        + "- Run235でsource normalizationの重複実装を`source_normalization.py`へ集約し、`pipeline.py`は単一正本を参照する。\n"
        + "- Run236でEvidence本文のtruncate/excerpt/mergeロジックをprovider・DB非依存の`evidence_context.py`へ抽出する。`pipeline.py`には現行の動的文字数上限を束縛する薄いwrapperだけを残す。\n"
        + "- Run235/236はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。\n"
    )
    if anchor not in text:
        raise SystemExit("Run236 guard failed: Run231 detail anchor is missing")
    text = text.replace(anchor, addition, 1)
    SPEC.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    patch_pipeline()
    patch_spec()
