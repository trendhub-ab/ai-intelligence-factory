#!/usr/bin/env python3
"""Run219: make paid-member detail pages read like ordinary Japanese.

This is a presentation-only layer on top of Run215.  It changes headings,
status wording and the visible generated-callout label only.  Current score,
status, Evidence, risk, source copy, next action, article state and source data
remain authoritative and unchanged.

The migration recognizes both the previous clean member callout and the new
human-language callout, so existing generated bodies are replaced instead of
duplicated.  Manual blocks continue to be preserved by the existing fast body
sync.

ZERO Gemini/model requests.
"""
from __future__ import annotations

import json
import sys
from typing import Any

import member_human_language_ux as base
import member_presentation_body_sync as body
import member_ux_guard as guard
import run215_member_action_final_dedup as run215


NEW_VISIBLE_CALLOUT_LABEL = "🧭 このAI・技術をどう見る？"
PREVIOUS_VISIBLE_CALLOUT_LABEL = "🧭 判断サマリー"

STATUS_PLAIN = {
    "ADOPT": "導入を考えてよい",
    "TEST": "まず小さく試す",
    "WATCH": "もう少し様子を見る",
    "AVOID": "今は選ばない",
}

_INSTALLED = False


def _clean(value: Any) -> str:
    return base._clean(value)


def _status_summary(state: dict[str, Any]) -> str:
    status = _clean(state.get("status"))
    label = STATUS_PLAIN.get(status, "確認が必要")
    score = state.get("score")
    score_text = (
        f"{int(score)}点"
        if isinstance(score, (int, float)) and not isinstance(score, bool)
        else "—"
    )
    readiness = _clean(state.get("readiness")) or "—"
    confidence = _clean(state.get("confidence")) or "—"
    return (
        f"いまの目安：{label}｜参考スコア：{score_text}｜"
        f"実用性：{readiness}｜情報の確かさ：{confidence}"
    )


def _build_children(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep current authority but present it in non-engineer-first language."""
    children: list[dict[str, Any]] = []

    summary = _clean(state.get("plain_summary"))
    if summary:
        children.append(body._heading("これは何？"))
        children.append(body._paragraph(summary))

    children.append(body._heading("いま、どうする？"))
    children.append(body._paragraph(_status_summary(state)))

    topic = _clean(state.get("topic"))
    if topic:
        children.append(body._heading("なぜ今見る？"))
        children.append(body._paragraph(topic))

    action = _clean(state.get("next_action"))
    if action:
        children.append(body._heading("次にやること"))
        children.append(body._paragraph(action))

    reason = _clean(state.get("judgment_reason"))
    if reason:
        children.append(body._heading("そう判断した理由"))
        children.append(body._paragraph(reason))

    risk = _clean(state.get("main_risk"))
    if risk:
        children.append(body._heading("気をつけたいこと"))
        children.append(body._paragraph(risk))

    best_for = _clean(state.get("best_for"))
    if best_for:
        children.append(body._heading("こんな使い方に向いています"))
        children.append(body._paragraph(best_for))

    avoid_for = _clean(state.get("avoid_for"))
    if avoid_for:
        children.append(body._heading("こんな使い方には向きません"))
        children.append(body._paragraph(avoid_for))

    change_reason = _clean(state.get("change_reason"))
    if change_reason:
        children.append(body._heading("前と判断が変わった理由"))
        children.append(body._paragraph(change_reason))

    evidence = _clean(state.get("evidence"))
    primary_url = _clean(state.get("primary_url"))
    related_article = _clean(state.get("related_article"))
    urls = body._extract_urls(evidence, primary_url)
    if urls or related_article:
        children.append(body._heading("確認に使った公式・一次情報"))
        for index, url in enumerate(urls[:5], 1):
            children.append(body._link_paragraph(f"公式・一次情報 {index}", url))
        if related_article:
            children.append(body._link_paragraph("関連記事", related_article))

    return children


def _looks_like_generated_member_callout(
    block: dict[str, Any], child_cache: dict[str, list[dict[str, Any]]]
) -> bool:
    """Recognize both pre-Run219 and Run219 generated member callouts."""
    if block.get("type") != "callout":
        return False
    label = body._block_text(block)
    if label not in {NEW_VISIBLE_CALLOUT_LABEL, PREVIOUS_VISIBLE_CALLOUT_LABEL}:
        return False
    block_id = str(block.get("id") or "")
    if not block_id:
        return False
    if block_id in child_cache:
        children = child_cache[block_id]
    else:
        children = body._children(block_id)
        child_cache[block_id] = children
    headings = guard._heading_texts(children)
    has_decision = bool({"いま、どうする？", "いまの判断", "結論"} & headings)
    has_reason = bool({"そう判断した理由", "判断理由"} & headings)
    return has_decision and "次にやること" in headings and has_reason


def _install_body_builder() -> None:
    guard.VISIBLE_CALLOUT_LABEL = NEW_VISIBLE_CALLOUT_LABEL
    body._build_children = _build_children
    guard._looks_like_generated_visible_callout = _looks_like_generated_member_callout


def install() -> None:
    """Make Run170/170.4's body-install hook resolve to the Run219 builder."""
    global _INSTALLED
    if _INSTALLED:
        return
    base.install_human_body_builder = _install_body_builder
    _INSTALLED = True


def run_presentation_sync() -> dict[str, Any]:
    result = run215.run_presentation_sync()
    result["run219_human_language_ui"] = "body_and_member_navigation_only"
    result["zero_gemini_calls"] = True
    return result


def run_body_sync() -> dict[str, Any]:
    install()
    result = run215.run_body_sync()
    result["run219_human_language_ui"] = {
        "visible_callout_label": NEW_VISIBLE_CALLOUT_LABEL,
        "status_codes_hidden_from_body_summary": True,
        "non_engineer_headings": True,
    }
    result["reader_order"] = ["これは何？", "いま、どうする？", "なぜ今見る？", "次にやること"]
    result["zero_gemini_calls"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1 or args[0] not in {"presentation", "body"}:
        raise SystemExit("usage: python run219_member_human_language_ui.py [presentation|body]")
    result = run_presentation_sync() if args[0] == "presentation" else run_body_sync()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
