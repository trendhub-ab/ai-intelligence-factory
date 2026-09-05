"""Deterministic reader-purpose badge taxonomy and fixed vector-style icons.

This helper is intentionally provider-free.  It classifies the public eyecatch badge from
article/topic cues already available to Run181 and draws compact icons with Pillow
primitives only.  It does not introduce factual claims, model calls, image-generation
calls, network access, or font dependencies.
"""
from __future__ import annotations

from typing import Any


BADGE_LABELS = (
    "初心者向け",
    "比較で理解",
    "安全性を確認",
    "論文をやさしく",
    "実務で判断",
    "最新動向を理解",
    "仕組みを理解",
    "開発で使う",
    "データを理解",
    "要点を理解",
)

_COMPARE_CUES = (" vs ", "vs.", "比較", "違い", "どちら", "選ぶなら", "versus")
_SECURITY_CUES = (
    "脆弱",
    "攻撃",
    "security",
    "secure",
    "安全性",
    "cve-",
    "jailbreak",
    "prompt injection",
    "リスク",
)
_RESEARCH_CUES = ("論文", "研究", "arxiv", "paper", "benchmark", "ベンチマーク")
_BEGINNER_CUES = (
    "初心者",
    "入門",
    "はじめて",
    "初めて",
    "基礎から",
    "ゼロから",
    "beginner",
    "getting started",
)
_DEV_CUES = (
    "developer",
    "sdk",
    " cli",
    "cli ",
    "github",
    "コーディング",
    "コード生成",
    "開発ツール",
    "開発者",
    "repository",
    "リポジトリ",
)
_DATA_CUES = (
    "database",
    "vector database",
    "データベース",
    "rag",
    "retrieval",
    "データ基盤",
    "data pipeline",
    "データパイプライン",
)
_PRACTICAL_CUES = (
    "導入",
    "採用",
    "使うべき",
    "実務",
    "運用",
    "業務",
    "企業",
    "料金",
    "価格",
    "roi",
    "enterprise",
    "business",
)
_NEWS_CUES = (
    "発表",
    "公開",
    "リリース",
    "アップデート",
    "新機能",
    "提供開始",
    "正式版",
    "release",
    "released",
    "launch",
    "launched",
    "announce",
    "announced",
    "update",
)
_MECHANISM_CUES = (
    "なぜ",
    "仕組み",
    "原理",
    "どう動く",
    "どうして",
    "内部",
    "構造",
    "architecture",
    "mechanism",
    "how it works",
    "高速",
    "速い",
    "性能",
)
_MECHANISM_CATEGORIES = {
    "AI AGENTS",
    "MODELS",
    "ROBOTICS",
    "MULTIMODAL",
    "AI INFRA",
}


def classify_badge(title: str, summary: str, category: str) -> str:
    """Choose one reader-purpose badge without defaulting generic stories to beginner.

    ``初心者向け`` is reserved for explicit beginner/introductory cues.  Generic articles
    fall back to ``要点を理解`` so the publication grid does not falsely imply that every
    article is an introductory tutorial.
    """
    text = f"{title or ''}\n{summary or ''}".lower()
    category = str(category or "AI & TECH").strip().upper()

    if any(token in text for token in _COMPARE_CUES):
        return "比較で理解"
    if category == "SECURITY" or any(token in text for token in _SECURITY_CUES):
        return "安全性を確認"
    if category == "RESEARCH" or any(token in text for token in _RESEARCH_CUES):
        return "論文をやさしく"
    if any(token in text for token in _BEGINNER_CUES):
        return "初心者向け"
    if category == "DEV TOOLS" or any(token in text for token in _DEV_CUES):
        return "開発で使う"
    if category == "DATA" or any(token in text for token in _DATA_CUES):
        return "データを理解"
    if category == "AI BUSINESS" or any(token in text for token in _PRACTICAL_CUES):
        return "実務で判断"
    if any(token in text for token in _NEWS_CUES):
        return "最新動向を理解"
    if category in _MECHANISM_CATEGORIES or any(token in text for token in _MECHANISM_CUES):
        return "仕組みを理解"
    return "要点を理解"


def _navy() -> tuple[int, int, int]:
    return (7, 30, 66)


