#!/usr/bin/env python3
"""Run250/253: align the paid member surface to the initial work-use ICP.

Run250 remains presentation-only. The Intelligence Engine, source facts, Evidence,
canonical score/status, Deep Tech inventory and Notion schema remain unchanged.

Run253 corrects the product centre of gravity: the primary job is not "answer a
client's AI question". It is "understand what is worth using in my own work".
Client proposal reuse remains available as a secondary outcome.

The paid surface therefore does two things:
1. Homepage ranking uses work relevance for navigation while preserving the source
   score in the actual record.
2. Member detail bodies translate authoritative fields into work-use language:
   work use case -> business impact -> checks -> next step.

Run251 hardening note:
Run170.4 contained a legacy fixed three-item editorial shortlist for the older
broad/corporate member product. That installer executes *inside* the lower
presentation stack, after Run250 is initially installed, so it can otherwise
silently regain final authority. Run250 explicitly retires that old fixed
shortlist before the lower stack runs. The lower editorial wrapper remains in
place as a fallback but delegates selection to the current relevance ranker.

Run252 hardening note:
The production workflow executes ``run219_member_human_language_ui.py`` as a
script. In that mode the active wrapper is ``__main__`` while importing Run250
also imports a second canonical ``run219_member_human_language_ui`` module.
Patching only that canonical copy leaves the active CLI wrapper on the old body
builder. ``install_body`` therefore accepts the active wrapper module explicitly
and always binds the current builder to both that wrapper and the shared body
renderer before lower layers run.

ZERO model/provider calls.
"""
from __future__ import annotations

from typing import Any, Callable

import member_client_action_alignment as alignment
import member_human_language_ux_v2 as ux2
import member_presentation_body_sync as body
import member_presentation_sync as presentation
import run219_member_human_language_ui as run219

_NAV_INSTALLED = False
_BODY_INSTALLED = False
_BASE_ASSIGN_HOME_RANKS: Callable[..., list[dict[str, Any]]] | None = None
_BASE_BODY_MATCHES: Callable[..., bool] | None = None


def _key(state: dict[str, Any]) -> str:
    return str(state.get("sync_id") or state.get("name") or id(state))


def retire_legacy_editorial_shortlist() -> tuple[str, ...]:
    """Disable the pre-ICP fixed shortlist while preserving copy overrides."""
    previous = tuple(ux2.EDITORIAL_HOME_SYNC_IDS)
    ux2.EDITORIAL_HOME_SYNC_IDS = ()
    return previous


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
    """Work-first body using existing authoritative values only."""
    children: list[dict[str, Any]] = []

    summary = run219._clean(state.get("plain_summary"))
    if summary:
        children.append(body._heading("これは何？"))
        children.append(body._paragraph(summary))

    children.append(body._heading("いま、どうする？"))
    children.append(body._paragraph(run219._status_summary(state)))

    work_case = alignment.work_case_text(state)
    if work_case:
        children.append(body._heading("仕事で使える場面"))
        children.append(body._paragraph(work_case))

    impact = alignment.business_impact_text(state)
    if impact:
        children.append(body._heading("仕事への意味（Business Impact）"))
        children.append(body._paragraph(impact))

    topic = run219._clean(state.get("topic"))
    if topic:
        children.append(body._heading("なぜ今見る？"))
        children.append(body._paragraph(topic))

    checks = alignment.work_check_text(state)
    if checks:
        children.append(body._heading("使う前に確認すること"))
        children.append(body._paragraph(checks))

    action = alignment.work_action_text(state)
    if action:
        children.append(body._heading("試すときの次の一手"))
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


def _heading_texts(blocks: list[dict[str, Any]]) -> set[str]:
    texts: set[str] = set()
    for block in blocks:
        if block.get("type") != "heading_3":
            continue
        payload = block.get("heading_3") or {}
        parts: list[str] = []
        for item in payload.get("rich_text") or []:
            text = item.get("plain_text")
            if not text:
                text = ((item.get("text") or {}).get("content"))
            if text:
                parts.append(str(text))
        joined = "".join(parts).strip()
        if joined:
            texts.add(joined)
    return texts


def _body_matches_client_action(
    children: list[dict[str, Any]], state: dict[str, Any]
) -> bool:
    """Require current work-first product semantics, not only source-state equality."""
    if _BASE_BODY_MATCHES is None or not _BASE_BODY_MATCHES(children, state):
        return False
    headings = _heading_texts(children)
    required = {"いま、どうする？", "仕事への意味（Business Impact）"}
    if alignment.work_case_text(state):
        required.add("仕事で使える場面")
    if alignment.work_action_text(state):
        required.add("試すときの次の一手")
    if alignment.work_check_text(state):
        required.add("使う前に確認すること")
    return required.issubset(headings)


def install_navigation() -> None:
    """Install after Run225 and retire the older fixed shortlist."""
    global _NAV_INSTALLED, _BASE_ASSIGN_HOME_RANKS
    if _NAV_INSTALLED:
        return
    retire_legacy_editorial_shortlist()
    _BASE_ASSIGN_HOME_RANKS = presentation.assign_home_ranks
    presentation.assign_home_ranks = assign_home_ranks_for_client_action
    _NAV_INSTALLED = True


def install_body(target_run219_module: Any | None = None) -> None:
    """Bind work-first body semantics to the active wrapper and shared renderer."""
    global _BODY_INSTALLED, _BASE_BODY_MATCHES
    target = target_run219_module if target_run219_module is not None else run219

    target._build_children = _build_children
    body._build_children = _build_children

    if _BODY_INSTALLED:
        return
    _BASE_BODY_MATCHES = body._body_matches
    body._body_matches = _body_matches_client_action
    _BODY_INSTALLED = True


def contract() -> dict[str, Any]:
    return {
        "initial_icp": alignment.ICP_LABEL,
        "product_purpose": "work_first_decision_intelligence",
        "client_proposal_secondary": True,
        "intelligence_engine_preserved": True,
        "deep_tech_preserved": True,
        "source_scores_preserved": True,
        "evidence_preserved": True,
        "notion_schema_changed": False,
        "legacy_fixed_shortlist_retired": True,
        "client_action_body_migration_required": True,
        "work_first_body_migration_required": True,
        "script_entrypoint_body_authority": True,
        "paid_surface": [
            "仕事で使える場面",
            "仕事への意味（Business Impact）",
            "使う前に確認すること",
            "試すときの次の一手",
            "Decision Update",
        ],
        "zero_gemini_calls": True,
    }
