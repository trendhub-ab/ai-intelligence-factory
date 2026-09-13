#!/usr/bin/env python3
"""Fail closed when live acquisition precision or zero-model smoke safety drifts.

This guard protects executable acquisition behavior only. Historical Run labels,
canonical-spec prose, and reference-document wording are intentionally excluded.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE_ACQUISITION = "business_source_acquisition.py"
PRECISION = "run269_acquisition_precision.py"
CURRENT_STATE = "run269_vendor_current_state.py"
LAYER = "run269_business_source_precision.py"
SMOKE = "run269_live_acquisition_smoke.py"
ENTRYPOINT = "production_pipeline.py"
LIVE_WORKFLOW = ".github/workflows/run269-live-acquisition-smoke.yml"

REQUIRED_VENDORS = (
    "OpenAI", "Anthropic", "Google Gemini", "Alibaba Qwen", "DeepSeek",
    "ByteDance Doubao/Seed", "Moonshot AI Kimi", "Zhipu AI GLM", "MiniMax",
    "Baidu ERNIE", "Tencent Hunyuan",
)


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _require(text: str, markers: tuple[str, ...], prefix: str) -> list[str]:
    return [f"{prefix}_missing:{marker}" for marker in markers if marker not in text]


def collect_errors(root: Path = ROOT) -> list[str]:
    texts = {
        BASE_ACQUISITION: _read(root, BASE_ACQUISITION),
        PRECISION: _read(root, PRECISION),
        CURRENT_STATE: _read(root, CURRENT_STATE),
        LAYER: _read(root, LAYER),
        SMOKE: _read(root, SMOKE),
        ENTRYPOINT: _read(root, ENTRYPOINT),
        LIVE_WORKFLOW: _read(root, LIVE_WORKFLOW),
    }
    errors: list[str] = []

    for filename in (PRECISION, CURRENT_STATE, LAYER, SMOKE, ENTRYPOINT):
        try:
            ast.parse(texts[filename], filename=filename)
        except SyntaxError as exc:
            errors.append(f"python_syntax_error:{filename}:{exc.lineno}:{exc.msg}")

    precision = texts[PRECISION]
    errors += _require(
        precision,
        (
            "import business_source_acquisition as run268",
            "SOURCE_ROLE_CONTRACT = run268.SOURCE_ROLE_CONTRACT",
            "HN_LOOKBACK_DAYS = 30",
            'restrictSearchableAttributes": "title"',
            '"numericFilters": f"created_at_i>{cutoff}"',
            "def _query_matches_title",
            "not _query_matches_title(title, query)",
            '"structured_html"',
            '"structured_embedded"',
            '"page_fallback"',
        ),
        "precision",
    )
    query_block = precision.split("HN_AI_QUERIES = (", 1)[1].split(")", 1)[0] if "HN_AI_QUERIES = (" in precision else ""
    if '\n    "AI",' in "\n" + query_block:
        errors.append("hn_raw_ai_query_reintroduced")
    if "hacker-news.firebaseio.com/v0/topstories.json" in precision:
        errors.append("hn_firebase_topstories_reintroduced")

    effective_registry = texts[BASE_ACQUISITION] + "\n" + precision + "\n" + texts[CURRENT_STATE]
    for vendor in REQUIRED_VENDORS:
        if vendor not in effective_registry:
            errors.append(f"vendor_missing:{vendor}")

    current_state = texts[CURRENT_STATE]
    errors += _require(
        current_state,
        (
            '"current_state_page": True',
            '"structured_current_state"',
            "_MODEL_LIST_MARKERS",
            "_MODEL_STATE_MARKERS",
            "def _has_model_list_current_state",
            "def _normalize_existing_current_state",
            'details["current_state_timestamp_observed"]',
            'details["current_state_model_markers_observed"]',
            'details["current_state_transport"]',
            '"published_at": updated_at',
            "Never fabricate a date",
            "redirected outside vendor allowlist",
        ),
        "current_state",
    )

    layer = texts[LAYER]
    errors += _require(
        layer,
        (
            "from run269_vendor_current_state import",
            'p.fetch_hackernews_top = fetch_hackernews_run269',
            'p.fetch_producthunt_trending = fetch_official_vendor_run269',
            'required = ("normalize_item", "requests")',
            'http_post=getattr(p.requests, "post", None)',
        ),
        "precision_layer",
    )

    entrypoint = texts[ENTRYPOINT]
    errors += _require(
        entrypoint,
        (
            "from run268_business_source_strategy import install as install_run268_business_source_strategy",
            "from run269_business_source_precision import install as install_run269_business_source_precision",
            "install_run268_business_source_strategy(pipeline)",
            "install_run269_business_source_precision(pipeline)",
        ),
        "production_entrypoint",
    )
    if all(marker in entrypoint for marker in ("install_run268_business_source_strategy(pipeline)", "install_run269_business_source_precision(pipeline)")):
        if entrypoint.index("install_run268_business_source_strategy(pipeline)") > entrypoint.index("install_run269_business_source_precision(pipeline)"):
            errors.append("precision_layer_must_install_after_source_strategy")

    smoke = texts[SMOKE]
    errors += _require(
        smoke,
        (
            "gemini_model_calls\": 0",
            "notion_writes\": 0",
            "production_db_writes\": 0",
            "publication_actions\": 0",
            "pipeline_imported\": False",
            "--require-all-vendors",
            'kind == "page_fallback"',
            'startswith("structured_")',
        ),
        "smoke",
    )
    for forbidden in ("import pipeline", "import google.generativeai", "notion.pages", "NOTION_TOKEN"):
        if forbidden in smoke:
            errors.append(f"live_smoke_forbidden_surface:{forbidden}")

    live_workflow = texts[LIVE_WORKFLOW]
    errors += _require(
        live_workflow,
        (
            "workflow_dispatch:",
            "Run precision unit tests before network",
            "python -m unittest tests.test_run269_acquisition_precision -v",
            "python -m unittest tests.test_run269_vendor_current_state -v",
            "--require-all-vendors",
        ),
        "live_workflow",
    )
    for forbidden in ("GEMINI_API_KEY", "NOTION_TOKEN", "GH_PAT"):
        if forbidden in live_workflow:
            errors.append(f"live_workflow_forbidden_secret:{forbidden}")
    run_lines = "\n".join(line for line in live_workflow.splitlines() if line.lstrip().startswith("run:") or "python " in line)
    if "production_pipeline.py" in run_lines:
        errors.append("live_workflow_must_not_execute_production_pipeline")

    return list(dict.fromkeys(errors))


def main() -> int:
    errors = collect_errors(ROOT)
    if errors:
        print("ACQUISITION_PRECISION_GUARD=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("ACQUISITION_PRECISION_GUARD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