def draw_badge_icon(
    draw: Any,
    label: str,
    left: int,
    top: int,
    accent: tuple[int, int, int],
    *,
    size: int = 26,
) -> None:
    """Draw a fixed vector-style icon for one badge using Pillow primitives only."""
    x, y, s = int(left), int(top), int(size)
    navy = _navy()
    mid = s // 2
    right = x + s
    bottom = y + s
    stroke = max(2, s // 12)

    if label == "初心者向け":
        # Japanese beginner-mark inspired shield. Fixed geometry, no external SVG asset.
        points = [(x + 3, y + 2), (x + mid, y + 9), (right - 3, y + 2), (right - 3, y + 16), (x + mid, bottom - 1), (x + 3, y + 16)]
        left_half = [points[0], points[1], (x + mid, bottom - 1), points[5]]
        right_half = [points[1], points[2], points[3], (x + mid, bottom - 1)]
        draw.polygon(left_half, fill=(72, 190, 95))
        draw.polygon(right_half, fill=(247, 214, 63))
        draw.line(points + [points[0]], fill=navy, width=stroke, joint="curve")
        draw.line((x + mid, y + 9, x + mid, bottom - 1), fill=navy, width=stroke)
        return

    if label == "比較で理解":
        draw.line((x + 3, y + 8, right - 4, y + 8), fill=accent, width=stroke + 1)
        draw.polygon([(right - 4, y + 8), (right - 10, y + 3), (right - 10, y + 13)], fill=accent)
        draw.line((right - 3, y + 18, x + 4, y + 18), fill=navy, width=stroke + 1)
        draw.polygon([(x + 4, y + 18), (x + 10, y + 13), (x + 10, y + 23)], fill=navy)
        return

    if label == "安全性を確認":
        shield = [(x + mid, y + 2), (right - 3, y + 6), (right - 5, y + 17), (x + mid, bottom - 2), (x + 5, y + 17), (x + 3, y + 6)]
        draw.polygon(shield, fill=None, outline=accent)
        draw.line((x + 8, y + 13, x + 12, y + 17, right - 7, y + 9), fill=navy, width=stroke + 1)
        return

    if label == "論文をやさしく":
        draw.rounded_rectangle((x + 5, y + 2, right - 5, bottom - 2), radius=2, outline=navy, width=stroke)
        draw.line((x + 9, y + 8, right - 9, y + 8), fill=accent, width=stroke)
        draw.line((x + 9, y + 13, right - 7, y + 13), fill=accent, width=stroke)
        draw.line((x + 9, y + 18, right - 11, y + 18), fill=accent, width=stroke)
        return

    if label == "実務で判断":
        draw.rounded_rectangle((x + 3, y + 8, right - 3, bottom - 3), radius=3, outline=navy, width=stroke)
        draw.arc((x + 8, y + 2, right - 8, y + 13), 180, 360, fill=navy, width=stroke)
        draw.line((x + 7, y + 15, x + 11, y + 19, right - 6, y + 11), fill=accent, width=stroke + 1)
        return

    if label == "最新動向を理解":
        draw.line((x + 3, y + 18, x + 8, y + 18, x + 11, y + 9, x + 15, y + 21, x + 19, y + 12, right - 3, y + 12), fill=accent, width=stroke + 1)
        draw.ellipse((right - 7, y + 3, right - 3, y + 7), fill=navy)
        return

    if label == "仕組みを理解":
        nodes = ((x + mid, y + 3), (x + 5, y + 19), (right - 5, y + 19))
        draw.line((nodes[0][0], nodes[0][1], nodes[1][0], nodes[1][1], nodes[2][0], nodes[2][1], nodes[0][0], nodes[0][1]), fill=accent, width=stroke)
        for cx, cy in nodes:
            draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=navy)
        return

    if label == "開発で使う":
        draw.line((x + 10, y + 5, x + 4, y + mid, x + 10, bottom - 5), fill=navy, width=stroke + 1)
        draw.line((right - 10, y + 5, right - 4, y + mid, right - 10, bottom - 5), fill=navy, width=stroke + 1)
        draw.line((x + 15, bottom - 4, right - 9, y + 4), fill=accent, width=stroke)
        return

    if label == "データを理解":
        draw.ellipse((x + 4, y + 3, right - 4, y + 10), outline=navy, width=stroke)
        draw.line((x + 4, y + 7, x + 4, bottom - 6), fill=navy, width=stroke)
        draw.line((right - 4, y + 7, right - 4, bottom - 6), fill=navy, width=stroke)
        draw.arc((x + 4, y + 10, right - 4, y + 18), 0, 180, fill=accent, width=stroke)
        draw.arc((x + 4, bottom - 11, right - 4, bottom - 3), 0, 180, fill=accent, width=stroke)
        return

    # Generic ``要点を理解`` icon: three concise checklist marks.
    for offset in (5, 12, 19):
        draw.line((x + 3, y + offset, x + 6, y + offset + 3, x + 10, y + offset - 2), fill=accent, width=stroke)
        draw.line((x + 13, y + offset, right - 3, y + offset), fill=navy, width=stroke)
