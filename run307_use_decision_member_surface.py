#!/usr/bin/env python3
"""Run307: generic AI/technology use-decision member surface.

Run270 remains the historical Proposal-First compatibility layer. Run307 installs after
Run270 and broadens the current visible product framing so the same paid product helps a
solo developer / freelancer / small operator decide whether an AI or technology is usable
for their own development, internal work, or a client proposal without making the client
case the primary subject.

The core promise is simple: ``「このAI、使える！」を、根拠付きで判断できる。``

This module changes presentation framing only. It never changes source Evidence, Decision
Score, canonical status, source data, Notion schema, ranking source quality, or provider/model
behavior. ZERO Gemini/model calls.
"""
from __future__ import annotations

from typing import Any

import member_client_action_alignment as alignment
import member_presentation_body_sync as body
import run219_member_human_language_ui as run219


USE_DECISION_ICP = (
    "AI・Web・業務システム等を自ら開発・導入したり、必要に応じて提案したりする、"
    "フリーランス／個人事業主／1〜3名規模の小規模事業者"
)
PRIMARY_JOB = (
    "新しいAI・技術について『このAI、使える！』と判断するために、"
    "Evidence・比較・リスク・利用条件・小規模検証条件を短時間で整理する"
)
CORE_PROMISE = "「このAI、使える！」を、根拠付きで判断できる。"

_STATUS_USE = {
    "ADOPT": "利用条件が合えば、導入候補として検討できる",
    "TEST": "本番利用の前に、近い条件で小さく検証する",
    "WATCH": "現時点では採用を急がず、条件や成熟度の変化を追う",
    "AVOID": "現時点では採用候補から外し、代替案を比較する",
}


def _clean(value: Any) -> str:
    return alignment.neutral_subject_text(value)


def _use_decision_text(state: dict[str, Any]) -> str:
    status = str(state.get("status") or "").strip().upper()
    lead = _STATUS_USE.get(status, "利用条件を確認してから、使えるか判断する")
    reason = _clean(state.get("judgment_reason"))
    return f"{lead}。{reason}" if reason else f"{lead}。"


def _use_update_text(state: dict[str, Any]) -> str:
    reason = _clean(state.get("change_reason"))
    delta = state.get("delta")
    if not reason or not isinstance(delta, (int, float)) or isinstance(delta, bool):
        return ""
    if float(delta) > 0:
        prefix = "前回より『使える』と判断できる材料が増えました。"
    elif float(delta) < 0:
        prefix = "前回より利用判断を慎重にする必要が高まりました。"
    else:
        return ""
    return f"{prefix}{reason}"


def _build_children(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Render current generic use-decision copy using existing authoritative fields only."""
    children: list[dict[str, Any]] = []

    summary = _clean(state.get("plain_summary"))
    if summary:
        children.append(body._heading("これは何？"))
        children.append(body._paragraph(summary))

    children.append(body._heading("いま、使える？"))
    children.append(body._paragraph(_use_decision_text(state)))

    use_case = alignment.work_case_text(state)
    if use_case:
        children.append(body._heading("使える場面"))
        children.append(body._paragraph(use_case))

    topic = _clean(state.get("topic"))
    if topic:
        children.append(body._heading("なぜ今見る？"))
        children.append(body._paragraph(topic))

    checks = alignment.work_check_text(state)
    if checks:
        children.append(body._heading("使う前に確認すること"))
        children.append(body._paragraph(checks))

    action = alignment.work_action_text(state)
    if action:
        children.append(body._heading("試す・導入する次の一手"))
        children.append(body._paragraph(action))

    update = _use_update_text(state)
    if update:
        children.append(body._heading("Decision Update｜判断を変える必要がある？"))
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


def _body_matches_use_decision(children: list[dict[str, Any]], state: dict[str, Any]) -> bool:
    """Exact deterministic body contract; superseded Proposal-First bodies rewrite once."""
    return body._body_fingerprint(children) == body._body_fingerprint(_build_children(state))


def install_navigation() -> None:
    """Keep the existing navigation ranker; Run307 changes product framing only."""
    return None


def install_body(target_run219_module: Any | None = None) -> None:
    """Install after Run270 on the active wrapper and shared body renderer."""
    target = target_run219_module if target_run219_module is not None else run219
    target._build_children = _build_children
    body._build_children = _build_children
    body._body_matches = _body_matches_use_decision


def contract() -> dict[str, Any]:
    return {
        "initial_icp": USE_DECISION_ICP,
        "primary_job": PRIMARY_JOB,
        "core_promise": CORE_PROMISE,
        "product_purpose": "use_decision_intelligence",
        "self_development_supported": True,
        "internal_work_use_supported": True,
        "client_proposal_supported": True,
        "client_proposal_primary": False,
        "navigation_ranker_inherited": True,
        "intelligence_engine_preserved": True,
        "deep_tech_preserved": True,
        "source_scores_preserved": True,
        "decision_status_preserved": True,
        "evidence_preserved": True,
        "notion_schema_changed": False,
        "zero_gemini_calls": True,
        "paid_surface": [
            "いま、使える？",
            "使える場面",
            "使う前に確認すること",
            "試す・導入する次の一手",
            "Decision Update｜判断を変える必要がある？",
        ],
    }
