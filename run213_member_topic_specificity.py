#!/usr/bin/env python3
"""Run213: eliminate residual generic member topics from current authoritative copy.

Run212 safely recovers stable reader-facing copy from archived Product Review
history, but intentionally rejects stale archive topics.  A small tail can
therefore remain on the deterministic generic topic fallback.

This layer does not relax Run212.  When, and only when, the post-Run212 topic is
still generic, it reuses the *current* Decision Intelligence judgment reason as
the reader-facing topic.  Run170.4 then performs its existing role-separation
step and rewrites the judgment reason from current risk/decision context when
needed, so the topic and judgment reason do not collapse into duplicate copy.

No historical decision field, model call, Gemini request or new factual claim is
introduced here.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Callable

import member_human_language_ux as base
import member_human_language_ux_v2 as ux2
import run212_member_review_copy as run212


_RUNTIME_STATS: dict[str, int] = {}
_INSTALLED = False
_PRIOR_HUMANIZE: Callable[..., dict[str, Any]] | None = None

# These two mixed-language artifacts were produced by the older broad
# ``Evidence`` presentation replacement. Repairs are deliberately local; we do
# not globally rewrite English identifiers or titles.
_HYBRID_COPY_REPAIRS = (
    ("Safety 根拠", "安全性の根拠"),
    ("Transfer 根拠", "転移を示す根拠"),
)


def reset_runtime_stats() -> None:
    _RUNTIME_STATS.clear()
    _RUNTIME_STATS.update(
        {
            "generic_topics_replaced_from_current_reason": 0,
            "hybrid_copy_repairs": 0,
        }
    )


reset_runtime_stats()


def _repair_hybrid_copy(value: Any) -> str:
    text = base._clean(value)
    if not text:
        return ""
    for old, new in _HYBRID_COPY_REPAIRS:
        if old in text:
            text = text.replace(old, new)
            _RUNTIME_STATS["hybrid_copy_repairs"] += 1
    return text


def apply_current_topic_specificity(state: dict[str, Any]) -> dict[str, Any]:
    """Replace only a residual generic topic with a current specific reason."""
    out = dict(state)

    # Repair only known customer-visible mixed-language artifacts. This does
    # not alter source identifiers, URL, score, status, Evidence, or category.
    for key in ("topic", "judgment_reason", "main_risk", "next_action"):
        if key in out:
            out[key] = _repair_hybrid_copy(out.get(key))

    current_topic = base._clean(out.get("topic"))
    if not base.GENERIC_TOPIC_RE.match(current_topic):
        return out

    current_reason = base._clean(out.get("judgment_reason"))
    if not current_reason or base.BAD_REASON_RE.search(current_reason):
        return out
    if base.GENERIC_TOPIC_RE.match(current_reason):
        return out

    out["topic"] = current_reason
    _RUNTIME_STATS["generic_topics_replaced_from_current_reason"] += 1
    return out


def install() -> None:
    """Install Run212 first, then add the current-authority specificity layer."""
    global _INSTALLED, _PRIOR_HUMANIZE
    if _INSTALLED:
        return
    run212.install()
    reset_runtime_stats()
    _PRIOR_HUMANIZE = base.humanize_state

    def specific_humanize_state(
        state: dict[str, Any], review_copy: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert _PRIOR_HUMANIZE is not None
        humanized = _PRIOR_HUMANIZE(state, review_copy)
        return apply_current_topic_specificity(humanized)

    base.humanize_state = specific_humanize_state
    _INSTALLED = True


def run_presentation_sync() -> dict[str, Any]:
    install()
    result = ux2.run_presentation_sync()
    result["run212_review_copy"] = dict(run212._RUNTIME_STATS)
    result["run213_topic_specificity"] = dict(_RUNTIME_STATS)
    result["review_copy_policy"] = "current_authority_archive_copy_only"
    result["topic_fallback_policy"] = "current_authority_reason_only"
    result["zero_gemini_calls"] = True
    return result


def run_body_sync() -> dict[str, Any]:
    result = ux2.run_body_sync()
    result["run213_topic_specificity"] = "presentation_only"
    result["zero_gemini_calls"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1 or args[0] not in {"presentation", "body"}:
        raise SystemExit("usage: python run213_member_topic_specificity.py [presentation|body]")
    result = run_presentation_sync() if args[0] == "presentation" else run_body_sync()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
