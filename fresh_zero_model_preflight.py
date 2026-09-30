"""Measurement-only source preflight. Never scores, writes articles, or calls an LLM.

The live entrypoint uses the separate manual fresh-zero-model-preflight.yml
workflow. Its stand-alone bootstrap installs the same frozen Production runtime
and source-acquisition overlays without modifying production_pipeline.py or
initializing a model runtime, font downloader, Screening or Deep Dive.

Live mode still reads four public source endpoints and authoritative Notion.
It is NOT a network-free test or an eligible-article/quality certification.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from local_skills_daily_canary import STRATIFIED_SOURCES, _fresh_candidates

AUDIT_PATH = Path("article_audit/fresh_zero_model_preflight.json")
CONFIRM_VALUE = "RUN_READ_ONLY_PREFLIGHT"


def _minimal_acquisition_surface(pipeline: Any) -> SimpleNamespace:
    """Whitelist just acquisition and deduplication functions; no model methods."""
    names = (
        "fetch_github_trending", "fetch_hackernews_top", "fetch_arxiv_ai_ml",
        "fetch_producthunt_trending", "round_robin_candidates",
        "legal_safety_gate", "get_existing_repo_urls",
        "candidate_identity_urls", "_normalize_title_for_match",
        "GITHUB_FETCH_LIMIT", "HN_FETCH_LIMIT", "ARXIV_FETCH_LIMIT",
        "OFFICIAL_VENDOR_FETCH_LIMIT", "MAX_SCREENING_CANDIDATES",
    )
    required_functions = names[:9]
    for name in required_functions:
        if not callable(getattr(pipeline, name, None)):
            raise RuntimeError("Source preflight is missing required Production acquisition surface")
    return SimpleNamespace(**{
        name: getattr(pipeline, name)
        for name in names
        if hasattr(pipeline, name)
    })


def _summarize(acquisition: dict, *, provenance: str) -> dict:
    stages = acquisition.get("source_attrition")
    if not isinstance(stages, dict):
        raise RuntimeError("Source preflight is missing complete attrition diagnostics")
    required = (
        "collected_by_source", "round_robin_by_source", "legal_safe_by_source",
        "dedupe_excluded_by_source", "existing_notion_duplicate_by_source",
        "intra_run_duplicate_by_source", "observed_excluded_by_source",
        "fresh_by_source",
    )
    counts = {}
    for stage in required:
        row = stages.get(stage)
        if not isinstance(row, dict) or set(row) != STRATIFIED_SOURCES:
            raise RuntimeError("Source preflight is missing one of the four required sources")
        if any(type(v) is not int or v < 0 for v in row.values()):
            raise RuntimeError("Source preflight received invalid aggregate counts")
        counts[stage] = dict(row)
    for source in sorted(STRATIFIED_SOURCES):
        collected = counts["collected_by_source"][source]
        in_rotation = counts["round_robin_by_source"][source]
        safe = counts["legal_safe_by_source"][source]
        duplicates = counts["dedupe_excluded_by_source"][source]
        observed = counts["observed_excluded_by_source"][source]
        fresh = counts["fresh_by_source"][source]
        if not (collected >= in_rotation >= safe >= duplicates + observed + fresh):
            raise RuntimeError("Source preflight aggregate counts do not reconcile")
    return {
        "mode": "source_preflight",
        "provenance": provenance,
        "quality_measured": False,
        "model_provider_calls": 0,
        "note_or_notion_article_writes": 0,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_status": {
            source: (
                "NO_FRESH_CANDIDATES" if counts["fresh_by_source"][source] == 0
                else "FRESH_PRE_SCREEN_ONLY"
            )
            for source in sorted(STRATIFIED_SOURCES)
        },
        "source_attrition": counts,
        "production_fetch_limits": acquisition.get("production_fetch_limits", {}),
        "production_max_screening": acquisition.get("production_max_screening"),
        "gate_result": "NOT_MEASURED",
    }


def run_live(pipeline: Any, *, audit_path: Path = AUDIT_PATH) -> dict:
    """Explicit credentialed reads only. No Gemini credentials permitted."""
    if os.environ.get("FRESH_SOURCE_PREFLIGHT_CONFIRM") != CONFIRM_VALUE:
        raise RuntimeError("Manual source-preflight confirmation required")
    if os.environ.get("AIIF_LOCAL_SKILLS_CANARY_SOURCE"):
        raise RuntimeError("All four sources must be measured together in preflight")
    if os.environ.get("GEMINI_API_KEY") or getattr(pipeline, "GEMINI_API_KEY", None):
        raise RuntimeError("Source preflight refuses all Gemini credentials")
    if not getattr(pipeline, "GH_PAT", None):
        raise RuntimeError("Authoritative GitHub source credentials are required")
    if not getattr(pipeline, "NOTION_API_KEY", None) or not (
        getattr(pipeline, "NOTION_DATA_SOURCE_ID", None)
        or getattr(pipeline, "NOTION_DATABASE_ID", None)
    ):
        raise RuntimeError("Authoritative Notion dedupe credentials are required")
    # This restricted facade has no screening, calibration, model or persistence
    # functions. It uses the current Production source and identity callables.
    facade = _minimal_acquisition_surface(pipeline)
    requested_trial = os.environ.get("FRESH_SUPPLY_TRIAL_PROTOCOL", "")
    trial_metrics: dict = {}
    if requested_trial:
        from fresh_candidate_supply_experiment import PROTOCOL_ID, make_fetcher
        if requested_trial != PROTOCOL_ID or (
            os.environ.get("FRESH_SUPPLY_TRIAL_APPROVAL") != "ALLOW_3_GITHUB_READS"
        ):
            raise RuntimeError("Source-supply experiment requires exact preregistered approval")
        if not callable(getattr(pipeline, "normalize_item", None)) or not hasattr(pipeline, "requests"):
            raise RuntimeError("Experimental source transport unavailable")
        facade.fetch_github_trending = make_fetcher(pipeline, capture=trial_metrics)
    elif os.environ.get("FRESH_SUPPLY_TRIAL_APPROVAL"):
        raise RuntimeError("Experimental approval cannot leak into baseline preflight")

    _repos, acquisition = _fresh_candidates(facade)
    provenance = (
        "EXPERIMENTAL_GITHUB_SOURCE_SUPPLY_NOT_PRODUCTION"
        if requested_trial else "LIVE_SOURCE_AND_NOTION_READS"
    )
    result = _summarize(acquisition, provenance=provenance)
    if requested_trial:
        result["experimental_github"] = trial_metrics
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    """Stand-alone manual bootstrap; leave validated Production orchestration intact."""
    if os.environ.get("FRESH_SOURCE_PREFLIGHT_CONFIRM") != CONFIRM_VALUE:
        raise RuntimeError("Explicit manual source preflight confirmation is required")
    if os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("Source preflight cannot receive Gemini credentials")

    import pipeline
    from source_normalization import install as install_source_normalization
    from production_pipeline import install_runtime_layers
    from run268_business_source_strategy import install as install_run268
    from run269_business_source_precision import install as install_run269

    install_source_normalization(pipeline)
    install_runtime_layers(pipeline)
    install_run268(pipeline)
    install_run269(pipeline)
    if not getattr(pipeline, "_RUN268_BUSINESS_SOURCE_STRATEGY_INSTALLED", False):
        raise RuntimeError("Production four-source acquisition overlay did not install")
    if not getattr(pipeline, "_RUN269_BUSINESS_SOURCE_PRECISION_INSTALLED", False):
        raise RuntimeError("Current Production source precision overlay did not install")
    report = run_live(pipeline)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
