"""ONE-SHOT E2E: one existing editorial article, one provider request, normal gates."""
from __future__ import annotations

import json
from pathlib import Path

from gemini_temporary_exclusion import allowed_pool
from run374_ready_rescue import run_reserved_ready_rescue


APPROVED_MODELS = {
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
}


def validation_pool(pool, now=None):
    """Use the normal article model set; only the time-bounded exclusion may remove 3.6."""
    return [model for model in allowed_pool(pool, now=now) if model in APPROVED_MODELS]


def run(pipeline):
    pipeline.DEEP_DIVE_MODEL_POOL = validation_pool(pipeline.DEEP_DIVE_MODEL_POOL)
    pipeline.DEEP_DIVE_MODEL_CANDIDATES = list(pipeline.DEEP_DIVE_MODEL_POOL)
    if not pipeline.DEEP_DIVE_MODEL_POOL:
        raise RuntimeError("Ready Rescue validation has no approved model")
    pipeline.initialize_runtime()
    cap = int(pipeline.DEEP_DIVE_MODEL_BUDGET.budget)
    pipeline._run346_original_deep_dive_budget = cap
    pipeline._READY_RESCUE_VALIDATION = True
    result = {"mode": "ready_rescue_validation", "ready": 0, "provider_sends": 0,
              "total_cap": cap, "error": ""}
    try:
        ready, rank = run_reserved_ready_rescue(pipeline, 0, 0)
        result.update(ready=ready, candidate_rank=rank)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        result["provider_sends"] = getattr(pipeline, "_READY_RESCUE_PROVIDER_SENDS", 0)
        destination = Path("article_audit/ready_rescue_validation.json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pipeline.logger.info("[READY RESCUE VALIDATION] %s", result)
    return result
