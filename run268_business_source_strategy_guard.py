#!/usr/bin/env python3
"""Run268 zero-network fail-closed source-strategy guard.

Run268 remains the authority for the four-source acquisition architecture. Later runs may
change paid-product framing without weakening the Run268 source invariants.
"""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ACQUISITION = "business_source_acquisition.py"
LAYER = "run268_business_source_strategy.py"
ENTRYPOINT = "production_pipeline.py"
PRODUCT = "PAID_PRODUCT_CONTRACT.md"
SPEC = "AI_Intelligence_Factory_最終仕様書.md"
WORKFLOW = ".github/workflows/repository-falsification.yml"
REFERENCE = "docs/reference/RUN268_BUSINESS_SOURCE_STRATEGY.md"

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


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _require(text: str, markers: tuple[str, ...], prefix: str) -> list[str]:
    return [f"{prefix}_missing:{marker}" for marker in markers if marker not in text]


def collect_errors(root: Path = ROOT) -> list[str]:
    global ROOT
    original_root = ROOT
    ROOT = root
    try:
        acquisition = _read(ACQUISITION)
        layer = _read(LAYER)
        entrypoint = _read(ENTRYPOINT)
        product = _read(PRODUCT)
        spec = _read(SPEC)
        workflow = _read(WORKFLOW)
        reference = _read(REFERENCE)
    finally:
        ROOT = original_root

    errors: list[str] = []

    for name, text in ((ACQUISITION, acquisition), (LAYER, layer)):
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
    if "hacker-news.firebaseio.com/v0/topstories.json" in acquisition:
        errors.append("run268_hn_must_not_use_firebase_topstories")
    for forbidden in ("api.producthunt.com", "PRODUCTHUNT_DEVELOPER_TOKEN"):
        if forbidden in acquisition:
            errors.append(f"run268_acquisition_contains_producthunt_transport:{forbidden}")

    errors += _require(
        layer,
        (
            'ACTIVE_SOURCE_ORDER = ("GitHub", "HackerNews", "ArXiv", "OfficialVendor")',
            'p.fetch_producthunt_trending = fetch_official_vendor_run268',
            'p.fetch_hackernews_top = fetch_hackernews_run268',
            'p.PRODUCTHUNT_DEVELOPER_TOKEN = "RUN268_OFFICIAL_VENDOR_NO_TOKEN_REQUIRED"',
            'source_groups.pop("ProductHunt")',
            'source_groups.setdefault("OfficialVendor", legacy_items)',
        ),
        "layer",
    )
    active_line = next((line for line in layer.splitlines() if line.startswith("ACTIVE_SOURCE_ORDER =")), "")
    if "ProductHunt" in active_line:
        errors.append("producthunt_present_in_active_source_order")
    if "api.producthunt.com" in layer:
        errors.append("run268_layer_must_not_call_producthunt_graphql")

    errors += _require(
        entrypoint,
        (
            "from run268_business_source_strategy import install as install_run268_business_source_strategy",
            "install_runtime_layers(pipeline)",
            "install_run268_business_source_strategy(pipeline)",
        ),
        "production_entrypoint",
    )
    if "install_runtime_layers(pipeline)" in entrypoint and "install_run268_business_source_strategy(pipeline)" in entrypoint:
        if entrypoint.index("install_runtime_layers(pipeline)") > entrypoint.index("install_run268_business_source_strategy(pipeline)"):
            errors.append("run268_must_install_after_historical_runtime_layers")

    # Run268 remains the source-architecture authority. Run307 intentionally supersedes the
    # Proposal-First product framing while preserving the same acquisition architecture.
    errors += _require(
        product,
        (
            "Run307 current product contract",
            "Generic Use-Decision Intelligence",
            "GitHub — 実装動向",
            "ArXiv — 技術の先行動向",
            "HackerNews — 市場・エンジニア反応",
            "OfficialVendor — 商用利用に直結する一次情報",
            "Product HuntはRun268からProductionのactive Sourceではない",
            "中国主要",
            "Run268 — Proposal-First ICP / Four-Source Intelligence",
        ),
        "paid_product_contract",
    )

    errors += _require(
        spec,
        (
            "Business / Source Strategy Baseline: **Run268",
            "Paid Product Messaging Baseline: **Run307",
            "GitHub = 実装動向",
            "ArXiv = 技術の先行動向",
            "HackerNews = 市場・エンジニア反応",
            "OfficialVendor = 商用利用に直結する一次情報",
            "Product HuntはRun268からProductionのactive Sourceではない",
            "Alibaba Qwen",
            "Tencent Hunyuan",
            "docs/reference/RUN268_BUSINESS_SOURCE_STRATEGY.md",
        ),
        "canonical_spec",
    )

    errors += _require(
        workflow,
        (
            "Enforce Run268 business/source strategy contract",
            "python run268_business_source_strategy_guard.py",
            "tests.test_run268_business_source_strategy_guard",
            "tests.test_run268_business_source_strategy",
        ),
        "repository_falsification_workflow",
    )
    if "falsify-all-tracked-surfaces:" not in workflow:
        errors.append("required_falsification_context_name_changed")

    errors += _require(
        reference,
        (
            "# Run268 — Proposal-First / Four-Source Intelligence",
            "Product Hunt retirement",
            "Alibaba Qwen",
            "Tencent Hunyuan",
            "新しい有料API・API keyを追加しない",
        ),
        "run268_reference",
    )

    return list(dict.fromkeys(errors))


def main() -> int:
    errors = collect_errors(ROOT)
    if errors:
        print("RUN268_BUSINESS_SOURCE_STRATEGY_GUARD=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("RUN268_BUSINESS_SOURCE_STRATEGY_GUARD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
