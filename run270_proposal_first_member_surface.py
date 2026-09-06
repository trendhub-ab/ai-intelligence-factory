#!/usr/bin/env python3
"""Run270 Proposal-First paid-member presentation overlay.

Run268 is the paid-product/business contract authority. Run250 remains a historical
Work-First compatibility layer, but its visible body semantics no longer match the
current primary ICP. Run270 installs *after* Run250 and changes presentation only:
client technology selection/proposal becomes primary, while internal work use and
skill growth remain secondary benefits.

This module never changes Evidence, Decision Score, canonical status, source data,
Notion schema, or provider/model behavior. ZERO Gemini/model calls.
"""
from __future__ import annotations

from typing import Any

import member_client_action_alignment as alignment
import member_presentation_body_sync as body
import run219_member_human_language_ui as run219


PROPOSAL_FIRST_ICP = (
    "AI・Web・業務システム等を顧客へ提案・開発する、"
    "1〜3名規模のフリーランス／小規模開発事業者"
)
PRIMARY_JOB = (
    "顧客から『このAI / 技術を使うべきか？』と聞かれたとき、"
    "調査・比較・リスク確認・提案作成を短時間で終わらせる"
)

_STATUS_PROPOSAL = {
    "ADOPT": "顧客要件と運用条件が合えば、提案候補として検討できる",
    "TEST": "本番提案の前に、顧客案件に近い条件で小さく検証する",
    "WATCH": "現時点では提案を急がず、条件や成熟度の変化を追う",
    "AVOID": "現時点では提案候補から外し、代替案を比較する",
}


def _clean(value: Any) -> str:
    return alignment.neutral_subject_text(value)


def _proposal_decision_text(state: dict[str, Any]) -> str:
    status = str(state.get("status") or "").strip().upper()
    lead = _STATUS_PROPOSAL.get(status, "顧客要件と利用条件を確認してから提案判断する")
    reason = _clean(state.get("judgment_reason"))
    return f"{lead}。{reason}" if reason else f"{lead}。"


def _proposal_update_text(state: dict[str, Any]) -> str:
    reason = _clean(state.get("change_reason"))
    delta = state.get("delta")
    if not reason or not isinstance(delta, (int, float)) or isinstance(delta, bool):
        return ""
    if float(delta) > 0:
        prefix = "前回より提案候補として再検討する価値が上がりました。"
    elif float(delta) < 0:
        prefix = "前回より提案判断を慎重にする必要が高まりました。"
    else:
        return ""
    return f"{prefix}{reason}"


def _build_children(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Render Proposal-First copy using existing authoritative fields only."""
    children: list[dict[str, Any]] = []

    summary = _clean(state.get("plain_summary"))
    if summary:
        children.append(body._heading("これは何？"))
        children.append(body._paragraph(summary))

    children.append(body._heading("顧客にどう答える？"))
    children.append(body._paragraph(_proposal_decision_text(state)))

    proposal_case = alignment.client_case_text(state)
    if proposal_case:
        children.append(body._heading("提案できる場面"))
        children.append(body._paragraph(proposal_case))

    topic = _clean(state.get("topic"))
    if topic:
        children.append(body._heading("なぜ今見る？"))
        children.append(body._paragraph(topic))

    checks = alignment.client_check_text(state)
    if checks:
        children.append(body._heading("提案前に確認すること"))
        children.append(body._paragraph(checks))

    action = alignment.proposal_action_text(state)
    if action:
        children.append(body._heading("提案・検証の次の一手"))
        children.append(body._paragraph(action))

    update = _proposal_update_text(state)
    if update:
        children.append(body._heading("Decision Update｜提案を変える必要がある？"))
        children.append(body._paragraph(update))

    evidence = run219._clean(state.get("evidence"))
    primary_url = run219._clean(state.get("primary_url"))
    related_article = run219._clean(state.get("related_article"))
    urls = body._extract_urls(evidence, primary_url)
    if urls or related_article:
        children.append(body._heading("確認に使った公式・一次情報"))
        for index, url in enumerate(urls[:5], 1):
            children.append(body._link_paragraph(f"公式・一次情報 {index}", url))
        if related_article:
            children.append(body._link_paragraph("関連記事", related_article))

    return children


def _body_matches_proposal_first(children: list[dict[str, Any]], state: dict[str, Any]) -> bool:
    """Exact deterministic body contract; stale Work-First bodies must rewrite once."""
    return body._body_fingerprint(children) == body._body_fingerprint(_build_children(state))


def install_navigation() -> None:
    """Keep Run250's proven navigation ranker; Run270 changes product framing only."""
    return None


def install_body(target_run219_module: Any | None = None) -> None:
    """Install after Run250 on both the active CLI module and shared body renderer."""
    target = target_run219_module if target_run219_module is not None else run219
    target._build_children = _build_children
    body._build_children = _build_children
    body._body_matches = _body_matches_proposal_first


def contract() -> dict[str, Any]:
    return {
        "initial_icp": PROPOSAL_FIRST_ICP,
        "primary_job": PRIMARY_JOB,
        "product_purpose": "proposal_first_decision_intelligence",
        "client_proposal_primary": True,
        "internal_work_use_secondary": True,
        "skill_growth_secondary": True,
        "navigation_ranker_inherited_from_run250": True,
        "intelligence_engine_preserved": True,
        "deep_tech_preserved": True,
        "source_scores_preserved": True,
        "decision_status_preserved": True,
        "evidence_preserved": True,
        "notion_schema_changed": False,
        "zero_gemini_calls": True,
        "paid_surface": [
            "顧客にどう答える？",
            "提案できる場面",
            "提案前に確認すること",
            "提案・検証の次の一手",
            "Decision Update｜提案を変える必要がある？",
        ],
    }
