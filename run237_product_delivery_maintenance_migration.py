#!/usr/bin/env python3
"""Run237 guarded migration for product-delivery maintenance ownership.

The script is intentionally idempotent and fail-closed.  It physically removes
paid-product delivery / Evidence Health orchestration from pipeline.py and leaves
only compatibility wrappers that bind the live pipeline runtime dependencies.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PIPELINE = ROOT / "pipeline.py"

IMPORT_ANCHOR = "from evidence_authority import classify_evidence, authority_rank\n"
IMPORT_BLOCK = '''from product_delivery_maintenance import (\n    current_month_id as _current_month_id_impl,\n    previous_month_id as _previous_month_id_impl,\n    run_evidence_health_maintenance as _run_evidence_health_maintenance_impl,\n    run_product_delivery_maintenance as _run_product_delivery_maintenance_impl,\n)\n'''

START_MARKER = "def _previous_month_id(today) -> str:\n"
END_MARKER = "def process_article_backlog(pending_items: list[dict] | None, generated_count: int,\n"

WRAPPERS = '''def _previous_month_id(today) -> str:\n    """Compatibility wrapper bound to the canonical Run237 month helper."""\n    return _previous_month_id_impl(today)\n\n\ndef _current_month_id(today) -> str:\n    """Compatibility wrapper bound to the canonical Run237 month helper."""\n    return _current_month_id_impl(today)\n\n\ndef run_evidence_health_maintenance() -> dict:\n    """Bind canonical zero-Gemini Evidence Health logic to live pipeline dependencies."""\n    return _run_evidence_health_maintenance_impl(\n        evidence_ledger=evidence_ledger,\n        decision_intelligence=decision_intelligence,\n        requests_module=requests,\n        logger=logger,\n        github_repo_name_from_url=_github_repo_name_from_url,\n        fetch_github_readme_context=fetch_github_readme_context,\n        extract_arxiv_id=_extract_arxiv_id,\n        fetch_arxiv_api_context=fetch_arxiv_api_context,\n        http_get_health_limited=_http_get_health_limited,\n        readable_html_text_parser=_ReadableHTMLTextParser,\n        web_context_max_bytes=WEB_CONTEXT_MAX_BYTES,\n        now_iso=lambda: datetime.now(timezone.utc).isoformat(),\n    )\n\n\ndef run_product_delivery_maintenance(today=None) -> dict:\n    """Bind canonical paid-product maintenance to live pipeline flags and timezone."""\n    return _run_product_delivery_maintenance_impl(\n        enabled=ENABLE_REVENUE_PRODUCT_PHASE2,\n        decision_intelligence=decision_intelligence,\n        logger=logger,\n        evidence_health_runner=run_evidence_health_maintenance,\n        today=today,\n        today_factory=lambda: datetime.now(ZoneInfo(NOTION_TIMEZONE)).date(),\n    )\n\n\n'''

HEAVY_MARKERS = (
    'for state in evidence_ledger.query_health_candidates(token):',
    'decision_intelligence.sync_subscriber_technology_db()',
    'for _ in range(3):',
    'decision_intelligence.create_history_monthly_digest(period)',
)


def _top_level_functions(source: str) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(source)
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def transform_source(source: str) -> str:
    """Return the canonical Run237 pipeline postimage or raise on drift."""
    if IMPORT_BLOCK not in source:
        if source.count(IMPORT_ANCHOR) != 1:
            raise RuntimeError("Run237 import anchor missing or ambiguous")
        source = source.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORT_BLOCK, 1)

    # Idempotent current-postimage path.
    if WRAPPERS in source:
        functions = _top_level_functions(source)
        for name in (
            "_previous_month_id",
            "_current_month_id",
            "run_evidence_health_maintenance",
            "run_product_delivery_maintenance",
        ):
            if name not in functions:
                raise RuntimeError(f"Run237 wrapper missing after apparent migration: {name}")
        return source

    if source.count(START_MARKER) != 1 or source.count(END_MARKER) != 1:
        raise RuntimeError("Run237 migration surface missing or ambiguous")

    start = source.index(START_MARKER)
    end = source.index(END_MARKER)
    if end <= start:
        raise RuntimeError("Run237 migration markers are out of order")

    old_surface = source[start:end]
    required_defs = (
        "def _previous_month_id",
        "def _current_month_id",
        "def run_evidence_health_maintenance",
        "def run_product_delivery_maintenance",
    )
    for marker in required_defs:
        if old_surface.count(marker) != 1:
            raise RuntimeError(f"Run237 expected definition missing/duplicated: {marker}")
    for marker in HEAVY_MARKERS:
        if marker not in old_surface:
            raise RuntimeError(f"Run237 expected historical behavior marker missing: {marker}")

    post = source[:start] + WRAPPERS + source[end:]
    ast.parse(post)

    # The orchestration algorithms must be physically gone from pipeline.py.
    post_surface = post[post.index(START_MARKER):post.index(END_MARKER)]
    for marker in HEAVY_MARKERS:
        if marker in post_surface:
            raise RuntimeError(f"Run237 heavy logic survived migration: {marker}")
    return post


def main() -> int:
    source = PIPELINE.read_text(encoding="utf-8")
    post = transform_source(source)
    if post == source:
        print("Run237 pipeline already canonical; no write")
        return 0
    PIPELINE.write_text(post, encoding="utf-8")
    print(
        "Run237 pipeline migration applied: "
        f"lines {len(source.splitlines())} -> {len(post.splitlines())}; "
        f"bytes {len(source.encode('utf-8'))} -> {len(post.encode('utf-8'))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
