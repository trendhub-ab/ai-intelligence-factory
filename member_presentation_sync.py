#!/usr/bin/env python3
"""Clean member-facing presentation sync for AI Decision Intelligence.

The existing Subscriber Technology DB remains the compatibility bridge used by
the Factory. This module copies only reader-facing Japanese information into a
separate presentation DB.

Principles:
- ZERO Gemini/model requests.
- One real title property: ``AI・技術名``.
- ``今回の話題`` / ``判断理由`` / ``評価が変わった理由`` have distinct roles.
- ``次にやること`` must be an executable action, not another evaluation sentence.
- Generic Factory boilerplate is removed from member copy.
- Homepage recommendations are capped and only diversified among near-ties.
- Durable change memory comes from the bridge DB's important-change fields.
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests

import decision_intelligence


# Production workflows resolve these IDs during the provision step.  Empty
# defaults are deliberate: a developer invocation must not silently write to an
# obsolete/test database.
NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID = os.environ.get(
    "NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID", ""
).strip()
NOTION_MEMBER_PRESENTATION_DATABASE_ID = os.environ.get(
    "NOTION_MEMBER_PRESENTATION_DATABASE_ID", ""
).strip()
MEMBER_HOME_MAX = max(1, min(12, int(os.environ.get("MEMBER_HOME_MAX", "8"))))
MEMBER_HOME_DIVERSITY_TOLERANCE = max(
    0.0, float(os.environ.get("MEMBER_HOME_DIVERSITY_TOLERANCE", "0.5"))
)

GENERIC_RISK_SUFFIX = "導入前に対象環境と実データでこの条件を確認し、運用責任者を決める必要がある。"
GENERIC_BEST_SUFFIX = "採用時は小さな実案件で効果と運用負荷を同時に測る。"
GENERIC_AVOID_SUFFIX = "この条件に当てはまる場合は、より単純または現行の別候補を優先する。"
GENERIC_RATIONALE_SUFFIX = "一次情報の現状を前提に、用途・保守性・運用コストまで含めて判断する。"

CONFIDENCE_JA = {"HIGH": "高", "MEDIUM": "中", "LOW": "低"}
READINESS_JA = {"HIGH": "高", "MEDIUM": "中", "LOW": "低"}
CATEGORY_JA = {
    "MODEL": "AIモデル",
    "AGENT": "エージェント",
    "DEVTOOLS": "開発ツール",
    "INFRA": "基盤",
    "DATA": "データ",
    "SECURITY": "セキュリティ",
    "MULTIMODAL": "マルチモーダル",
    "PRODUCT": "製品・サービス",
    "OTHER": "その他",
}

PUBLIC_SCHEMA = {
    "AI・技術名": "title",
    "これは何？": "rich_text",
    "判断": "select",
    "判断スコア": "number",
    "判断理由": "rich_text",
    "今回の話題": "rich_text",
    "次にやること": "rich_text",
    "主なリスク": "rich_text",
    "向いている用途": "rich_text",
    "向いていない用途": "rich_text",
    "根拠の確かさ": "select",
    "実用度": "select",
    "分野": "select",
    "分類": "select",
    "評価の変化": "number",
    "評価が変わった理由": "rich_text",
    "重要変化日": "date",
    "最終確認日": "date",
    "見つけた日": "date",
    "一次情報": "rich_text",
    "関連記事": "url",
    "公式ページ": "url",
    "情報源": "multi_select",
    "注目順位": "number",
    "今月の重要変化": "checkbox",
    "同期ID": "rich_text",
}

_ACTION_END_RE = re.compile(
    r"(?:確認|検証|評価|比較|実装|運用|設計|計画|固定|監視|再評価|再選定|"
    r"切り替|移行|導入|試験|テスト|測定|測る|試す|選ぶ|決める|絞る|移す|"
    r"待つ|追う|行う|進める|見送る|優先する)(?:する|します|した|して)?[。！？]?$"
)
_DECLARATIVE_MARKERS = (
    "候補", "価値が高い", "完成度", "優先度が高い", "成熟しています",
    "成熟している", "対応しています", "対応している", "提供しています",
    "提供している", "備えています", "備えている", "重要です", "重要である",
)


def _plain_text(values: list[dict] | None) -> str:
    return "".join(
        str(x.get("plain_text") or ((x.get("text") or {}).get("content")) or "")
        for x in (values or [])
    ).strip()


def _text(prop: dict | None) -> str:
    prop = prop or {}
    if prop.get("title") is not None:
        return _plain_text(prop.get("title"))
    if prop.get("rich_text") is not None:
        return _plain_text(prop.get("rich_text"))
    formula = prop.get("formula") or {}
    if isinstance(formula.get("string"), str):
        return formula["string"].strip()
    return ""


def _number(prop: dict | None) -> int | float | None:
    prop = prop or {}
    value = prop.get("number")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    value = (prop.get("formula") or {}).get("number")
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _select(prop: dict | None) -> str:
    return str(((prop or {}).get("select") or {}).get("name") or "").strip()


def _multi_select(prop: dict | None) -> list[str]:
    return sorted(
        {
            str(x.get("name") or "").strip()
            for x in ((prop or {}).get("multi_select") or [])
            if x.get("name")
        }
    )


def _date(prop: dict | None) -> str | None:
    value = ((prop or {}).get("date") or {}).get("start")
    return str(value).strip() if value else None


def _url(prop: dict | None) -> str:
    return str((prop or {}).get("url") or "").strip()


def _checkbox(prop: dict | None) -> bool:
    return bool((prop or {}).get("checkbox"))


def _norm(text: str) -> str:
    text = str(text or "").replace("<br>", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _norm_key(text: str) -> str:
    return re.sub(r"[\W_]+", "", _norm(text)).casefold()


def _strip_suffix(text: str, suffix: str) -> str:
    text = _norm(text)
    suffix = _norm(suffix)
    if text.endswith(suffix):
        text = text[: -len(suffix)].rstrip()
    return text


def _sentences(text: str) -> list[str]:
    text = _norm(text)
    if not text:
        return []
    return [x.strip() for x in re.split(r"(?<=[。！？])\s*", text) if x.strip()]


def _is_action_sentence(sentence: str) -> bool:
    sentence = _norm(sentence)
    return bool(sentence and _ACTION_END_RE.search(sentence))


def clean_risk(text: str) -> str:
    return _strip_suffix(text, GENERIC_RISK_SUFFIX)


def clean_best_for(text: str) -> str:
    return _strip_suffix(text, GENERIC_BEST_SUFFIX)


def clean_avoid_for(text: str) -> str:
    return _strip_suffix(text, GENERIC_AVOID_SUFFIX)


def _clean_rationale(text: str) -> str:
    return _strip_suffix(text, GENERIC_RATIONALE_SUFFIX)


def _fallback_action(status: str) -> str:
    return {
        "ADOPT": "導入候補として、自社要件との適合と運用条件を最終確認する。",
        "TEST": "代表業務を1つ選び、小さく試して効果と運用負荷を確認する。",
        "WATCH": "次回レビューまで監視し、成熟度・保守状況の変化を確認する。",
        "AVOID": "新規採用は見送り、保守中の代替候補を比較する。",
    }.get(status, "必要な条件を確認してから次の判断へ進む。")


def _action_score(sentence: str, status: str) -> int:
    sentence = _norm(sentence)
    if not sentence:
        return -99
    if not _is_action_sentence(sentence):
        return -20
    terms = {
        "ADOPT": ("確認", "導入", "固定", "測", "運用", "比較", "検証", "決め"),
        "TEST": ("実装", "試", "検証", "確認", "測", "評価", "比較", "テスト"),
        "WATCH": ("待", "監視", "確認", "再評価", "追", "移行", "成熟"),
        "AVOID": ("移", "比較", "代替", "再選定", "切り替", "見送", "優先"),
    }.get(status, ("確認", "比較", "検証"))
    score = 8 + sum(3 for term in terms if term in sentence)
    if "判断点は" in sentence:
        score -= 2
    if any(marker in sentence for marker in _DECLARATIVE_MARKERS):
        score -= 5
    if sentence in {"新規採用は見送り。", "まず小さく試す。", "本格導入を検討してよい。"}:
        score -= 10
    return score


def derive_next_action(status: str, rationale: str, topic: str = "") -> str:
    rationale = _clean_rationale(rationale)
    candidates = _sentences(rationale)
    if topic:
        candidates.extend(x for x in _sentences(topic) if x not in candidates)
    actionable = [x for x in candidates if _is_action_sentence(x)]
    if not actionable:
        return _fallback_action(status)
    best = max(actionable, key=lambda x: _action_score(x, status))
    if _action_score(best, status) < 5:
        return _fallback_action(status)
    best = best.replace("判断点は、", "").replace("判断点は", "").lstrip("、,:： ").strip()
    return best or _fallback_action(status)


def clean_topic_trigger(text: str, *, name: str = "", action: str = "") -> str:
    """Keep current context, excluding judgment/action tails where possible."""
    text = _norm(text)
    if not text:
        return f"{name}の現在の機能・保守状況を確認しています。" if name else ""
    if "判断点は" in text:
        before = text.split("判断点は", 1)[0].rstrip(" 、,:：。")
        if before:
            text = before + ("。" if before[-1] not in "。！？" else "")
    sentences = _sentences(text)
    deduped: list[str] = []
    seen: set[str] = set()
    for sentence in sentences:
        key = _norm_key(sentence)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(sentence)
    if action:
        action_key = _norm_key(action)
        without_action = [s for s in deduped if _norm_key(s) != action_key]
        if without_action:
            deduped = without_action
    # If there is at least one descriptive sentence, remove imperative/action
    # sentences from the topic field. This keeps Mastra-like "what/why now" copy
    # separate from the concrete next step.
    descriptive = [s for s in deduped if not _is_action_sentence(s)]
    if descriptive:
        deduped = descriptive
    result = _norm("".join(deduped))
    if not result and name:
        return f"{name}の現在の機能・保守状況を確認しています。"
    return result


def _status_reason_from_risk(status: str, risk: str) -> str:
    risk = clean_risk(risk)
    if not risk:
        return ""
    base = risk.rstrip("。！？")
    if status == "AVOID":
        return f"{base}ため、新規採用は見送る判断が妥当です。"
    if status == "WATCH":
        return f"{base}ため、現時点では導入を急がず状況を追う判断が妥当です。"
    if status == "TEST":
        return f"{base}ため、本番採用の前に小さく検証する判断が妥当です。"
    return risk


def derive_judgment_reason(
    status: str,
    rationale: str,
    topic: str,
    main_risk: str,
    action: str = "",
) -> str:
    """Explain the current judgment rather than restating the topic/action."""
    rationale = _clean_rationale(rationale)
    action_key = _norm_key(action)
    candidates = []
    for sentence in _sentences(rationale):
        if action_key and _norm_key(sentence) == action_key:
            continue
        if _is_action_sentence(sentence):
            continue
        if sentence in {"新規採用は見送り。", "まず小さく試す。", "本格導入を検討してよい。"}:
            continue
        candidates.append(sentence)
    topical = clean_topic_trigger(topic, action=action)
    for candidate in candidates:
        if _norm_key(candidate) != _norm_key(topical):
            return candidate
    # If the only rationale is effectively the topic, use the risk-based causal
    # explanation for TEST/WATCH/AVOID instead of showing duplicate properties.
    if status in {"TEST", "WATCH", "AVOID"}:
        risk_reason = _status_reason_from_risk(status, main_risk)
        if risk_reason:
            return risk_reason
    if candidates:
        candidate = candidates[0]
        if status == "ADOPT":
            return candidate
        return candidate
    if topical:
        return topical
    return clean_risk(main_risk)


def clean_change_reason(
    reason: str,
    delta: int | float | None,
    *,
    action: str = "",
) -> str:
    reason = _norm(reason)
    if not reason or delta is None or abs(float(delta)) < decision_intelligence.MEANINGFUL_SCORE_DELTA:
        return ""
    if "判断点は" in reason:
        before = reason.split("判断点は", 1)[0].rstrip(" 、,:：。")
        if before:
            reason = before + ("。" if before[-1] not in "。！？" else "")
    sentences = _sentences(reason)
    if action:
        action_key = _norm_key(action)
        kept = [s for s in sentences if _norm_key(s) != action_key]
        if kept:
            sentences = kept
    descriptive = [s for s in sentences if not _is_action_sentence(s)]
    if descriptive:
        sentences = descriptive
    reason = _norm("".join(sentences))
    if not reason:
        return ""
    if reason.startswith("前回より評価"):
        return reason
    direction = "上がった" if float(delta) > 0 else "下がった"
    return f"前回より評価が{direction}のは、{reason}"


def _strip_review_suffix(label: str) -> str:
    label = _norm(label)
    return re.sub(r"\s*[—–-]\s*判断用レビュー\s*$", "", label).strip()


def _source_state(page: dict) -> dict[str, Any] | None:
    p = page.get("properties") or {}
    sync_id = _text(p.get("正規エンティティID"))
    if not sync_id:
        return None
    raw_name = _text(p.get("技術・プロジェクト名"))
    name = (
        _text(p.get("AI・技術名"))
        or _strip_review_suffix(_text(p.get("日本語表示名")))
        or raw_name
    )
    status = _select(p.get("採用判断（内部）"))
    score = _number(p.get("採用スコア（内部）"))
    confidence_raw = _select(p.get("根拠信頼度（内部）"))
    readiness_raw = _select(p.get("実用準備度（内部）"))
    category_raw = _select(p.get("分野（内部）")) or "OTHER"
    rationale_raw = _text(p.get("判断理由（内部）"))
    topic_raw = _text(p.get("今回の話題（内部）"))
    main_risk_raw = _text(p.get("主リスク（内部）"))
    delta = _number(p.get("評価の変化"))
    important_at = _date(p.get("重要変化日"))
    important_reason_raw = _text(p.get("評価が変わった理由"))
    classification = _text(p.get("会員向け棚")) or "実務判断"

    action = derive_next_action(status, rationale_raw, topic_raw)
    topic = clean_topic_trigger(topic_raw, name=name, action=action)
    reason = derive_judgment_reason(status, rationale_raw, topic_raw, main_risk_raw, action)
    return {
        "sync_id": sync_id,
        "name": name,
        "plain_summary": _text(p.get("これは何？")) or _text(p.get("わかりやすい要約（内部）")),
        "status": status,
        "score": score,
        "judgment_reason": reason,
        "topic": topic,
        "next_action": action,
        "main_risk": clean_risk(main_risk_raw),
        "best_for": clean_best_for(_text(p.get("向いている用途（内部）"))),
        "avoid_for": clean_avoid_for(_text(p.get("向いていない用途（内部）"))),
        "confidence": CONFIDENCE_JA.get(confidence_raw, "中"),
        "readiness": READINESS_JA.get(readiness_raw, "中"),
        "category": CATEGORY_JA.get(category_raw, "その他"),
        "classification": (
            classification
            if classification in {"実務判断", "Deep Tech", "参考資料"}
            else "実務判断"
        ),
        "delta": delta,
        "change_reason": clean_change_reason(important_reason_raw, delta, action=action),
        "important_at": important_at,
        "last_reviewed": _date(p.get("最終レビュー日（内部）")),
        "first_seen": _date(p.get("初回発見日（内部）")),
        "evidence": _norm(_text(p.get("一次情報URL（内部）"))),
        "related_article": _url(p.get("関連記事（内部）")),
        "primary_url": _url(p.get("公式URL")),
        "sources": _multi_select(p.get("情報源（内部）")),
        "rank": None,
        "current_month_change": False,
    }


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def mark_current_month_changes(
    states: list[dict[str, Any]], *, now: datetime | None = None
) -> None:
    tz = ZoneInfo(decision_intelligence.PRODUCT_TIMEZONE)
    now_local = (now or datetime.now(timezone.utc)).astimezone(tz)
    for state in states:
        changed = _parse_dt(state.get("important_at"))
        state["current_month_change"] = bool(
            changed
            and (changed.astimezone(tz).year, changed.astimezone(tz).month)
            == (now_local.year, now_local.month)
        )


def assign_home_ranks(
    states: list[dict[str, Any]], *, limit: int = MEMBER_HOME_MAX
) -> list[dict[str, Any]]:
    """Rank practical choices; diversity may reorder only genuinely near-tied items."""
    for state in states:
        state["rank"] = None
    remaining = [
        s
        for s in states
        if s.get("classification") == "実務判断"
        and s.get("status") in {"ADOPT", "TEST"}
        and s.get("confidence") != "低"
        and isinstance(s.get("score"), (int, float))
    ]

    def merit(state: dict[str, Any]) -> float:
        value = float(state.get("score") or 0)
        if state.get("confidence") == "高":
            value += 1.5
        if state.get("readiness") == "高":
            value += 1.0
        if (
            state.get("current_month_change")
            and isinstance(state.get("delta"), (int, float))
            and float(state["delta"]) >= 5
        ):
            value += 1.0
        return value

    selected: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}
    while remaining and len(selected) < max(1, limit):
        strongest = max(
            remaining,
            key=lambda s: (merit(s), float(s.get("score") or 0), s.get("name") or ""),
        )
        floor = merit(strongest) - MEMBER_HOME_DIVERSITY_TOLERANCE
        competitive = [s for s in remaining if merit(s) >= floor]
        winner = max(
            competitive,
            key=lambda s: (
                -category_counts.get(str(s.get("category") or "その他"), 0),
                merit(s),
                float(s.get("score") or 0),
                str(s.get("name") or ""),
            ),
        )
        selected.append(winner)
        category = str(winner.get("category") or "その他")
        category_counts[category] = category_counts.get(category, 0) + 1
        remaining.remove(winner)
    for rank, state in enumerate(selected, 1):
        state["rank"] = rank
    return selected


def _rt(value: str) -> dict:
    value = _norm(value)[:2000]
    return (
        {"rich_text": []}
        if not value
        else {"rich_text": [{"type": "text", "text": {"content": value}}]}
    )


def _title(value: str) -> dict:
    value = _norm(value)[:2000] or "名称未設定"
    return {"title": [{"type": "text", "text": {"content": value}}]}


def _sel(value: str) -> dict:
    return {"select": {"name": value}} if value else {"select": None}


def _num(value: int | float | None) -> dict:
    return {
        "number": value
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else None
    }


def _date_prop(value: str | None) -> dict:
    return {"date": {"start": value}} if value else {"date": None}


def _props(state: dict[str, Any]) -> dict[str, dict]:
    return {
        "AI・技術名": _title(state.get("name") or ""),
        "これは何？": _rt(state.get("plain_summary") or ""),
        "判断": _sel(state.get("status") or ""),
        "判断スコア": _num(state.get("score")),
        "判断理由": _rt(state.get("judgment_reason") or ""),
        "今回の話題": _rt(state.get("topic") or ""),
        "次にやること": _rt(state.get("next_action") or ""),
        "主なリスク": _rt(state.get("main_risk") or ""),
        "向いている用途": _rt(state.get("best_for") or ""),
        "向いていない用途": _rt(state.get("avoid_for") or ""),
        "根拠の確かさ": _sel(state.get("confidence") or ""),
        "実用度": _sel(state.get("readiness") or ""),
        "分野": _sel(state.get("category") or "その他"),
        "分類": _sel(state.get("classification") or "実務判断"),
        "評価の変化": _num(state.get("delta")),
        "評価が変わった理由": _rt(state.get("change_reason") or ""),
        "重要変化日": _date_prop(state.get("important_at")),
        "最終確認日": _date_prop(state.get("last_reviewed")),
        "見つけた日": _date_prop(state.get("first_seen")),
        "一次情報": _rt(state.get("evidence") or ""),
        "関連記事": {"url": state.get("related_article") or None},
        "公式ページ": {"url": state.get("primary_url") or None},
        "情報源": {
            "multi_select": [{"name": x} for x in (state.get("sources") or [])]
        },
        "注目順位": _num(state.get("rank")),
        "今月の重要変化": {"checkbox": bool(state.get("current_month_change"))},
        "同期ID": _rt(state.get("sync_id") or ""),
    }


def _destination_state(page: dict) -> dict[str, Any]:
    p = page.get("properties") or {}
    return {
        "page_id": str(page.get("id") or ""),
        "sync_id": _text(p.get("同期ID")),
        "name": _text(p.get("AI・技術名")),
        "plain_summary": _text(p.get("これは何？")),
        "status": _select(p.get("判断")),
        "score": _number(p.get("判断スコア")),
        "judgment_reason": _text(p.get("判断理由")),
        "topic": _text(p.get("今回の話題")),
        "next_action": _text(p.get("次にやること")),
        "main_risk": _text(p.get("主なリスク")),
        "best_for": _text(p.get("向いている用途")),
        "avoid_for": _text(p.get("向いていない用途")),
        "confidence": _select(p.get("根拠の確かさ")),
        "readiness": _select(p.get("実用度")),
        "category": _select(p.get("分野")),
        "classification": _select(p.get("分類")),
        "delta": _number(p.get("評価の変化")),
        "change_reason": _text(p.get("評価が変わった理由")),
        "important_at": _date(p.get("重要変化日")),
        "last_reviewed": _date(p.get("最終確認日")),
        "first_seen": _date(p.get("見つけた日")),
        "evidence": _text(p.get("一次情報")),
        "related_article": _url(p.get("関連記事")),
        "primary_url": _url(p.get("公式ページ")),
        "sources": _multi_select(p.get("情報源")),
        "rank": _number(p.get("注目順位")),
        "current_month_change": _checkbox(p.get("今月の重要変化")),
    }


def _comparable(state: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "sync_id",
        "name",
        "plain_summary",
        "status",
        "score",
        "judgment_reason",
        "topic",
        "next_action",
        "main_risk",
        "best_for",
        "avoid_for",
        "confidence",
        "readiness",
        "category",
        "classification",
        "delta",
        "change_reason",
        "important_at",
        "last_reviewed",
        "first_seen",
        "evidence",
        "related_article",
        "primary_url",
        "sources",
        "rank",
        "current_month_change",
    )
    out = {key: state.get(key) for key in keys}
    out["sources"] = sorted(out.get("sources") or [])
    for key in (
        "name",
        "plain_summary",
        "judgment_reason",
        "topic",
        "next_action",
        "main_risk",
        "best_for",
        "avoid_for",
        "change_reason",
        "evidence",
    ):
        out[key] = _norm(out.get(key) or "")
    return out


def _validate_destination_schema() -> None:
    res = requests.get(
        decision_intelligence._schema_url(
            NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID,
            NOTION_MEMBER_PRESENTATION_DATABASE_ID,
        ),
        headers=decision_intelligence._headers(),
        timeout=20,
    )
    res.raise_for_status()
    props = res.json().get("properties") or {}
    missing = [name for name in PUBLIC_SCHEMA if name not in props]
    wrong = [
        f"{name}:{(props.get(name) or {}).get('type')}"
        for name, expected in PUBLIC_SCHEMA.items()
        if name in props and (props.get(name) or {}).get("type") != expected
    ]
    if missing or wrong:
        raise ValueError(
            f"Member presentation schema incompatible: missing={missing} wrong={wrong}"
        )


def _write(method: str, url: str, *, json: dict) -> requests.Response:
    for attempt in range(5):
        res = requests.request(
            method,
            url,
            json=json,
            headers=decision_intelligence._headers(),
            timeout=25,
        )
        if res.status_code == 429:
            time.sleep(max(0.8, float(res.headers.get("Retry-After") or 1.0)))
            continue
        if 500 <= res.status_code < 600 and attempt < 4:
            time.sleep(1.0 + attempt)
            continue
        return res
    return res


def sync_member_presentation() -> dict[str, Any]:
    if not decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY:
        raise ValueError("NOTION_DECISION_INTELLIGENCE_API_KEY is required")
    if not (
        decision_intelligence.NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID
        or decision_intelligence.NOTION_SUBSCRIBER_TECH_DATABASE_ID
    ):
        raise ValueError("Subscriber Technology DB is not configured")
    if not (
        NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID
        or NOTION_MEMBER_PRESENTATION_DATABASE_ID
    ):
        raise ValueError("Member presentation DB is not configured")

    _validate_destination_schema()
    source_pages = decision_intelligence._query_external_db(
        decision_intelligence.NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID,
        decision_intelligence.NOTION_SUBSCRIBER_TECH_DATABASE_ID,
        max_records=5000,
    )
    states = [state for state in (_source_state(page) for page in source_pages) if state]
    mark_current_month_changes(states)
    selected = assign_home_ranks(states)

    destination_pages = decision_intelligence._query_external_db(
        NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID,
        NOTION_MEMBER_PRESENTATION_DATABASE_ID,
        max_records=5000,
    )
    dest_by_id: dict[str, dict[str, Any]] = {}
    for page in destination_pages:
        state = _destination_state(page)
        if state.get("sync_id") and state["sync_id"] not in dest_by_id:
            dest_by_id[state["sync_id"]] = state

    created = updated = unchanged = archived = 0
    source_ids: set[str] = set()
    for state in states:
        sync_id = state["sync_id"]
        source_ids.add(sync_id)
        current = dest_by_id.get(sync_id)
        if current and _comparable(current) == _comparable(state):
            unchanged += 1
            continue
        if current:
            res = _write(
                "PATCH",
                f"https://api.notion.com/v1/pages/{current['page_id']}",
                json={"properties": _props(state)},
            )
            if res.status_code != 200:
                raise RuntimeError(
                    f"Member presentation update failed {sync_id}: "
                    f"{res.status_code} {res.text[:500]}"
                )
            updated += 1
        else:
            parent = decision_intelligence._parent(
                NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID,
                NOTION_MEMBER_PRESENTATION_DATABASE_ID,
            )
            res = _write(
                "POST",
                "https://api.notion.com/v1/pages",
                json={"parent": parent, "properties": _props(state)},
            )
            if res.status_code != 200:
                raise RuntimeError(
                    f"Member presentation create failed {sync_id}: "
                    f"{res.status_code} {res.text[:500]}"
                )
            created += 1
        time.sleep(0.34)

    for sync_id, current in dest_by_id.items():
        if sync_id in source_ids:
            continue
        res = _write(
            "PATCH",
            f"https://api.notion.com/v1/pages/{current['page_id']}",
            json={"archived": True},
        )
        if res.status_code != 200:
            raise RuntimeError(
                f"Member presentation archive failed {sync_id}: "
                f"{res.status_code} {res.text[:500]}"
            )
        archived += 1
        time.sleep(0.34)

    return {
        "enabled": True,
        "zero_gemini_calls": True,
        "source_records": len(states),
        "homepage_count": len(selected),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "archived": archived,
        "destination_data_source_id": NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID,
    }


def main() -> None:
    print(sync_member_presentation())


if __name__ == "__main__":
    main()
