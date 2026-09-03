#!/usr/bin/env python3
"""Run214: make paid-member next actions specific without new model calls.

Run170.4 intentionally converted vague actions into bounded category-aware
operational steps.  In the live member DB, however, those safe templates became
highly repetitive even when current authoritative fields already contained a
specific ``best_for`` or post-Run213 topic.

This presentation-only layer keeps the existing action itself authoritative and
adds current context only when the action is one of the known deterministic
Run170.4 templates.  It never invents a new benchmark, threshold, product claim,
score, Evidence item, risk or decision.

Context priority:
1. current ``best_for`` / 向いている用途;
2. current non-generic post-Run213 topic / 今回の話題;
3. otherwise fail safe and keep the existing action unchanged.

ZERO Gemini/model requests.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any, Callable

import member_human_language_ux as base
import member_human_language_ux_v2 as ux2
import run213_member_topic_specificity as run213


# Exact outputs of the existing Run170.4 deterministic action generator.
# Explicit source/curated actions are intentionally outside this set and remain
# untouched.
_TEMPLATE_ACTIONS = {
    "実際の業務を1つ選び、5人程度で試し、現在の方法と比べて時間・費用・使いやすさを確認してから導入範囲を決める。",
    "守りたい情報と禁止したい操作を10件程度挙げ、検証環境で防げるか確認し、既存の安全対策との役割分担を決める。",
    "代表的な業務タスクを20件程度用意し、現在の候補と同じ条件で品質・速度・費用を比較する。",
    "代表的な1つの処理を検証環境で動かし、現在の方法と速度・費用・運用負荷を比較する。",
    "実際の利用場面を1つ決め、小規模に試して効果・費用・運用負荷を確認してから導入を判断する。",
    "実際の利用者3〜5人で1週間ほど試し、使いやすさ・回答品質・費用を現在の方法と比較する。",
    "想定する事故や禁止操作を10件程度用意し、検証環境でどこまで防げるかを確認する。",
    "代表タスクを20件程度用意し、小規模テストで品質・速度・費用を現行候補と比較する。",
    "代表的な1つの処理だけを検証環境で動かし、導入前後の速度・費用・運用負荷を比較する。",
    "実際の利用場面を1つ選び、小規模テストで効果・費用・運用負荷を確認する。",
    "自社に関係する用途を1つ決め、次回レビュー時に性能・再現性・公開実装の有無が変わったか確認する。",
    "今は導入せず、次回レビュー時または大型更新時に、保守状況・価格・主要機能の変化を再確認する。",
    "新規採用は止め、同じ用途で現在も保守されている候補を2〜3件比較する。",
    "利用場面を1つ決め、必要な条件を確認してから次の判断へ進む。",
}

_WATCH_DEEP_TECH_TEMPLATE = (
    "自社に関係する用途を1つ決め、次回レビュー時に性能・再現性・公開実装の有無が変わったか確認する。"
)
_WATCH_DEEP_TECH_TAIL = (
    "次回レビュー時に性能・再現性・公開実装の有無が変わったか確認する。"
)

_RUNTIME_STATS: dict[str, int] = {}
_INSTALLED = False
_PRIOR_MEMBER_FIRST_ACTION: Callable[[dict[str, Any]], str] | None = None


def reset_runtime_stats() -> None:
    _RUNTIME_STATS.clear()
    _RUNTIME_STATS.update(
        {
            "template_actions_refined": 0,
            "best_for_context_used": 0,
            "topic_context_used": 0,
            "template_actions_left_without_context": 0,
        }
    )


reset_runtime_stats()


def _first_stable_fragment(value: Any, *, max_chars: int = 110) -> str:
    """Return one bounded current-authority fragment without mid-word clipping."""
    text = base._clean(value)
    if not text:
        return ""
    # A member-facing context label should be a single idea, not a paragraph.
    first = re.split(r"[。！？\n]", text, maxsplit=1)[0].strip(" \t\r\n、。！？")
    if not first or len(first) > max_chars:
        return ""
    return first


def _specific_context(state: dict[str, Any]) -> tuple[str, str]:
    best_for = _first_stable_fragment(state.get("best_for"))
    if best_for:
        return "best_for", best_for

    topic = _first_stable_fragment(state.get("topic"))
    if topic and not base.GENERIC_TOPIC_RE.match(topic):
        return "topic", topic
    return "", ""


def contextualize_template_action(state: dict[str, Any], action: str) -> str:
    """Add only current context to a known deterministic action template."""
    if action not in _TEMPLATE_ACTIONS:
        return action

    source, focus = _specific_context(state)
    if not focus:
        _RUNTIME_STATS["template_actions_left_without_context"] += 1
        return action

    body = action
    if action == _WATCH_DEEP_TECH_TEMPLATE:
        # The focus itself replaces the vague "自社に関係する用途を1つ決め" clause.
        body = _WATCH_DEEP_TECH_TAIL

    if source == "best_for":
        out = f"「{focus}」を想定し、{body}"
        _RUNTIME_STATS["best_for_context_used"] += 1
    else:
        out = f"今回の論点「{focus}」を踏まえ、{body}"
        _RUNTIME_STATS["topic_context_used"] += 1

    _RUNTIME_STATS["template_actions_refined"] += 1
    return out


def install() -> None:
    """Install Run213 first, then wrap only Run170.4's member action function."""
    global _INSTALLED, _PRIOR_MEMBER_FIRST_ACTION
    if _INSTALLED:
        return
    run213.install()
    reset_runtime_stats()
    _PRIOR_MEMBER_FIRST_ACTION = ux2._member_first_action

    def specific_member_first_action(state: dict[str, Any]) -> str:
        assert _PRIOR_MEMBER_FIRST_ACTION is not None
        existing = _PRIOR_MEMBER_FIRST_ACTION(state)
        return contextualize_template_action(state, existing)

    ux2._member_first_action = specific_member_first_action
    _INSTALLED = True


def run_presentation_sync() -> dict[str, Any]:
    install()
    result = run213.run_presentation_sync()
    result["run214_action_specificity"] = dict(_RUNTIME_STATS)
    result["action_context_policy"] = "current_best_for_then_current_topic_only"
    result["zero_gemini_calls"] = True
    return result


def run_body_sync() -> dict[str, Any]:
    result = run213.run_body_sync()
    result["run214_action_specificity"] = "presentation_only"
    result["zero_gemini_calls"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1 or args[0] not in {"presentation", "body"}:
        raise SystemExit("usage: python run214_member_action_specificity.py [presentation|body]")
    result = run_presentation_sync() if args[0] == "presentation" else run_body_sync()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
