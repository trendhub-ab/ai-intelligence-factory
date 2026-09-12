"""Run382: preserve the last valid pre-retry manuscript for read-only validation.

This module does not change any acceptance gate, publication state, or persistence path.
It captures the ``previous_article`` already passed into a quality-retry prompt. If the
provider then fails and the canonical generator returns ``None``, read-only validation
lanes receive that exact pre-retry manuscript as ``rejected`` instead of losing the
specimen entirely. Production write paths never consume this fallback.
"""
from __future__ import annotations

from typing import Any

SNAPSHOT_ATTR = "_run382_pre_retry_snapshot"
_INSTALLED_ATTR = "_run382_retry_snapshot_installed"
_READ_ONLY_ORIGINS = frozenset({"pending_retry_validation", "article_revalidation"})


def clear_snapshot(pipeline_module: Any) -> None:
    setattr(pipeline_module, SNAPSHOT_ATTR, None)


def peek_snapshot(pipeline_module: Any) -> dict[str, str] | None:
    value = getattr(pipeline_module, SNAPSHOT_ATTR, None)
    return dict(value) if isinstance(value, dict) else None


def consume_snapshot(pipeline_module: Any) -> dict[str, str] | None:
    value = peek_snapshot(pipeline_module)
    clear_snapshot(pipeline_module)
    return value


def _capture_from_prompt_call(pipeline_module: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    # Canonical signature: name, url, stars, desc, quality_feedback, ...,
    # previous_article=<...>. Retry calls use previous_article as a keyword today.
    feedback = str(kwargs.get("quality_feedback") or (args[4] if len(args) > 4 else "") or "").strip()
    previous = str(kwargs.get("previous_article") or "").strip()
    if not feedback or not previous:
        return
    setattr(
        pipeline_module,
        SNAPSHOT_ATTR,
        {
            "manuscript": previous,
            "quality_feedback": feedback,
        },
    )


def _candidate_origin(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    if "candidate_origin" in kwargs:
        return str(kwargs.get("candidate_origin") or "new")
    # generate_intelligence_report positional order:
    # repo, notion_page_id, screening_score, screening_reason, persist_results,
    # candidate_rank, candidate_origin, ...
    return str(args[6] if len(args) > 6 else "new")


def _persist_results(args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool:
    if "persist_results" in kwargs:
        return bool(kwargs.get("persist_results"))
    return bool(args[4]) if len(args) > 4 else True


def install(pipeline_module: Any) -> Any:
    """Install read-only retry-snapshot preservation without weakening any gate."""
    if bool(getattr(pipeline_module, _INSTALLED_ATTR, False)):
        return pipeline_module

    original_prompt = getattr(pipeline_module, "build_decision_prompt", None)
    original_generate = getattr(pipeline_module, "generate_intelligence_report", None)
    if not callable(original_prompt):
        raise RuntimeError("Run382 requires pipeline.build_decision_prompt")
    if not callable(original_generate):
        raise RuntimeError("Run382 requires pipeline.generate_intelligence_report")

    def prompt_with_snapshot(*args: Any, **kwargs: Any):
        _capture_from_prompt_call(pipeline_module, args, kwargs)
        return original_prompt(*args, **kwargs)

    prompt_with_snapshot.__name__ = getattr(original_prompt, "__name__", "build_decision_prompt")
    prompt_with_snapshot.__doc__ = getattr(original_prompt, "__doc__", None)
    pipeline_module.build_decision_prompt = prompt_with_snapshot

    def generate_with_snapshot(*args: Any, **kwargs: Any):
        origin = _candidate_origin(args, kwargs)
        persist = _persist_results(args, kwargs)
        clear_snapshot(pipeline_module)
        result = original_generate(*args, **kwargs)
        if result is not None:
            clear_snapshot(pipeline_module)
            return result
        if persist or origin not in _READ_ONLY_ORIGINS:
            clear_snapshot(pipeline_module)
            return None
        snapshot = consume_snapshot(pipeline_module) or {}
        manuscript = str(snapshot.get("manuscript") or "").strip()
        if not manuscript:
            return None
        logger = getattr(pipeline_module, "logger", None)
        if logger is not None:
            logger.warning(
                "[RUN382 RETRY SNAPSHOT PRESERVED] origin=%s chars=%s status=rejected persist=false",
                origin,
                len(manuscript),
            )
        return manuscript, "rejected"

    generate_with_snapshot.__name__ = getattr(original_generate, "__name__", "generate_intelligence_report")
    generate_with_snapshot.__doc__ = getattr(original_generate, "__doc__", None)
    pipeline_module.generate_intelligence_report = generate_with_snapshot

    clear_snapshot(pipeline_module)
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
