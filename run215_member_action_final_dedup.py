#!/usr/bin/env python3
"""Run215: remove the final deterministic next-action duplicates with current context only.

Run214 correctly contextualizes known safe action templates, but it prefers
``best_for`` over ``topic``.  A small set of current records still carry broad,
deterministic ``best_for`` fallback copy while their post-Run213 ``topic`` is
specific.  That priority leaves otherwise distinct records with identical member
actions.

This presentation-only layer keeps Run214's safety boundary and changes only the
context selection rule:

1. a specific current ``best_for`` still wins;
2. a known generic ``best_for`` is bypassed when a specific current topic exists;
3. if no specific topic exists, the existing generic ``best_for`` behavior is
   preserved rather than inventing context.

No score, decision, Evidence, risk, article content or source data is changed.
ZERO Gemini/model requests.
"""
from __future__ import annotations

import json
import sys
from typing import Any

import member_human_language_ux as base
import run214_member_action_specificity as run214


_GENERIC_BEST_FOR_PREFIXES = (
    "論文の対象課題が自社ユースケースと一致し、既存手法との比較を小規模に再現できる研究・開発チーム",
    "関連分野の技術選定・リスク評価・研究ロードマップを行い、次に試す候補を比較したいチーム",
)

_RUNTIME_STATS = {
    "generic_best_for_bypassed_for_specific_topic": 0,
}
_INSTALLED = False


def reset_runtime_stats() -> None:
    _RUNTIME_STATS["generic_best_for_bypassed_for_specific_topic"] = 0


def _is_known_generic_best_for(value: str) -> bool:
    text = base._clean(value)
    return any(text.startswith(prefix) for prefix in _GENERIC_BEST_FOR_PREFIXES)


def _specific_context(state: dict[str, Any]) -> tuple[str, str]:
    best_for = run214._first_stable_fragment(state.get("best_for"))
    topic = run214._first_stable_fragment(state.get("topic"))
    specific_topic = bool(topic and not base.GENERIC_TOPIC_RE.match(topic))

    if best_for and not _is_known_generic_best_for(best_for):
        return "best_for", best_for

    if specific_topic:
        if best_for and _is_known_generic_best_for(best_for):
            _RUNTIME_STATS["generic_best_for_bypassed_for_specific_topic"] += 1
        return "topic", topic

    # Preserve Run214's fail-safe behavior when there is no better current
    # context.  We do not delete a generic label merely to make rows unique.
    if best_for:
        return "best_for", best_for
    return "", ""


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    run214.install()
    reset_runtime_stats()
    run214._specific_context = _specific_context
    _INSTALLED = True


def run_presentation_sync() -> dict[str, Any]:
    install()
    result = run214.run_presentation_sync()
    result["run215_action_final_dedup"] = dict(_RUNTIME_STATS)
    result["action_context_policy"] = "specific_best_for_else_specific_current_topic"
    result["zero_gemini_calls"] = True
    return result


def run_body_sync() -> dict[str, Any]:
    result = run214.run_body_sync()
    result["run215_action_final_dedup"] = "presentation_only"
    result["zero_gemini_calls"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1 or args[0] not in {"presentation", "body"}:
        raise SystemExit("usage: python run215_member_action_final_dedup.py [presentation|body]")
    result = run_presentation_sync() if args[0] == "presentation" else run_body_sync()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
