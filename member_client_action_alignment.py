"""Run253 work-first paid-product alignment.

This is a deterministic presentation policy. It does not change source Evidence,
scores, decisions, or canonical records. It answers a narrower product question:
which already-qualified technologies are most relevant to a small operator who
wants to understand what is worth using in their own work?

Initial ICP:
- 1–3 person operators in web, marketing, business improvement, creative work, etc.
- actively want to use AI in their own work
- choose/test/adopt tools themselves
- client proposals are a secondary reuse case, not the core product purpose

The broad Intelligence Engine remains intact. This module only determines what
should be surfaced first and how existing authoritative fields should be framed.
ZERO model/provider calls.
"""
from __future__ import annotations

import re
from typing import Any

ICP_LABEL = (
    "Web制作・マーケティング・業務改善・クリエイティブなどでAIを仕事に活用する"
    "1〜3名規模の事業者で、自分でツールを選び、試し、導入判断をする人"
)

CATEGORY_BASE = {
    "製品・サービス": 74.0,
    "エージェント": 69.0,
    "マルチモーダル": 67.0,
    "開発ツール": 62.0,
    "セキュリティ": 50.0,
    "データ": 44.0,
    "AIモデル": 44.0,
    "基盤": 28.0,
    "その他": 46.0,
}

# Generic work-use signals, not product-name allowlists. New products can rank
# without a code change. Client-facing terms remain small positive signals because
# they can matter to the ICP, but they are no longer the ranking centre.
POSITIVE_SIGNALS: tuple[tuple[str, float], ...] = (
    ("web制作", 10),
    ("制作", 8),
    ("マーケ", 8),
    ("業務改善", 10),
    ("自動化", 10),
    ("ワークフロー", 8),
    ("ブラウザ", 9),
    ("faq", 7),
    ("問い合わせ", 7),
    ("文書検索", 8),
    ("資料検索", 8),
    ("検索", 4),
    ("要約", 5),
    ("調査", 6),
    ("aiアプリ", 8),
    ("ノーコード", 8),
    ("ローコード", 8),
    ("画像", 7),
    ("動画", 7),
    ("デザイン", 7),
    ("文章", 6),
    ("ライティング", 6),
    ("コーディング", 8),
    ("コード", 5),
    ("ide", 5),
    ("エディタ", 5),
    ("チャット", 4),
    ("営業", 6),
    ("コンテンツ", 6),
    ("生産性", 7),
    ("効率", 7),
    ("時短", 7),
    ("作業", 5),
    ("顧客", 2),
    ("クライアント", 2),
)

TECHNICAL_DEPTH_SIGNALS: tuple[tuple[str, float], ...] = (
    ("kubernetes", -22),
    ("gpuクラスタ", -20),
    ("gpu cluster", -20),
    ("推論サーバ", -18),
    ("inference server", -18),
    ("モデルサービング", -18),
    ("serving engine", -16),
    ("mlops", -16),
    ("分散推論", -18),
    ("分散ノード", -14),
    ("vector db", -14),
    ("ベクトルデータベース", -14),
    ("量子化", -10),
    ("cuda", -12),
    ("tensorrt", -18),
    ("execution provider", -10),
    ("モデル学習", -8),
    ("学習基盤", -10),
    ("モデル管理", -8),
)

WORK_READY_SIGNALS: tuple[str, ...] = (
    "小さく試",
    "少人数",
    "1業務",
    "限定",
    "月額",
    "費用",
    "権限",
    "外部送信",
    "データ",
    "リスク",
)
# Backward-compatible alias for older tests/imports.
CLIENT_READY_SIGNALS = WORK_READY_SIGNALS


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _blob(state: dict[str, Any]) -> str:
    parts = (
        state.get("name"),
        state.get("plain_summary"),
        state.get("topic"),
        state.get("judgment_reason"),
        state.get("best_for"),
        state.get("avoid_for"),
        state.get("main_risk"),
        state.get("next_action"),
        state.get("category"),
    )
    return " ".join(_clean(x) for x in parts if _clean(x)).casefold()


