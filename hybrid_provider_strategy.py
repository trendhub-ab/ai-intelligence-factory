"""Provider-routing contract for the Groq-preprocess / Gemini-writer hybrid.

This module is intentionally pure and side-effect free. It does not import either
provider SDK, does not mutate Production, and does not perform retries or business
writes. The default remains GEMINI_ONLY so introducing this module cannot change the
current Production path by import alone.

Safety goals:
- Preserve the existing Gemini-only path as the rollback authority.
- Move only bounded preprocessing/decision work to Groq.
- Keep final Japanese article writing on Gemini.
- Never silently fall back from a failed Groq preprocessing stage to Gemini; doing so
  would recreate the Gemini call volume we are trying to reduce.
- Keep quality gates local/provider-neutral.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping

GEMINI_ONLY = "gemini_only"
HYBRID_GROQ_GEMINI = "hybrid_groq_gemini"
VALID_MODES = frozenset({GEMINI_ONLY, HYBRID_GROQ_GEMINI})

# Immutable rollback references created before Hybrid implementation.
GEMINI_ONLY_BACKUP_BRANCH = "backup/gemini-only-run360-20260912"
GEMINI_ONLY_BACKUP_SHA = "bdcd0a548084b348efb821b45b32d4a3faa0dc12"
PRE_RUN360_BACKUP_BRANCH = "backup/gemini-only-run359-20260912"

# Stages that are allowed to consume a model call. Local gates are explicitly not here.
MODEL_STAGES = (
    "screening",
    "calibration",
    "decision_plan",
    "article_writer",
)

# Hybrid deliberately keeps prose generation on Gemini. Groq handles the work where
# structured output, classification and bounded reasoning are more valuable than
# Japanese editorial quality.
HYBRID_STAGE_PROVIDER = {
    "screening": "groq",
    "calibration": "groq",
    "decision_plan": "groq",
    "article_writer": "gemini",
}

GEMINI_ONLY_STAGE_PROVIDER = {stage: "gemini" for stage in MODEL_STAGES}

LOCAL_ONLY_STAGES = frozenset({
    "candidate_collection",
    "evidence_normalization",
    "evidence_sufficiency",
    "fact_gate",
    "editorial_gate",
    "publication_gate",
    "human_appeal_gate",
    "note_manuscript",
    "notion_payload",
})


class HybridRoutingError(RuntimeError):
    pass


@dataclass(frozen=True)
class RouteDecision:
    mode: str
    stage: str
    provider: str
    allow_cross_provider_fallback: bool
    business_writes: int = 0


def resolve_mode(env: Mapping[str, str] | None = None) -> str:
    """Resolve routing mode; default is always the existing Gemini-only path."""
    source = os.environ if env is None else env
    mode = str(source.get("AIIF_PROVIDER_MODE", GEMINI_ONLY)).strip().lower()
    if mode not in VALID_MODES:
        raise HybridRoutingError(f"unsupported_provider_mode:{mode}")
    return mode


def route_stage(stage: str, *, mode: str | None = None, env: Mapping[str, str] | None = None) -> RouteDecision:
    stage = str(stage or "").strip().lower()
    if stage in LOCAL_ONLY_STAGES:
        return RouteDecision(
            mode=mode or resolve_mode(env),
            stage=stage,
            provider="local",
            allow_cross_provider_fallback=False,
        )
    if stage not in MODEL_STAGES:
        raise HybridRoutingError(f"unknown_stage:{stage}")

    selected_mode = mode or resolve_mode(env)
    if selected_mode not in VALID_MODES:
        raise HybridRoutingError(f"unsupported_provider_mode:{selected_mode}")

    provider_map = (
        GEMINI_ONLY_STAGE_PROVIDER if selected_mode == GEMINI_ONLY
        else HYBRID_STAGE_PROVIDER
    )
    provider = provider_map[stage]

    # Critical rule: Hybrid preprocessing does not silently consume Gemini when Groq
    # fails. Final article writing is already Gemini by design; local gates remain local.
    return RouteDecision(
        mode=selected_mode,
        stage=stage,
        provider=provider,
        allow_cross_provider_fallback=False,
    )


def estimate_provider_calls(stage_counts: Mapping[str, int], *, mode: str) -> dict[str, int]:
    """Estimate model-call distribution without executing either provider.

    Counts are intentionally stage-level and conservative. Retry behavior is excluded;
    transport retry policy belongs to each provider runtime and must not be hidden here.
    """
    if mode not in VALID_MODES:
        raise HybridRoutingError(f"unsupported_provider_mode:{mode}")
    totals = {"gemini": 0, "groq": 0, "local": 0}
    for raw_stage, raw_count in stage_counts.items():
        stage = str(raw_stage).strip().lower()
        if type(raw_count) is not int or raw_count < 0:
            raise HybridRoutingError(f"invalid_stage_count:{stage}")
        decision = route_stage(stage, mode=mode)
        totals[decision.provider] += raw_count
    return totals


def gemini_call_reduction(stage_counts: Mapping[str, int]) -> dict[str, float | int]:
    """Return deterministic Gemini-call reduction from routing alone.

    This is not a promise about 503 probability. It measures only how many scheduled
    model calls are routed away from Gemini before retries are considered.
    """
    baseline = estimate_provider_calls(stage_counts, mode=GEMINI_ONLY)
    hybrid = estimate_provider_calls(stage_counts, mode=HYBRID_GROQ_GEMINI)
    before = baseline["gemini"]
    after = hybrid["gemini"]
    reduction = before - after
    pct = (reduction / before * 100.0) if before else 0.0
    return {
        "gemini_calls_before": before,
        "gemini_calls_after": after,
        "gemini_calls_avoided": reduction,
        "gemini_call_reduction_pct": round(pct, 2),
        "groq_calls_after": hybrid["groq"],
    }


def assert_backup_contract() -> None:
    """Static invariant used by CI/documentation guards."""
    if not GEMINI_ONLY_BACKUP_BRANCH.startswith("backup/gemini-only-"):
        raise HybridRoutingError("gemini_backup_branch_invalid")
    if len(GEMINI_ONLY_BACKUP_SHA) != 40:
        raise HybridRoutingError("gemini_backup_sha_invalid")
