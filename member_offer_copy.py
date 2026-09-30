"""Evidence-neutral, reader-first membership CTA for free note articles.

Copy changes only; never claims the current article appears in paid DB, a
guaranteed update cadence, measured ROI, or instant access after payment.
The offer is the already-verified ¥1,980/month Decision DB + monthly Brief.
No model calls; preserve the full free article and existing attribution URL.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

HEADING = "調査と判断の時間を減らしたい方へ"
LINK_LABEL = "月額1,980円の内容を確認する"

# Classify an already-approved reader summary; never copy a model-produced
# sentence into a sales assertion. First match wins and no new source fact
# is manufactured by this classification.
_SECURITY = re.compile(r"攻撃|侵害|漏洩|漏えい|脆弱|セキュリティ|権限|認証|malware|security|breach", re.I)
_RESEARCH = re.compile(r"研究|論文|実験|ベンチマーク|評価手法|arxiv|research|paper|benchmark", re.I)
_TOOL = re.compile(r"導入|乗り換え|製品|サービス|新機能|開発ツール|運用|API|SDK|release|tool", re.I)

OPENINGS = {
    "safety": "問題を知ったあと、気になるのは「自分の環境なら、どこを確認するか」。",
    "research": "研究の面白さと、実際に試せるかどうかは別の話です。",
    "tool": "新しい選択肢を知るたびに、一から比較するのは大変です。",
    "general": "今日の話題を理解しても、明日にはまた別の選択肢が現れます。",
}
FOLLOWUPS = {
    "safety": "利用条件やリスクを、技術ごとに見直せる場所があると判断しやすくなります。",
    "research": "実用性、検証条件、まだ分かっていないことを整理してから判断したいところです。",
    "tool": "いま使うか、試すか、まだ待つか。その判断材料をためておくために。",
    "general": "そのつど情報を集め直すのではなく、必要なときに根拠へ戻れるように。",
}


def classify(reader_summary: Mapping[str, Any] | None, *, source: str = "") -> str:
    summary = reader_summary or {}
    what = str(summary.get("what") or "")
    why = str(summary.get("why") or "")
    text = (what + " " + why)[:1200]
    if _SECURITY.search(text):
        return "safety"
    if source == "ArXiv" or _RESEARCH.search(text):
        return "research"
    if _TOOL.search(text):
        return "tool"
    return "general"


def render(*, tracking_url: str, reader_summary: Mapping[str, Any] | None = None,
           source: str = "", divider: str = "---") -> str:
    if not tracking_url:
        return ""
    # The caller must retain the existing validated landing URL builder.
    from urllib.parse import urlsplit
    parsed = urlsplit(tracking_url)
    if parsed.scheme != "https" or not parsed.netloc:
        return ""
    angle = classify(reader_summary, source=source)
    return (
        f"{divider}"
        f"### {HEADING}\n\n"
        f"{OPENINGS[angle]}{FOLLOWUPS[angle]}\n\n"
        "AI Decision Intelligenceの会員向けDBでは、AIや技術の使いどころ、"
        "利用前に確認したい条件、主なリスク、次の一手と参照情報をまとめています。"
        "月次Decision Briefは、その中から今の判断に役立つ情報を先に読む入口です。\n\n"
        "この記事の結論は無料のまま。会員向けには、次の選択に迷ったときに使える情報を整理しています。\n\n"
        f"[{LINK_LABEL}]({tracking_url})\n\n"
        "※会員コンテンツはNotionで提供しています。加入後に利用登録・招待が必要です。"
        "閲覧のためにNotionの有料プランへ加入する必要はありません。\n"
    )
