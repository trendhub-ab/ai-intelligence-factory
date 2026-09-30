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
FALLBACK_FETCH_PER_SOURCE = 20
FALLBACK_MAX_SCREENING = 60
STRATIFIED_SOURCES = frozenset({"GitHub", "HackerNews", "ArXiv", "OfficialVendor"})

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
    "Anthropic's AI biolab finds 'CRISPR-like' DNA in viruses. What's next?",
    "DeepSeek Elastic Compute:A Sandbox Infrastructure for Effective Agentic Training",
    "Automating eval design and hillclimbing with Claude",
    "Show HN: Agentcap – eBPF exporter for AI-agent activity to Grafana",
    "Claude Sonnet 5.5 for code review: More catches than Sonnet 5, in half the time",
    "An AI agent escaped Google\'s kvmCTF sandbox",
    "Routing LLM traffic across inference providers with TCP-style congestion control",
    "OpenAI Releases Sign in with ChatGPT DevKit",
    "Are new OpenAI models getting better for coding?",
    "An LLM Workflow That Reproduces, Improves, Extends Published Economics Research",
    "Inspect: An open-source framework for large language model evaluations",
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
    "d41586-026-03039-6",
    "2609.22978",
    "claude.dev/blog/automating-eval-design-and-hillclimbing",
    "github.com/yeet-src/agentcap",
    "coderabbit.ai/blog/sonnet-5-5-model-review",
    "pwn.ai/blog/kvmescape",
    "getunblocked.com/blog/adaptive-routing-inference-providers",
    "github.com/openai/sign-in-with-chatgpt-devkit",
    "developer.microsoft.com/blog/what-ai-benchmarks-are-not-telling-you",
    "nber.org/papers/w35782",
    "inspect.aisi.org.uk",
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


def _production_acquisition_limits(pipeline: Any) -> dict[str, int]:
    """Mirror current Production acquisition breadth without changing quality policy."""
    return {
        "GitHub": int(getattr(pipeline, "GITHUB_FETCH_LIMIT", FALLBACK_FETCH_PER_SOURCE)),
        "HackerNews": int(getattr(pipeline, "HN_FETCH_LIMIT", FALLBACK_FETCH_PER_SOURCE)),
        "ArXiv": int(getattr(pipeline, "ARXIV_FETCH_LIMIT", FALLBACK_FETCH_PER_SOURCE)),
        "OfficialVendor": int(getattr(pipeline, "OFFICIAL_VENDOR_FETCH_LIMIT", FALLBACK_FETCH_PER_SOURCE)),
        "max_screening": int(getattr(pipeline, "MAX_SCREENING_CANDIDATES", FALLBACK_MAX_SCREENING)),
    }


def _validated_requested_source() -> str:
    """An optional exact, fail-closed source restriction for cross-source Fresh tests."""
    source = os.environ.get("AIIF_LOCAL_SKILLS_CANARY_SOURCE", "")
    if source and source not in STRATIFIED_SOURCES:
        raise RuntimeError("Invalid source-stratified Fresh target")
    return source


def _restrict_source(repos: list[dict], source: str) -> list[dict]:
    """Restrict only after normal Production acquisition/legal/Notion deduplication."""
    if not source:
        return repos
    if source not in STRATIFIED_SOURCES:
        raise RuntimeError("Invalid source-stratified Fresh target")
    return [repo for repo in repos if repo.get("source") == source]


def _source_counts(rows: list[dict]) -> dict[str, int]:
    """Only aggregate counts; no candidate names, URLs or article content."""
    return {source: sum(row.get("source") == source for row in rows)
            for source in sorted(STRATIFIED_SOURCES)}


def _screening_diagnostics(screened: list[dict], pipeline: Any) -> dict[str, Any]:
    """Observe existing score distribution without modifying selection."""
    scores = [int(row.get("score") or 0) for row in screened]
    notion = int(pipeline.NOTION_SAVE_THRESHOLD_SCORE)
    return {
        "screened_count": len(scores),
        "max_score": max(scores) if scores else None,
        "notion_save_threshold": notion,
        "at_or_above_notion_save": sum(score >= notion for score in scores),
    }


