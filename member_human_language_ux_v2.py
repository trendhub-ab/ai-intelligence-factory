#!/usr/bin/env python3
"""Run170.1: final role-separation guard for member-facing copy.

Run170 humanizes member copy. This small refinement catches older review rows
where a single legacy rationale contains three roles at once: current topic,
next action, and a generic evaluation suffix. Those rows must not be copied
verbatim into ``判断理由``.

Presentation only. ZERO Gemini/model requests.
"""
from __future__ import annotations

import json
import sys
from typing import Any

import member_human_language_ux as base
import member_presentation_sync as mps
import member_ux_body_fast as body_fast
import member_ux_guard as guard


def _deep_tech_reason(state: dict[str, Any]) -> str:
    status = base._clean(state.get("status"))
    if status == "TEST":
        return "研究結果をそのまま本番へ持ち込まず、小さな再現テストを前提に判断します。"
    if status == "WATCH":
        return "研究段階の情報なので、今は導入対象ではなく判断材料として追います。"
    return ""


def refine_judgment_reason(
    state: dict[str, Any], review_copy: dict[str, str] | None = None
) -> str:
    """Keep ``判断理由`` distinct from ``なぜ今見る？`` and ``次にやること``."""
    review_copy = review_copy or {}
    current = base._humanize_terms(state.get("judgment_reason"))
    topic_key = mps._norm_key(state.get("topic"))
    action_key = mps._norm_key(state.get("next_action"))

    # A clean, single-role reason should be preserved.
    if (
        current
        and not base.BAD_REASON_RE.search(current)
        and mps._norm_key(current) != topic_key
        and len(mps._sentences(current)) == 1
    ):
        return current

    raw = review_copy.get("short_rationale") or current
    raw = mps._clean_rationale(base._humanize_terms(raw))
    descriptive: list[str] = []
    for sentence in mps._sentences(raw):
        key = mps._norm_key(sentence)
        if not key:
            continue
        if action_key and key == action_key:
            continue
        if mps._is_action_sentence(sentence):
            continue
        if "一次情報の現状を前提に" in sentence:
            continue
        if base.BAD_REASON_RE.search(sentence):
            continue
        descriptive.append(sentence)

    distinct = [s for s in descriptive if mps._norm_key(s) != topic_key]
    if distinct:
        return distinct[0]

    risk_reason = base._natural_reason_from_risk(
        base._clean(state.get("status")), base._clean(state.get("main_risk"))
    )
    if risk_reason:
        return risk_reason

    if base._clean(state.get("classification")) == "Deep Tech":
        deep_reason = _deep_tech_reason(state)
        if deep_reason:
            return deep_reason

    if descriptive:
        return descriptive[0]
    return current


def install_refined_language_guard() -> tuple[dict[str, int], dict[str, int]]:
    summary_stats = guard.install_presentation_guard()
    guarded_source_state = mps._source_state
    index = base.load_review_copy_index()
    stats = {
        "review_copy_used": 0,
        "reasons_role_separated": 0,
        "bad_reasons_remaining": 0,
        "generic_topics_remaining": 0,
    }

    def refined_source_state(page: dict[str, Any]) -> dict[str, Any] | None:
        state = guarded_source_state(page)
        if not state:
            return None
        reviewed = base.review_copy_for_state(state, index)
        if reviewed:
            stats["review_copy_used"] += 1
        state = base.humanize_state(state, reviewed)
        before = base._clean(state.get("judgment_reason"))
        after = refine_judgment_reason(state, reviewed)
        state["judgment_reason"] = after
        if before != after:
            stats["reasons_role_separated"] += 1
        if base.BAD_REASON_RE.search(after):
            stats["bad_reasons_remaining"] += 1
        if base.GENERIC_TOPIC_RE.match(base._clean(state.get("topic"))):
            stats["generic_topics_remaining"] += 1
        return state

    mps._source_state = refined_source_state
    return summary_stats, stats


def run_presentation_sync() -> dict[str, Any]:
    summary_stats, refine_stats = install_refined_language_guard()
    result = mps.sync_member_presentation()
    result["summary_guard"] = summary_stats
    result["human_language_v2"] = refine_stats
    result["homepage_contract"] = guard.HOME_SHORTLIST_SIZE
    result["zero_gemini_calls"] = True
    if summary_stats.get("missing"):
        raise RuntimeError("Member summary guard left missing summaries")
    if refine_stats["bad_reasons_remaining"]:
        raise RuntimeError(
            f"Member copy still contains {refine_stats['bad_reasons_remaining']} malformed reasons"
        )
    if result.get("source_records", 0) >= guard.HOME_SHORTLIST_SIZE and result.get("homepage_count") != guard.HOME_SHORTLIST_SIZE:
        raise RuntimeError(
            f"Member homepage contract mismatch: expected {guard.HOME_SHORTLIST_SIZE}, got {result.get('homepage_count')}"
        )
    return result


def run_body_sync() -> dict[str, Any]:
    base.install_human_body_builder()
    result = body_fast.sync_member_page_bodies_fast()
    result["reader_order"] = ["これは何？", "いまの判断", "なぜ今見る？", "次にやること"]
    result["zero_gemini_calls"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1 or args[0] not in {"presentation", "body"}:
        raise SystemExit("usage: python member_human_language_ux_v2.py [presentation|body]")
    result = run_presentation_sync() if args[0] == "presentation" else run_body_sync()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
