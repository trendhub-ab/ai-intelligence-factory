#!/usr/bin/env python3
"""Run170: human-language UX layer for the member Decision Intelligence product.

This module sits on top of the Run169 presentation guard and Run169.1 efficient
body migration. It changes presentation only: Product Review scores, Evidence,
article generation and the internal decision model are untouched.

Goals:
- remove mechanical/AI-sounding fallback copy from member-visible fields;
- prefer evidence-reviewed item-specific copy already committed in
  ``external_reviews/*.json``;
- explain common technical acronyms in ordinary Japanese;
- fail safe against malformed Japanese such as ``必要ため``;
- hide generic Deep Tech boilerplate when it adds no item-specific value;
- show ``これは何？`` before the decision on detail pages;
- use customer-language labels while retaining ADOPT/TEST/WATCH/AVOID codes;
- keep all migrations deterministic and ZERO Gemini/model requests.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import member_presentation_body_sync as body
import member_presentation_sync as mps
import member_ux_body_fast as body_fast
import member_ux_guard as guard


GENERIC_DEEP_RISK = (
    "現時点のEvidenceは主に研究・ベンチマーク由来で、"
    "対象条件外への一般化や本番運用の安定性は確立していない。"
)
GENERIC_DEEP_BEST = (
    "関連分野の技術選定・リスク評価・研究ロードマップを行い、"
    "次に試す候補を比較したいチーム。"
)
GENERIC_DEEP_AVOID = (
    "短期に安定した本番導入を必要とし、研究成果の再現検証に時間や計算資源を割けないケース。"
)

GENERIC_TOPIC_RE = re.compile(r"^.+の現在の機能・保守状況を確認しています[。.]?$")
BAD_REASON_RE = re.compile(r"(?:必要ため|重要ため|妥当です|妥当である|判断が妥当)")

OLD_GENERIC_ACTIONS = {
    "導入候補として、自社要件との適合と運用条件を最終確認する。",
    "代表業務を1つ選び、小さく試して効果と運用負荷を確認する。",
    "次回レビューまで監視し、成熟度・保守状況の変化を確認する。",
    "新規採用は見送り、保守中の代替候補を比較する。",
}

STATUS_HUMAN = {
    "ADOPT": "導入を検討",
    "TEST": "まず試す",
    "WATCH": "様子を見る",
    "AVOID": "見送る",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm_url(value: Any) -> str:
    return _clean(value).rstrip("/").casefold()


def _norm_name(value: Any) -> str:
    return _clean(value).casefold()


def _humanize_terms(text: Any) -> str:
    """Explain only common acronyms; preserve names and technical precision."""
    value = _clean(text)
    if not value:
        return ""
    value = value.replace("Evidence", "根拠")
    if "大規模言語モデル" not in value:
        value = re.sub(r"(?<![A-Za-z0-9])LLM(?![A-Za-z0-9])", "大規模言語モデル（LLM）", value)
    if "画像と言語を扱うAIモデル" not in value:
        value = re.sub(r"(?<![A-Za-z0-9])VLM(?![A-Za-z0-9])", "画像と言語を扱うAIモデル（VLM）", value)
    if "強化学習（RL）" not in value:
        value = re.sub(r"(?<![A-Za-z0-9])RL(?![A-Za-z0-9])", "強化学習（RL）", value)
    if "小規模な試行（PoC）" not in value:
        value = re.sub(r"(?<![A-Za-z0-9])PoC(?![A-Za-z0-9])", "小規模な試行（PoC）", value)
    if "AI・機械学習の開発・運用管理（MLOps）" not in value:
        value = re.sub(r"(?<![A-Za-z0-9])MLOps(?![A-Za-z0-9])", "AI・機械学習の開発・運用管理（MLOps）", value)
    if "Chain-of-Thought" not in value and re.search(r"(?<![A-Za-z0-9])CoT(?![A-Za-z0-9])", value):
        value = re.sub(r"(?<![A-Za-z0-9])CoT(?![A-Za-z0-9])", "Chain-of-Thought（CoT）", value)
    return value


def load_review_copy_index(root: str | Path = "external_reviews") -> dict[str, dict[str, dict[str, str]]]:
    """Index evidence-reviewed copy by URL and name, with later fix files winning."""
    by_url: dict[str, dict[str, str]] = {}
    by_name: dict[str, dict[str, str]] = {}
    root_path = Path(root)
    if not root_path.exists():
        return {"by_url": by_url, "by_name": by_name}

    for path in sorted(root_path.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = payload.get("reviews") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            review = row.get("review") or {}
            context = row.get("decision_context") or {}
            if not isinstance(review, dict):
                review = {}
            if not isinstance(context, dict):
                context = {}
            copy = {
                "plain_summary": _clean(context.get("plain_summary") or row.get("description")),
                "topic_trigger": _clean(context.get("topic_trigger")),
                "short_rationale": _clean(review.get("short_rationale")),
                "main_risk": _clean(review.get("main_risk")),
                "best_for": _clean(review.get("best_for")),
                "avoid_for": _clean(review.get("avoid_for")),
            }
            name_key = _norm_name(row.get("name"))
            if name_key:
                by_name[name_key] = copy
            for raw_url in (row.get("primary_url"), row.get("url")):
                url_key = _norm_url(raw_url)
                if url_key:
                    by_url[url_key] = copy
    return {"by_url": by_url, "by_name": by_name}


def review_copy_for_state(
    state: dict[str, Any], index: dict[str, dict[str, dict[str, str]]]
) -> dict[str, str]:
    url_key = _norm_url(state.get("primary_url"))
    if url_key and url_key in index.get("by_url", {}):
        return index["by_url"][url_key]
    name_key = _norm_name(state.get("name"))
    if name_key and name_key in index.get("by_name", {}):
        return index["by_name"][name_key]
    return {}


def _specific_risk_from_rationale(rationale: str) -> str:
    text = _humanize_terms(rationale)
    for separator in ("が、", "だが、", "一方で、", "ただし、"):
        if separator not in text:
            continue
        tail = text.rsplit(separator, 1)[-1].strip()
        if len(tail) >= 12:
            return tail if tail.endswith(("。", "！", "？")) else tail + "。"
    return ""


def _natural_reason_from_risk(status: str, risk: str) -> str:
    risk = _humanize_terms(risk).rstrip("。！？")
    if not risk:
        return ""
    if status == "TEST":
        return f"{risk}。そのため、本番導入の前に小さく試して確認します。"
    if status == "WATCH":
        return f"{risk}。今は導入を急がず、変化を追うのがよいでしょう。"
    if status == "AVOID":
        return f"{risk}。新規採用は見送るのが安全です。"
    return risk + "。"


def _natural_action(state: dict[str, Any]) -> str:
    status = _clean(state.get("status"))
    classification = _clean(state.get("classification"))
    if status == "ADOPT":
        return "導入前に、自社の要件・費用・運用体制に合うかを最終確認する。"
    if status == "TEST":
        return "実際の業務を1つ選び、小さく試して品質・費用・運用負荷を確認する。"
    if status == "WATCH" and classification == "Deep Tech":
        return "今すぐ導入はせず、自社に関係する用途が出たときに最新の研究結果を確認する。"
    if status == "WATCH":
        return "今は導入せず、保守状況や後継版の動きが変わったときに再確認する。"
    if status == "AVOID":
        return "新規採用は見送り、現在も保守されている代替候補を比較する。"
    return "必要な条件を確認してから次の判断へ進む。"


def humanize_state(
    state: dict[str, Any], review_copy: dict[str, str] | None = None
) -> dict[str, Any]:
    """Return the same decision state with customer-language presentation copy."""
    review_copy = review_copy or {}
    out = dict(state)

    reviewed_summary = _clean(review_copy.get("plain_summary"))
    out["plain_summary"] = _humanize_terms(reviewed_summary or out.get("plain_summary"))

    current_topic = _clean(out.get("topic"))
    reviewed_topic = _humanize_terms(review_copy.get("topic_trigger"))
    if reviewed_topic and (not current_topic or GENERIC_TOPIC_RE.match(current_topic)):
        out["topic"] = reviewed_topic
    else:
        out["topic"] = _humanize_terms(current_topic)

    current_reason = _clean(out.get("judgment_reason"))
    reviewed_reason = _humanize_terms(review_copy.get("short_rationale"))
    if reviewed_reason and (
        not current_reason
        or BAD_REASON_RE.search(current_reason)
        or _clean(out.get("classification")) == "Deep Tech"
    ):
        out["judgment_reason"] = reviewed_reason
    else:
        out["judgment_reason"] = _humanize_terms(current_reason)

    current_risk = _humanize_terms(out.get("main_risk"))
    reviewed_risk = _humanize_terms(review_copy.get("main_risk"))
    generic_risk = _humanize_terms(GENERIC_DEEP_RISK)
    if _clean(out.get("classification")) == "Deep Tech" and current_risk == generic_risk:
        specific = _specific_risk_from_rationale(review_copy.get("short_rationale") or "")
        out["main_risk"] = specific
    else:
        out["main_risk"] = current_risk or reviewed_risk

    out["best_for"] = _humanize_terms(out.get("best_for"))
    out["avoid_for"] = _humanize_terms(out.get("avoid_for"))
    if _clean(out.get("classification")) == "Deep Tech":
        if _clean(out.get("best_for")) == _humanize_terms(GENERIC_DEEP_BEST):
            out["best_for"] = ""
        if _clean(out.get("avoid_for")) == _humanize_terms(GENERIC_DEEP_AVOID):
            out["avoid_for"] = ""

    # Repair malformed causal copy even when no external review match exists.
    if BAD_REASON_RE.search(_clean(out.get("judgment_reason"))):
        out["judgment_reason"] = _natural_reason_from_risk(
            _clean(out.get("status")), _clean(out.get("main_risk"))
        ) or _humanize_terms(out.get("topic"))

    action = _humanize_terms(out.get("next_action"))
    if not action or action in OLD_GENERIC_ACTIONS:
        action = _natural_action(out)
    out["next_action"] = action

    out["change_reason"] = _humanize_terms(out.get("change_reason"))
    return out


def install_human_language_guard() -> tuple[dict[str, int], dict[str, int]]:
    """Install Run169 summary guard, then add Run170 language transformations."""
    summary_stats = guard.install_presentation_guard()
    guarded_source_state = mps._source_state
    index = load_review_copy_index()
    stats = {
        "review_copy_used": 0,
        "generic_topics_removed": 0,
        "bad_reasons_removed": 0,
        "deep_boilerplate_removed": 0,
    }

    def human_source_state(page: dict[str, Any]) -> dict[str, Any] | None:
        state = guarded_source_state(page)
        if not state:
            return None
        before_topic = _clean(state.get("topic"))
        before_reason = _clean(state.get("judgment_reason"))
        before_generic_fields = sum(
            1
            for value, generic in (
                (state.get("main_risk"), GENERIC_DEEP_RISK),
                (state.get("best_for"), GENERIC_DEEP_BEST),
                (state.get("avoid_for"), GENERIC_DEEP_AVOID),
            )
            if _clean(value) == _clean(generic)
        )
        reviewed = review_copy_for_state(state, index)
        if reviewed:
            stats["review_copy_used"] += 1
        state = humanize_state(state, reviewed)
        if before_topic and GENERIC_TOPIC_RE.match(before_topic) and _clean(state.get("topic")) != before_topic:
            stats["generic_topics_removed"] += 1
        if BAD_REASON_RE.search(before_reason) and not BAD_REASON_RE.search(_clean(state.get("judgment_reason"))):
            stats["bad_reasons_removed"] += 1
        after_generic_fields = sum(
            1
            for value, generic in (
                (state.get("main_risk"), _humanize_terms(GENERIC_DEEP_RISK)),
                (state.get("best_for"), _humanize_terms(GENERIC_DEEP_BEST)),
                (state.get("avoid_for"), _humanize_terms(GENERIC_DEEP_AVOID)),
            )
            if _clean(value) == _clean(generic)
        )
        stats["deep_boilerplate_removed"] += max(0, before_generic_fields - after_generic_fields)
        return state

    mps._source_state = human_source_state
    return summary_stats, stats


def run_presentation_sync() -> dict[str, Any]:
    summary_stats, language_stats = install_human_language_guard()
    result = mps.sync_member_presentation()
    result["summary_guard"] = summary_stats
    result["human_language"] = language_stats
    result["homepage_contract"] = guard.HOME_SHORTLIST_SIZE
    result["zero_gemini_calls"] = True
    if summary_stats.get("missing"):
        raise RuntimeError("Member summary guard left missing summaries")
    if result.get("source_records", 0) >= guard.HOME_SHORTLIST_SIZE and result.get("homepage_count") != guard.HOME_SHORTLIST_SIZE:
        raise RuntimeError(
            f"Member homepage contract mismatch: expected {guard.HOME_SHORTLIST_SIZE}, got {result.get('homepage_count')}"
        )
    return result


def _human_status_summary(state: dict[str, Any]) -> str:
    status = _clean(state.get("status")) or "—"
    label = STATUS_HUMAN.get(status, "要確認")
    score = state.get("score")
    score_text = f"{int(score)}点" if isinstance(score, (int, float)) and not isinstance(score, bool) else "—"
    readiness = _clean(state.get("readiness")) or "—"
    confidence = _clean(state.get("confidence")) or "—"
    return f"{label}（{status}）｜{score_text}｜実用度 {readiness}｜根拠 {confidence}"


def _human_build_children(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Reader order: understand the item first, then decide what to do."""
    children: list[dict[str, Any]] = []
    status = _clean(state.get("status"))

    summary = _clean(state.get("plain_summary"))
    if summary:
        children.append(body._heading("これは何？"))
        children.append(body._paragraph(summary))

    children.append(body._heading("いまの判断"))
    children.append(body._paragraph(_human_status_summary(state)))

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
        children.append(body._heading("判断理由"))
        children.append(body._paragraph(reason))

    risk = _clean(state.get("main_risk"))
    if risk:
        children.append(body._heading("主なリスク"))
        children.append(body._paragraph(risk))

    best_for = _clean(state.get("best_for"))
    if best_for:
        children.append(body._heading("向いている用途"))
        children.append(body._paragraph(best_for))

    avoid_for = _clean(state.get("avoid_for"))
    if avoid_for:
        children.append(body._heading("向いていない用途"))
        children.append(body._paragraph(avoid_for))

    change_reason = _clean(state.get("change_reason"))
    if change_reason:
        children.append(body._heading("評価が変わった理由"))
        children.append(body._paragraph(change_reason))

    evidence = _clean(state.get("evidence"))
    primary_url = _clean(state.get("primary_url"))
    related_article = _clean(state.get("related_article"))
    urls = body._extract_urls(evidence, primary_url)
    if urls or related_article:
        children.append(body._heading("確認した一次情報"))
        for index, url in enumerate(urls[:5], 1):
            children.append(body._link_paragraph(f"一次情報 {index}", url))
        if related_article:
            children.append(body._link_paragraph("関連記事", related_article))
    return children


def _looks_like_human_generated_callout(
    block: dict[str, Any], child_cache: dict[str, list[dict[str, Any]]]
) -> bool:
    if block.get("type") != "callout" or body._block_text(block) != guard.VISIBLE_CALLOUT_LABEL:
        return False
    block_id = str(block.get("id") or "")
    if not block_id:
        return False
    children = child_cache.setdefault(block_id, body._children(block_id))
    headings = guard._heading_texts(children)
    has_decision = "いまの判断" in headings or "結論" in headings
    return has_decision and "次にやること" in headings and "判断理由" in headings


def install_human_body_builder() -> None:
    body._build_children = _human_build_children
    guard._looks_like_generated_visible_callout = _looks_like_human_generated_callout


def run_body_sync() -> dict[str, Any]:
    install_human_body_builder()
    result = body_fast.sync_member_page_bodies_fast()
    result["reader_order"] = ["これは何？", "いまの判断", "なぜ今見る？", "次にやること"]
    result["zero_gemini_calls"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1 or args[0] not in {"presentation", "body"}:
        raise SystemExit("usage: python member_human_language_ux.py [presentation|body]")
    result = run_presentation_sync() if args[0] == "presentation" else run_body_sync()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