def _fresh_candidates(pipeline: Any) -> tuple[list[dict], dict[str, Any]]:
    limits = _production_acquisition_limits(pipeline)
    groups = {
        "GitHub": pipeline.fetch_github_trending(limits["GitHub"]),
        "HackerNews": pipeline.fetch_hackernews_top(limits["HackerNews"]),
        "ArXiv": pipeline.fetch_arxiv_ai_ml(limits["ArXiv"]),
        # Run268 rewrites the retired Product Hunt call slot to OfficialVendor.
        "ProductHunt": pipeline.fetch_producthunt_trending(limits["OfficialVendor"]),
    }
    collected_by_source = {
        source: len(groups[key]) for source, key in (
            ("GitHub", "GitHub"), ("HackerNews", "HackerNews"),
            ("ArXiv", "ArXiv"), ("OfficialVendor", "ProductHunt"),
        )
    }
    repos = pipeline.round_robin_candidates(groups, limits["max_screening"])

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
    production_duplicate_by_source = dict.fromkeys(sorted(STRATIFIED_SOURCES), 0)
    observed_excluded_by_source = dict.fromkeys(sorted(STRATIFIED_SOURCES), 0)
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
            if repo.get("source") in production_duplicate_by_source:
                production_duplicate_by_source[repo["source"]] += 1
            continue
        if _already_observed(repo):
            observed_excluded += 1
            if repo.get("source") in observed_excluded_by_source:
                observed_excluded_by_source[repo["source"]] += 1
            continue
        local_identity_urls.update(identity_urls)
        if not identity_urls:
            local_fallback_keys.add(fallback_key)
        deduped.append(repo)

    attrition = {
        "collected_by_source": collected_by_source,
        "round_robin_by_source": _source_counts(repos),
        "legal_safe_by_source": _source_counts(safe),
        "dedupe_excluded_by_source": production_duplicate_by_source,
        "observed_excluded_by_source": observed_excluded_by_source,
        "fresh_by_source": _source_counts(deduped),
    }
    requested_source = _validated_requested_source()
    deduped = _restrict_source(deduped, requested_source)
    return deduped[:limits["max_screening"]], {
        "source_attrition": attrition,
        "requested_source": requested_source,
        "collected": len(repos),
        "safe": len(safe),
        "observed_canary_excluded": observed_excluded,
        "fresh_after_dedupe": len(deduped),
        "production_fetch_limits": {k: v for k, v in limits.items() if k != "max_screening"},
        "production_max_screening": limits["max_screening"],
    }


def run(pipeline: Any) -> dict[str, Any]:
    requested_source = _validated_requested_source()  # Reject before any external request.
    os.environ["AIIF_LOCAL_SKILLS_CANARY"] = "true"
    pipeline.initialize_runtime()
    pipeline.reset_article_style_memory()
    setattr(pipeline, "_LOCAL_SKILLS_CANARY_LAST_COMPILE", {})
    setattr(pipeline, "_LOCAL_SKILLS_CANARY_LAST_RESULT", {})

    result: dict[str, Any] = {
        "mode": "local_skills_canary_validation",
        "requested_source": requested_source,
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
        result["screening_diagnostics"] = _screening_diagnostics(screened, pipeline)

        # Reuse the current Production portfolio ordering without writing Stock.
        for item in screened:
            item["notion_page_id"] = (
                "LOCAL_SKILLS_CANARY_NO_WRITE"
                if item.get("score", 0) >= pipeline.NOTION_SAVE_THRESHOLD_SCORE
                else None
            )
        candidates = pipeline._select_stocked_deep_dive_candidates(screened)
        result["screening_diagnostics"]["selected_for_deep_dive"] = len(candidates)
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
            if requested_source and source != requested_source:
                raise RuntimeError("Cross-source Fresh candidate escaped source filter")
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
