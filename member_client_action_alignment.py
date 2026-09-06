"""Run250 client-action product alignment for the paid member surface.

This is a deterministic presentation policy. It does not change source Evidence,
scores, decisions, or canonical records. It answers a narrower product question:
which already-qualified technologies are most relevant to the initial paid ICP?

Initial ICP:
- 1–3 person web / marketing / business-improvement service providers
- receive AI questions from clients
- are not dedicated AI specialists

The broad Intelligence Engine remains intact. This module only determines what
should be surfaced first and how existing authoritative fields should be framed.
ZERO model/provider calls.
"""
from __future__ import annotations

import re
from typing import Any

ICP_LABEL = (
    "Web制作・マーケティング・業務改善などを受託する1〜3名規模の事業者で、"
    "顧客からAI活用を相談されるようになったが、AI専業ではない人"
)

CATEGORY_BASE = {
    "製品・サービス": 74.0,
    "エージェント": 68.0,
    "マルチモーダル": 66.0,
    "開発ツール": 60.0,
    "セキュリティ": 48.0,
    "データ": 42.0,
    "AIモデル": 42.0,
    "基盤": 28.0,
    "その他": 45.0,
}

# Generic signals, not product-name allowlists. New products can rank without a code change.
POSITIVE_SIGNALS: tuple[tuple[str, float], ...] = (
    ("顧客", 10),
    ("クライアント", 10),
    ("web制作", 10),
    ("制作", 8),
    ("マーケ", 8),
    ("業務改善", 10),
    ("自動化", 9),
    ("ワークフロー", 8),
    ("ブラウザ", 10),
    ("faq", 8),
    ("問い合わせ", 8),
    ("文書検索", 8),
    ("資料検索", 8),
    ("aiアプリ", 8),
    ("ノーコード", 8),
    ("ローコード", 8),
    ("画像", 6),
    ("動画", 6),
    ("デザイン", 6),
    ("コーディング", 8),
    ("コード", 5),
    ("ide", 5),
    ("エディタ", 5),
    ("チャット", 4),
    ("営業", 6),
    ("コンテンツ", 6),
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

CLIENT_READY_SIGNALS: tuple[str, ...] = (
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

    # Reversible/small-test language makes an item easier to turn into a client proposal.
    ready_hits = sum(1 for signal in CLIENT_READY_SIGNALS if signal.casefold() in blob)
    score += min(ready_hits, 4) * 2.0

    if positive_hits >= 3:
        score += 6.0
    elif positive_hits == 0:
        score -= 6.0

    return round(max(0.0, min(100.0, score)), 2)


def product_rank_score(state: dict[str, Any]) -> float:
    """Navigation-only composite: ICP fit dominates, source quality still matters."""
    fit = icp_relevance_score(state)
    source_score = state.get("score")
    quality = (
        float(source_score)
        if isinstance(source_score, (int, float)) and not isinstance(source_score, bool)
        else 0.0
    )
    return round((fit * 0.70) + (quality * 0.30), 4)


STATUS_PLAIN = {
    "ADOPT": "条件が合えば導入候補にする",
    "TEST": "限定業務で小さく試す",
    "WATCH": "今は提案の中心にせず、条件の変化を待つ",
    "AVOID": "新規提案の候補から外し、代替候補を見る",
}


def business_impact_text(state: dict[str, Any]) -> str:
    """Frame the authoritative decision as client-work impact without inventing ROI."""
    status = _clean(state.get("status")).upper()
    reason = _clean(state.get("judgment_reason"))
    lead = STATUS_PLAIN.get(status, "案件条件を確認してから判断する")
    if reason:
        return f"{lead}。{reason}"
    return f"{lead}。"


def client_case_text(state: dict[str, Any]) -> str:
    """Use the canonical best-for field as the client-use case."""
    best = _clean(state.get("best_for"))
    return best or _clean(state.get("plain_summary"))


def client_check_text(state: dict[str, Any]) -> str:
    """Use risk/avoid boundaries as pre-proposal checks; no new facts are created."""
    risk = _clean(state.get("main_risk"))
    avoid = _clean(state.get("avoid_for"))
    if risk and avoid and avoid not in risk:
        return f"{risk} また、{avoid}"
    return risk or avoid


def proposal_action_text(state: dict[str, Any]) -> str:
    """Return the existing next action with only audience-neutral wording."""
    action = _clean(state.get("next_action"))
    replacements = (
        ("自社要件", "案件要件"),
        ("自社案件", "対象案件"),
        ("自社の", "案件の"),
        ("自社で", "案件で"),
        ("自社", "案件"),
    )
    for old, new in replacements:
        action = action.replace(old, new)
    return action


def decision_update_text(state: dict[str, Any]) -> str:
    """Translate a recorded change into whether proposal judgment should move."""
    reason = _clean(state.get("change_reason"))
    delta = state.get("delta")
    if not reason or not isinstance(delta, (int, float)) or isinstance(delta, bool):
        return ""
    if float(delta) > 0:
        prefix = "前回より案件候補として再検討する価値が上がりました。"
    elif float(delta) < 0:
        prefix = "前回より案件候補として慎重に見る必要が高まりました。"
    else:
        return ""
    return f"{prefix}{reason}"
