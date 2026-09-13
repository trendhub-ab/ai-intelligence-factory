#!/usr/bin/env python3
"""Fail closed when active acquisition-source architecture drifts.

This guard protects executable source strategy only. Historical Run labels, canonical-spec
wording, product-copy prose, and reference-document text are intentionally outside CI.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ACQUISITION = "business_source_acquisition.py"
LAYER = "run268_business_source_strategy.py"
ENTRYPOINT = "production_pipeline.py"

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
    acquisition = _read(root, ACQUISITION)
    layer = _read(root, LAYER)
    entrypoint = _read(root, ENTRYPOINT)
    errors: list[str] = []

    for name, text in ((ACQUISITION, acquisition), (LAYER, layer), (ENTRYPOINT, entrypoint)):
        try:
            ast.parse(text, filename=name)
        except SyntaxError as exc:
            errors.append(f"python_syntax_error:{name}:{exc.lineno}:{exc.msg}")

    errors += _require(
        acquisition,
        (
            '"GitHub": "implementation_momentum"',
            '"ArXiv": "frontier_research"',
            '"HackerNews": "market_engineer_reaction"',
            '"OfficialVendor": "commercial_primary_source"',
            'HN_ALGOLIA_ENDPOINT = "https://hn.algolia.com/api/v1/search_by_date"',
            "fetch_official_vendor_updates",
            "fetch_hackernews_ai_reactions",
            "vendor_region",
        ),
        "acquisition",
    )
    for vendor in REQUIRED_VENDORS:
        if f'"vendor": "{vendor}"' not in acquisition:
            errors.append(f"official_vendor_missing:{vendor}")

    for forbidden in (
        "hacker-news.firebaseio.com/v0/topstories.json",
        "api.producthunt.com",
        "PRODUCTHUNT_DEVELOPER_TOKEN",
    ):
        if forbidden in acquisition:
            errors.append(f"acquisition_forbidden_transport:{forbidden}")

    errors += _require(
        layer,
        (
            'ACTIVE_SOURCE_ORDER = ("GitHub", "HackerNews", "ArXiv", "OfficialVendor")',
            'p.fetch_producthunt_trending = fetch_official_vendor_run268',
            'p.fetch_hackernews_top = fetch_hackernews_run268',
            'source_groups.pop("ProductHunt")',
            'source_groups.setdefault("OfficialVendor", legacy_items)',
        ),
        "source_layer",
    )
    active_line = next((line for line in layer.splitlines() if line.startswith("ACTIVE_SOURCE_ORDER =")), "")
    if "ProductHunt" in active_line:
        errors.append("producthunt_present_in_active_source_order")
    if "api.producthunt.com" in layer:
        errors.append("source_layer_must_not_call_producthunt_graphql")

    errors += _require(
        entrypoint,
        (
            "from run268_business_source_strategy import install as install_run268_business_source_strategy",
            "install_runtime_layers(pipeline)",
            "install_run268_business_source_strategy(pipeline)",
        ),
        "production_entrypoint",
    )
    if all(marker in entrypoint for marker in ("install_runtime_layers(pipeline)", "install_run268_business_source_strategy(pipeline)")):
        if entrypoint.index("install_runtime_layers(pipeline)") > entrypoint.index("install_run268_business_source_strategy(pipeline)"):
            errors.append("source_strategy_must_install_after_runtime_layers")

    return list(dict.fromkeys(errors))


def main() -> int:
    errors = collect_errors(ROOT)
    if errors:
        print("SOURCE_ACQUISITION_STRATEGY_GUARD=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("SOURCE_ACQUISITION_STRATEGY_GUARD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
