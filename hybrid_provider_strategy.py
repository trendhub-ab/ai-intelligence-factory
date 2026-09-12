"""Provider-routing contract for the Groq-preprocess / Gemini-writer hybrid.

This module is intentionally pure and side-effect free. It does not import either
provider SDK, does not mutate Production, and does not perform retries or business
writes. The default remains GEMINI_ONLY so introducing this module cannot change the
current Production path by import alone.

Safety goals:
- Preserve the existing Gemini-only path as the rollback authority.
- Move only bounded preprocessing/decision work to Groq.
- Keep final Japanese article writing on Gemini.
- Never silently fall back from a failed Groq preprocessing stage to Gemini.
- Keep quality gates local/provider-neutral.
- Keep Product Review/comment prose OUTSIDE Hybrid routing until shadow parity is proven.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping

GEMINI_ONLY = "gemini_only"
HYBRID_GROQ_GEMINI = "hybrid_groq_gemini"
VALID_MODES = frozenset({GEMINI_ONLY, HYBRID_GROQ_GEMINI})

GEMINI_ONLY_BACKUP_BRANCH = "backup/gemini-only-run360-20260912"
GEMINI_ONLY_BACKUP_SHA = "bdcd0a548084b348efb821b45b32d4a3faa0dc12"
PRE_RUN360_BACKUP_BRANCH = "backup/gemini-only-run359-20260912"

# Product Review writes comment-like Technology Intelligence properties. It remains a
# separately governed legacy stage and MUST NOT be added to Hybrid Groq routing merely
# because other preprocessing moved to Groq. Migration requires shadow parity evidence.
PRODUCT_REVIEW_MIGRATION_POLICY = "production_frozen_until_shadow_parity"
PRODUCT_REVIEW_HYBRID_ROUTING_ALLOWED = False

MODEL_STAGES = (
    "screening",
    "calibration",
    "decision_plan",
    "article_writer",
)

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
    source = os.environ if env is None else env
    mode = str(source.get("AIIF_PROVIDER_MODE", GEMINI_ONLY)).strip().lower()
    if mode not in VALID_MODES:
        raise HybridRoutingError(f"unsupported_provider_mode:{mode}")
    return mode


def route_stage(stage: str, *, mode: str | None = None, env: Mapping[str, str] | None = None) -> RouteDecision:
    stage = str(stage or "").strip().lower()
    if stage == "product_review":
        raise HybridRoutingError("product_review_provider_migration_frozen")
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

    provider_map = GEMINI_ONLY_STAGE_PROVIDER if selected_mode == GEMINI_ONLY else HYBRID_STAGE_PROVIDER
    provider = provider_map[stage]
    return RouteDecision(
        mode=selected_mode,
        stage=stage,
        provider=provider,
        allow_cross_provider_fallback=False,
    )


def estimate_provider_calls(stage_counts: Mapping[str, int], *, mode: str) -> dict[str, int]:
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
    if not GEMINI_ONLY_BACKUP_BRANCH.startswith("backup/gemini-only-"):
        raise HybridRoutingError("gemini_backup_branch_invalid")
    if len(GEMINI_ONLY_BACKUP_SHA) != 40:
        raise HybridRoutingError("gemini_backup_sha_invalid")
