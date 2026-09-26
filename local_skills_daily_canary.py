"""Fresh Daily acquisition canary for the frozen Local Skills publication compiler.

The lane reuses current Production acquisition, dedupe, legal, Screening,
Calibration, Evidence and Gate functions, but intentionally does not persist
Stock/article state or dispatch note publication. Production-style pre-Deep-Dive
backfill is allowed when a candidate fails Evidence/Source preconditions, but the
measurement permits at most one actual Deep Dive provider attempt. Its generated
article surface is then discarded and Local Skills is measured through unchanged
Gates.

Candidates already observed by a Local Skills canary are excluded from later
fresh measurements once their result has informed adapter/canary development.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

AUDIT_PATH = Path("article_audit/local_skills_daily_canary.json")
FETCH_PER_SOURCE = 20
MAX_SCREENING = 60

# Every record observed by a Local Skills canary is excluded once its result has
# informed validation or repair. Runs 36207549802 / 36208127057 informed canary
# orchestration. The later PASS article and Jevmem FAIL are also now observed:
# Jevmem directly informed the evidence/accessibility repair and may be used only
# as contaminated repair regression. Build Plugins validated the repaired v4 stack,
# then informed v4.1 hardening. "Yes, Claude can do nine loops" was the first fresh
# all-Gate PASS for v4.1. The later DeepSeek biopharma article exposed a remaining
# non-engineer accessibility defect and is contaminated repair evidence as well.
# The later Cockpit / Show HN article exposed discovery-label and reader-bridge
# weaknesses and is contaminated repair evidence as well. The v4.3 fresh ArXiv
# holdout then passed all unchanged Gates and now advances the candidate to broader
# validation. All observed records are excluded from future fresh claims.
OBSERVED_CANARY_NAMES = frozenset({
    "LLM Agents Can Easily Tamper With Their Own Traces",
    "U.S. appeals court upholds designation of Anthropic as supply chain risk",
    "My coding agent pushed a commit deleting every file on main",
    "Jevmem – automatic project memory for Claude Code, built on Jev",
    "Build Plugins for Claude",
    "Yes, Claude can do nine loops",
    "DeepSeek beats GPT-6 Sol in autonomous drug development",
    "Show HN: I couldn't deal with another Claude Code tab",
    "Revelations of dozens more platforms hit by OpenAI agents",
    "RAPID: Robot Agentic Programming from Demonstrations",
    "Minimally Invasive Steering of Language Models",
    "PoEM: Predicting RL Outcomes from Existing Policies",
    "OpenAI says agents leaked 53 images from ChatGPT users",
    "Coding Agents for Generalized Task and Motion Planning Problems",
    "AD-WM: Action-Discriminative World Models for Counterfactual Model Predictive Control",
    "The same bug fix costs 0.4¢ or $2, depending on which coding agent you ask",
    "Requirement-Bound Verified Commissioning: A Frozen Four-Billion-Parameter Local Model as a Candidate Generator under an External Acceptance Layer with Verification and Release Authority",
    "Temporal Gradient Inversion for Private Trajectory Reconstruction in Embodied Reinforcement Learning",
    "Self-hosting DeepSeek V4 for a software engineering org",
    "TrackEverything: Long Horizon Dense Tracking via De-Duplicating 3D Scene Representations",
    "Rolling-WAM: World Action Models with Rolling Imagination",
    "The Advisory Group on Mathematics and Artificial Intelligence",
    "To Trust or Not to Trust: Retrieval-Augmented Fact Checking in Speech",
})
OBSERVED_CANARY_URL_MARKERS = frozenset({
    "2609.30266",
    "dev.karakun.com/2026/08/28/coding-agent-pushed-deletion-to-main.html",
    "Avinash-jetwani/jevmem",
    "claude.com/blog/build-plugins-for-claude",
    "anthropic.com/research/yes-claude-can-do-nine-loops",
    "eval.raycaster.ai/benchmarks/biopharma-bench",
    "aidash.dev",
    "2609.30217",
    "abc.net.au/news/2026-09-26/openai-review-rogue-agents-australia-medicare-hack/107199074",
    "2609.30249",
    "2609.30226",
    "theguardian.com/technology/2026/sep/25/openai-agents-leaked-53-images-chatgpt",
    "2609.30233",
    "2609.30264",
    "ariwilson.com/writing/bakeoff-results",
    "2609.30219",
    "2609.30258",
    "parity.io/blog/self-hosted-ai-software-engineering",
    "2609.30222",
    "2609.30247",
    "terrytao.wordpress.com/2026/09/21/advisory-group-on-mathematics-and-artificial-intelligence",
    "2609.30227",
})


def _write(result: dict[str, Any]) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _already_observed(repo: dict) -> bool:
    name = str(repo.get("nameWithOwner") or repo.get("name") or "").strip()
    if name in OBSERVED_CANARY_NAMES:
        return True
    values = [
        str(repo.get("url") or ""),
        str(repo.get("primaryUrl") or ""),
        str(repo.get("canonical_entity_id") or ""),
    ]
    details = repo.get("sourceDetails") or {}
    if isinstance(details, dict):
        values.extend(str(value or "") for value in details.values() if isinstance(value, str))
    joined = "\n".join(values)
    return any(marker in joined for marker in OBSERVED_CANARY_URL_MARKERS)


def _deep_dive_attempt_count(pipeline: Any) -> int:
    """Count actual article-analysis provider sends already attempted this run."""
    audit = getattr(pipeline, "GEMINI_USAGE_AUDIT", None)
    records = list(getattr(audit, "records", []) or [])
    return sum(1 for row in records if str(row.get("kind") or "") == "deep_dive")


def _fresh_candidates(pipeline: Any) -> tuple[list[dict], dict[str, int]]:
    groups = {
        "GitHub": pipeline.fetch_github_trending(FETCH_PER_SOURCE),
        "HackerNews": pipeline.fetch_hackernews_top(FETCH_PER_SOURCE),
        "ArXiv": pipeline.fetch_arxiv_ai_ml(FETCH_PER_SOURCE),
        # Run268 rewrites the retired Product Hunt call slot to OfficialVendor.
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
    observed_excluded = 0
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
        if _already_observed(repo):
            observed_excluded += 1
            continue
        local_identity_urls.update(identity_urls)
        if not identity_urls:
            local_fallback_keys.add(fallback_key)
        deduped.append(repo)

    return deduped[:MAX_SCREENING], {
        "collected": len(repos),
        "safe": len(safe),
        "observed_canary_excluded": observed_excluded,
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
        "candidate_attempts": [],
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

        # Measure the frozen Local Skills manuscript itself: allow Production's
        # normal evidence/source backfill before the provider send, but permit at
        # most one actual Deep Dive. No Gemini quality rewrite or deterministic
        # publication rescue is allowed after that send.
        pipeline.MAX_QUALITY_RETRIES = 0
        pipeline.ENABLE_DETERMINISTIC_PUBLICATION_RESCUE = False

        for rank, candidate in enumerate(candidates, start=1):
            repo = candidate["repo"]
            if _already_observed(repo):
                raise RuntimeError("Previously observed Local Skills canary candidate reached selection")

            name = str(repo.get("nameWithOwner") or "")
            source = str(repo.get("source") or "")
            score = int(candidate.get("score") or 0)
            setattr(pipeline, "_LOCAL_SKILLS_CANARY_LAST_COMPILE", {})
            setattr(pipeline, "_LOCAL_SKILLS_CANARY_LAST_RESULT", {})

            before_deep_dive = _deep_dive_attempt_count(pipeline)
            report = pipeline.generate_intelligence_report(
                repo,
                notion_page_id=None,
                screening_score=candidate.get("score"),
                screening_reason=candidate.get("reason", ""),
                persist_results=False,
                candidate_rank=rank,
                candidate_origin="local_skills_canary_validation",
                attribution_context=candidate,
            )
            after_deep_dive = _deep_dive_attempt_count(pipeline)
            provider_send_attempted = after_deep_dive > before_deep_dive

            compile_meta = dict(
                getattr(pipeline, "_LOCAL_SKILLS_CANARY_LAST_COMPILE", {}) or {}
            )
            gates = dict(
                getattr(pipeline, "_LOCAL_SKILLS_CANARY_LAST_RESULT", {}) or {}
            )
            attempt = {
                "rank": rank,
                "name": name,
                "source": source,
                "screening_score": score,
                "deep_dive_provider_attempted": provider_send_attempted,
                "compiler_reached": bool(compile_meta),
                "gates_measured": bool(gates),
            }

            if compile_meta and gates:
                result.update({
                    "selected": name,
                    "source": source,
                    "screening_score": score,
                    "compile": compile_meta,
                    "gates": gates,
                })
                attempt["disposition"] = "measured"
                result["candidate_attempts"].append(attempt)

                if isinstance(report, tuple) and len(report) == 2:
                    result["outcome"] = str(report[1])
                elif report:
                    result["outcome"] = "accepted"
                else:
                    result["outcome"] = "rejected"

                if result["outcome"] not in {"accepted", "rejected"}:
                    raise RuntimeError("Local Skills canary produced an invalid measurement outcome")
                return result

            if not provider_send_attempted:
                # Production rejected/backfilled the candidate before any Deep Dive
                # send (e.g. Evidence Insufficient or Source Integrity). Continue
                # without spending the single article-analysis provider attempt.
                attempt["disposition"] = "pre_deep_dive_backfill"
                result["candidate_attempts"].append(attempt)
                continue

            # Once one article-analysis provider call has happened, never try a
            # second candidate. This keeps the fresh measurement single-send and
            # prevents integration bugs from multiplying API cost.
            attempt["disposition"] = "deep_dive_without_measurement"
            result["candidate_attempts"].append(attempt)
            result.update({
                "selected": name,
                "source": source,
                "screening_score": score,
            })
            raise RuntimeError(
                "Local Skills canary spent its single Deep Dive but did not reach compiler/Gate measurement"
            )

        raise RuntimeError(
            "No ranked fresh candidate reached an evidence-sufficient Deep Dive before backfill candidates were exhausted"
        )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        pipeline.MAX_QUALITY_RETRIES = old_retries
        pipeline.ENABLE_DETERMINISTIC_PUBLICATION_RESCUE = old_rescue
        _write(result)
        pipeline.logger.info("[LOCAL SKILLS DAILY CANARY] %s", result)
