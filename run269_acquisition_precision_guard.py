#!/usr/bin/env python3
"""Run269 zero-network fail-closed live acquisition precision guard."""
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
FALSIFICATION_WORKFLOW = ".github/workflows/repository-falsification.yml"
SPEC = "AI_Intelligence_Factory_最終仕様書.md"
REFERENCE = "docs/reference/RUN269_LIVE_ACQUISITION_PRECISION.md"

REQUIRED_VENDORS = (
    "OpenAI",
    "Anthropic",
    "Google Gemini",
    "Alibaba Qwen",
    "DeepSeek",
    "ByteDance Doubao/Seed",
    "Moonshot AI Kimi",
    "Zhipu AI GLM",
    "MiniMax",
    "Baidu ERNIE",
    "Tencent Hunyuan",
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
        FALSIFICATION_WORKFLOW: _read(root, FALSIFICATION_WORKFLOW),
        SPEC: _read(root, SPEC),
        REFERENCE: _read(root, REFERENCE),
    }
    errors: list[str] = []

    for filename in (PRECISION, CURRENT_STATE, LAYER, SMOKE):
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
            "*run268.OFFICIAL_VENDOR_REGISTRY[:5]",
            "run268.OFFICIAL_VENDOR_REGISTRY[6]",
            "run268.OFFICIAL_VENDOR_REGISTRY[7]",
            "run268.OFFICIAL_VENDOR_REGISTRY[9]",
            '"vendor": "ByteDance Doubao/Seed"',
            '"vendor": "MiniMax"',
            '"vendor": "Tencent Hunyuan"',
            "HN_LOOKBACK_DAYS = 30",
            'restrictSearchableAttributes": "title"',
            '"numericFilters": f"created_at_i>{cutoff}"',
            "def _query_matches_title",
            "not _query_matches_title(title, query)",
            '"Qwen"',
            '"DeepSeek"',
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
        errors.append("run269_hn_must_not_use_firebase_topstories")

    # Run268 remains the registry architecture authority. Run269 intentionally inherits
    # unchanged vendors by index and only overrides the surfaces proven imprecise by
    # live smoke. Validate the effective contract across base + overlay, not by forcing
    # all eleven vendor names to be duplicated in the precision module.
    effective_registry_contract = (
        texts[BASE_ACQUISITION] + "\n" + precision + "\n" + texts[CURRENT_STATE]
    )
    for vendor in REQUIRED_VENDORS:
        if vendor not in effective_registry_contract:
            errors.append(f"run269_vendor_missing:{vendor}")

    current_state = texts[CURRENT_STATE]
    errors += _require(
        current_state,
        (
            'row["vendor"] == "ByteDance Doubao/Seed"',
            "1799865?lang=zh",
            '"current_state_page": True',
            '"structured_current_state"',
            "リリースイベントではなく",
            "最近更新",
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
            'p._RUN269_BUSINESS_SOURCE_PRECISION_INSTALLED = True',
            'required = ("normalize_item", "requests")',
        ),
        "layer",
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
        "entrypoint",
    )
    if all(marker in entrypoint for marker in ("install_run268_business_source_strategy(pipeline)", "install_run269_business_source_precision(pipeline)")):
        if entrypoint.index("install_run268_business_source_strategy(pipeline)") > entrypoint.index("install_run269_business_source_precision(pipeline)"):
            errors.append("run269_must_install_after_run268")

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
            "actions/upload-artifact@v7",
            "retention-days: 14",
        ),
        "live_workflow",
    )
    for forbidden in ("GEMINI_API_KEY", "NOTION_TOKEN", "GH_PAT", "production_pipeline.py"):
        if forbidden == "production_pipeline.py":
            run_lines = "\n".join(line for line in live_workflow.splitlines() if line.lstrip().startswith("run:") or "python " in line)
            if forbidden in run_lines:
                errors.append("live_workflow_must_not_execute_production_pipeline")
        elif forbidden in live_workflow:
            errors.append(f"live_workflow_forbidden_secret:{forbidden}")

    falsification = texts[FALSIFICATION_WORKFLOW]
    errors += _require(
        falsification,
        (
            "Enforce Run269 live acquisition precision contract",
            "python run269_acquisition_precision_guard.py",
            "tests.test_run269_acquisition_precision_guard",
            "tests.test_run269_acquisition_precision",
            "tests.test_run269_vendor_current_state",
        ),
        "repository_falsification_workflow",
    )
    if "falsify-all-tracked-surfaces:" not in falsification:
        errors.append("required_falsification_context_name_changed")

    spec = texts[SPEC]
    errors += _require(
        spec,
        (
            "Acquisition Precision Baseline: **Run269",
            "HackerNews Precision — Run269",
            "exact token / exact phrase",
            "30日",
            "structured_current_state",
            "page_fallback",
            "docs/reference/RUN269_LIVE_ACQUISITION_PRECISION.md",
        ),
        "canonical_spec",
    )

    reference = texts[REFERENCE]
    errors += _require(
        reference,
        (
            "# Run269 — Live Acquisition Precision / East-West Vendor Smoke",
            "Qwen -> jQuery",
            "structured_current_state",
            "11/11",
            "Gemini/model calls = 0",
        ),
        "run269_reference",
    )

    return list(dict.fromkeys(errors))


def main() -> int:
    errors = collect_errors(ROOT)
    if errors:
        print("RUN269_ACQUISITION_PRECISION_GUARD=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("RUN269_ACQUISITION_PRECISION_GUARD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
