#!/usr/bin/env python3
"""Run250: align the paid member surface to the initial client-service ICP.

Run250 is presentation-only. The Intelligence Engine, source facts, Evidence,
canonical score/status, Deep Tech inventory and Notion schema remain unchanged.

It changes two paid-surface behaviors:
1. Homepage ranking uses ICP relevance for navigation while preserving the source
   score in the actual record.
2. Member detail bodies translate authoritative fields into client-work language:
   client use case -> business impact -> checks -> proposal next step.

ZERO model/provider calls.
"""
from __future__ import annotations

from typing import Any, Callable

import member_client_action_alignment as alignment
import member_presentation_body_sync as body
import member_presentation_sync as presentation
import run219_member_human_language_ui as run219

_NAV_INSTALLED = False
_BODY_INSTALLED = False
_BASE_ASSIGN_HOME_RANKS: Callable[..., list[dict[str, Any]]] | None = None


def _key(state: dict[str, Any]) -> str:
    return str(state.get("sync_id") or state.get("name") or id(state))


def rank_states_for_client_action(
    states: list[dict[str, Any]],
    *,
    ranker: Callable[..., list[dict[str, Any]]],
    limit: int,
) -> list[dict[str, Any]]:
    """Use proxy scores for navigation, then copy ranks back without touching source scores."""
    for state in states:
        state["rank"] = None

    proxies: list[dict[str, Any]] = []
    originals = {_key(state): state for state in states}
    for state in states:
        proxy = dict(state)
        proxy["_source_score"] = state.get("score")
        proxy["_icp_relevance"] = alignment.icp_relevance_score(state)
        proxy["score"] = alignment.product_rank_score(state)
        proxies.append(proxy)

    ranked_proxies = ranker(proxies, limit=limit)
    selected: list[dict[str, Any]] = []
    for proxy in sorted(
        ranked_proxies,
        key=lambda x: (
            int(x.get("rank")) if isinstance(x.get("rank"), (int, float)) else 9999,
            _key(x),
        ),
    ):
        original = originals.get(_key(proxy))
        if original is None:
            continue
        original["rank"] = proxy.get("rank")
        # Lifecycle is navigation metadata, not a source fact; preserve it if Run225 set it.
        if proxy.get("stock_lifecycle"):
            original["stock_lifecycle"] = proxy.get("stock_lifecycle")
        if proxy.get("stock_lifecycle_reason"):
            original["stock_lifecycle_reason"] = proxy.get("stock_lifecycle_reason")
        selected.append(original)
    return selected


def assign_home_ranks_for_client_action(
    states: list[dict[str, Any]], *, limit: int = presentation.MEMBER_HOME_MAX
) -> list[dict[str, Any]]:
    if _BASE_ASSIGN_HOME_RANKS is None:
        raise RuntimeError("Run250 navigation overlay was not installed")
    return rank_states_for_client_action(
        states,
        ranker=_BASE_ASSIGN_HOME_RANKS,
        limit=max(1, limit),
    )


def _build_children(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Client-action body using existing authoritative values only."""
    children: list[dict[str, Any]] = []

    summary = run219._clean(state.get("plain_summary"))
    if summary:
        children.append(body._heading("これは何？"))
        children.append(body._paragraph(summary))

    children.append(body._heading("いま、どうする？"))
    children.append(body._paragraph(run219._status_summary(state)))

    client_case = alignment.client_case_text(state)
    if client_case:
        children.append(body._heading("案件で使える場面"))
        children.append(body._paragraph(client_case))

    impact = alignment.business_impact_text(state)
    if impact:
        children.append(body._heading("案件への意味（Business Impact）"))
        children.append(body._paragraph(impact))

    topic = run219._clean(state.get("topic"))
    if topic:
        children.append(body._heading("なぜ今見る？"))
        children.append(body._paragraph(topic))

    checks = alignment.client_check_text(state)
    if checks:
        children.append(body._heading("提案前に確認すること"))
        children.append(body._paragraph(checks))

    action = alignment.proposal_action_text(state)
    if action:
        children.append(body._heading("提案時の次の一手"))
        children.append(body._paragraph(action))

    update = alignment.decision_update_text(state)
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


def install_navigation() -> None:
    """Install after Run225 so lifecycle constraints remain the outer source policy."""
    global _NAV_INSTALLED, _BASE_ASSIGN_HOME_RANKS
    if _NAV_INSTALLED:
        return
    _BASE_ASSIGN_HOME_RANKS = presentation.assign_home_ranks
    presentation.assign_home_ranks = assign_home_ranks_for_client_action
    _NAV_INSTALLED = True


def install_body() -> None:
    """Replace only Run219's presentation builder; source state stays authoritative."""
    global _BODY_INSTALLED
    if _BODY_INSTALLED:
        return
    run219._build_children = _build_children
    _BODY_INSTALLED = True


def contract() -> dict[str, Any]:
    return {
        "initial_icp": alignment.ICP_LABEL,
        "intelligence_engine_preserved": True,
        "deep_tech_preserved": True,
        "source_scores_preserved": True,
        "evidence_preserved": True,
        "notion_schema_changed": False,
        "paid_surface": [
            "案件で使える場面",
            "案件への意味（Business Impact）",
            "提案前に確認すること",
            "提案時の次の一手",
            "Decision Update",
        ],
        "zero_gemini_calls": True,
    }
