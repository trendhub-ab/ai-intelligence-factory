"""Run382: preserve the last valid pre-retry manuscript for read-only validation.

This module does not change any acceptance gate, publication state, or persistence path.
It only captures the ``previous_article`` already passed into a quality-retry prompt so
``article_revalidation`` can report that manuscript as REJECTED when the provider fails
before producing a replacement. Production write paths do not consume this snapshot.
"""
from __future__ import annotations

from typing import Any, Callable

SNAPSHOT_ATTR = "_run382_pre_retry_snapshot"
_INSTALLED_ATTR = "_run382_retry_snapshot_installed"


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


def install(pipeline_module: Any) -> Any:
    """Capture retry input without changing the prompt or provider call."""
    if bool(getattr(pipeline_module, _INSTALLED_ATTR, False)):
        return pipeline_module
    original = getattr(pipeline_module, "build_decision_prompt", None)
    if not callable(original):
        raise RuntimeError("Run382 requires pipeline.build_decision_prompt")

    def wrapped(*args: Any, **kwargs: Any):
        _capture_from_prompt_call(pipeline_module, args, kwargs)
        return original(*args, **kwargs)

    wrapped.__name__ = getattr(original, "__name__", "build_decision_prompt")
    wrapped.__doc__ = getattr(original, "__doc__", None)
    pipeline_module.build_decision_prompt = wrapped
    clear_snapshot(pipeline_module)
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
