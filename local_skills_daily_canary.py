"""Fresh Daily acquisition canary for the frozen Local Skills publication compiler.

The lane reuses current Production acquisition, dedupe, legal, Screening,
Calibration, Evidence and Gate functions, but intentionally does not persist
Stock/article state or dispatch note publication.  Exactly one fresh candidate
is sent through Deep Dive structured analysis, then its provider-generated
article body is replaced by Local Skills before the unchanged Gates run.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

AUDIT_PATH = Path("article_audit/local_skills_daily_canary.json")
FETCH_PER_SOURCE = 20
MAX_SCREENING = 60


def _write(result: dict[str, Any]) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _fresh_candidates(pipeline: Any) -> tuple[list[dict], dict[str, int]]:
    groups = {
        "GitHub": pipeline.fetch_github_trending(FETCH_PER_SOURCE),
        "HackerNews": pipeline.fetch_hackernews_top(FETCH_PER_SOURCE),
        "ArXiv": pipeline.fetch_arxiv_ai_ml(FETCH_PER_SOURCE),
        "ProductHunt": pipeline.fetch_producthunt_trending(FETCH_PER_SOURCE),
    }
    repos = pipeline.round_robin_candidates(groups, MAX_SCREENING)

    safe: list[dict] = []
    for repo in repos:
        ok, _reason = pipeline.legal_safety_gate(repo)
        if ok:
            safe.append(repo)

    existing_urls = pipeline.get_existing_repo_urls()
    if existing_urls is None:
        raise RuntimeError("Local Skills canary cannot verify Notion dedupe state")

    deduped: list[dict] = []
    local_identity_urls: set[str] = set()
    local_fallback_keys: set[str] = set()
    for repo in safe:
        identity_urls = pipeline.candidate_identity_urls(repo)
        title_key = pipeline._normalize_title_for_match(repo.get("nameWithOwner", ""))
        fallback_key = f"{repo.get('source', '')}:{title_key}"
        duplicate = (
            bool(identity_urls & existing_urls)
            or bool(identity_urls & local_identity_urls)
            or (not identity_urls and fallback_key in local_fallback_keys)
        )
        if duplicate:
            continue
        local_identity_urls.update(identity_urls)
        if not identity_urls:
            local_fallback_keys.add(fallback_key)
        deduped.append(repo)

    return deduped[:MAX_SCREENING], {
        "collected": len(repos),
        "safe": len(safe),
        "fresh_after_dedupe": len(deduped),
    }


def run(pipeline: Any) -> dict[str, Any]:
    os.environ["AIIF_LOCAL_SKILLS_CANARY"] = "true"
    pipeline.initialize_runtime()
    pipeline.reset_article_style_memory()
    setattr(pipeline, "_LOCAL_SKILLS_CANARY_LAST_COMPILE", {})
    setattr(pipeline, "_LOCAL_SKILLS_CANARY_LAST_RESULT", {})

    result: dict[str, Any] = {
        "mode": "local_skills_canary_validation",
        "fresh_holdout": True,
        "persist_results": False,
        "local_skills_additional_provider_calls": 0,
        "screening_candidates": 0,
        "selected": "",
        "source": "",
        "screening_score": 0,
        "outcome": "",
        "compile": {},
        "gates": {},
        "error": "",
    }

    old_retries = pipeline.MAX_QUALITY_RETRIES
    old_rescue = pipeline.ENABLE_DETERMINISTIC_PUBLICATION_RESCUE
    try:
        repos, acquisition = _fresh_candidates(pipeline)
        result["acquisition"] = acquisition
        if not repos:
            raise RuntimeError("No fresh Daily candidate remained after Production dedupe")

        screening_candidates = [
            {"screening_id": f"LSC{idx:04d}", "repo": repo}
            for idx, repo in enumerate(repos, start=1)
        ]
        screened, screening_calls = pipeline.screen_candidates_in_batches(screening_candidates)
        screened, calibration_calls = pipeline.calibrate_candidates(screened)
        result["screening_candidates"] = len(screened)
        result["screening_api_calls"] = int(screening_calls)
        result["calibration_api_calls"] = int(calibration_calls)

        # Reuse the current Production portfolio ordering without writing Stock.
        for item in screened:
            item["notion_page_id"] = (
                "LOCAL_SKILLS_CANARY_NO_WRITE"
                if item.get("score", 0) >= pipeline.NOTION_SAVE_THRESHOLD_SCORE
                else None
            )
        candidates = pipeline._select_stocked_deep_dive_candidates(screened)
        if not candidates:
            raise RuntimeError("No fresh candidate met the current Production Deep Dive threshold")

        candidate = candidates[0]
        repo = candidate["repo"]
        result.update({
            "selected": str(repo.get("nameWithOwner") or ""),
            "source": str(repo.get("source") or ""),
            "screening_score": int(candidate.get("score") or 0),
        })

        # Measure the frozen Local Skills manuscript itself: one Deep Dive structured
        # response, no Gemini quality rewrite, no deterministic rescue after Gate failure.
        pipeline.MAX_QUALITY_RETRIES = 0
        pipeline.ENABLE_DETERMINISTIC_PUBLICATION_RESCUE = False

        report = pipeline.generate_intelligence_report(
            repo,
            notion_page_id=None,
            screening_score=candidate.get("score"),
            screening_reason=candidate.get("reason", ""),
            persist_results=False,
            candidate_rank=1,
            candidate_origin="local_skills_canary_validation",
            attribution_context=candidate,
        )

        result["compile"] = dict(
            getattr(pipeline, "_LOCAL_SKILLS_CANARY_LAST_COMPILE", {}) or {}
        )
        result["gates"] = dict(
            getattr(pipeline, "_LOCAL_SKILLS_CANARY_LAST_RESULT", {}) or {}
        )
        if not result["compile"] or not result["gates"]:
            raise RuntimeError("Local Skills canary did not reach the frozen compiler and Gate measurement")

        if isinstance(report, tuple) and len(report) == 2:
            result["outcome"] = str(report[1])
        elif report:
            result["outcome"] = "accepted"
        else:
            result["outcome"] = "rejected"

        if result["outcome"] not in {"accepted", "rejected"}:
            raise RuntimeError("Local Skills canary produced an invalid measurement outcome")
        return result
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        pipeline.MAX_QUALITY_RETRIES = old_retries
        pipeline.ENABLE_DETERMINISTIC_PUBLICATION_RESCUE = old_rescue
        _write(result)
        pipeline.logger.info("[LOCAL SKILLS DAILY CANARY] %s", result)