def icp_relevance_score(state: dict[str, Any]) -> float:
    """Return 0–100 paid-surface relevance without changing factual quality."""
    if state.get("classification") not in {None, "", "実務判断"}:
        return 0.0

    category = _clean(state.get("category")) or "その他"
    score = CATEGORY_BASE.get(category, CATEGORY_BASE["その他"])
    blob = _blob(state)

    positive_hits = 0
    for signal, weight in POSITIVE_SIGNALS:
        if signal.casefold() in blob:
            score += weight
            positive_hits += 1

    for signal, weight in TECHNICAL_DEPTH_SIGNALS:
        if signal.casefold() in blob:
            score += weight

    # Reversible/small-test language makes an item easier to try in real work.
    ready_hits = sum(1 for signal in WORK_READY_SIGNALS if signal.casefold() in blob)
    score += min(ready_hits, 4) * 2.0

    if positive_hits >= 3:
        score += 6.0
    elif positive_hits == 0:
        score -= 6.0

    return round(max(0.0, min(100.0, score)), 2)


def product_rank_score(state: dict[str, Any]) -> float:
    """Navigation-only composite: work relevance dominates; source quality still matters."""
    fit = icp_relevance_score(state)
    source_score = state.get("score")
    quality = (
        float(source_score)
        if isinstance(source_score, (int, float)) and not isinstance(source_score, bool)
        else 0.0
    )
    return round((fit * 0.70) + (quality * 0.30), 4)


STATUS_PLAIN = {
    "ADOPT": "条件が合えば仕事で使う候補にする",
    "TEST": "限定業務で小さく試す",
    "WATCH": "今は急いで使わず、条件の変化を待つ",
    "AVOID": "今は使わず、代替候補を見る",
}


def business_impact_text(state: dict[str, Any]) -> str:
    """Frame the authoritative decision as work impact without inventing ROI."""
    status = _clean(state.get("status")).upper()
    reason = _clean(state.get("judgment_reason"))
    lead = STATUS_PLAIN.get(status, "利用条件を確認してから判断する")
    if reason:
        return f"{lead}。{reason}"
    return f"{lead}。"


def work_case_text(state: dict[str, Any]) -> str:
    """Use the canonical best-for field as the work-use case."""
    best = _clean(state.get("best_for"))
    return best or _clean(state.get("plain_summary"))


def _sentence(value: str) -> str:
    text = _clean(value)
    if not text:
        return ""
    return text if text.endswith(("。", "！", "？")) else f"{text}。"


def work_check_text(state: dict[str, Any]) -> str:
    """Use risk/avoid boundaries as pre-use checks; no new facts are created."""
    risk = _clean(state.get("main_risk"))
    avoid = _clean(state.get("avoid_for"))
    if risk and avoid and avoid not in risk:
        return f"{_sentence(risk)} 向かない条件：{_sentence(avoid)}"
    return risk or avoid


def work_action_text(state: dict[str, Any]) -> str:
    """Return existing next action with work-first, audience-neutral wording."""
    action = _clean(state.get("next_action"))
    replacements = (
        ("自社要件", "利用条件"),
        ("自社案件", "自分の仕事"),
        ("自社の", "自分の"),
        ("自社で", "自分の環境で"),
        ("自社", "自分の環境"),
        ("案件要件", "利用条件"),
        ("対象案件", "対象業務"),
        ("案件の", "対象業務の"),
        ("案件で", "対象業務で"),
    )
    for old, new in replacements:
        action = action.replace(old, new)
    return action


# Backward-compatible names retained so older wrappers/imports keep working.
def client_case_text(state: dict[str, Any]) -> str:
    return work_case_text(state)


def client_check_text(state: dict[str, Any]) -> str:
    return work_check_text(state)


def proposal_action_text(state: dict[str, Any]) -> str:
    return work_action_text(state)


def decision_update_text(state: dict[str, Any]) -> str:
    """Translate a recorded change into whether the user's work judgment should move."""
    reason = _clean(state.get("change_reason"))
    delta = state.get("delta")
    if not reason or not isinstance(delta, (int, float)) or isinstance(delta, bool):
        return ""
    if float(delta) > 0:
        prefix = "前回より仕事で使う候補として再検討する価値が上がりました。"
    elif float(delta) < 0:
        prefix = "前回より仕事で使う候補として慎重に見る必要が高まりました。"
    else:
        return ""
    return f"{prefix}{reason}"
