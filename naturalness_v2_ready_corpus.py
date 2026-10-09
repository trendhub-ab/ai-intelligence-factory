"""Provider-free Ready-corpus supplement for Naturalness v2.

This module only enriches an already-authorized Quality Retry. It does not
contribute to Publication Gate scoring, authorize a retry, or call a provider.
"""
from __future__ import annotations

import re

from editorial_naturalness import build_naturalness_retry_contract as _base_retry_contract


_EXCLUDED_HEADINGS = {
    "Reader-first summary", "Reader Summary", "どんな内容？", "なぜ重要？",
    "結論は？", "元情報", "Sources / Evidence", "Sources", "Evidence",
}


def _article_sections(text: str) -> list[tuple[int, str]]:
    """Return authorial H2/H3 prose while ignoring quotes, code, and metadata blocks."""
    lines: list[str] = []
    fence: str | None = None
    for line in (text or "").splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if fence:
            if re.fullmatch(r"\s{0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line):
                fence = None
            lines.append("")
            continue
        if marker:
            fence = marker.group(1)
            lines.append("")
            continue
        lines.append("" if re.match(r"^\s*>", line) else line)

    body = "\n".join(lines)
    body = re.sub(r"`[^`\n]*`|「[^」]*」|『[^』]*』", "引用", body)
    headings = list(re.finditer(r"^(#{2,3})\s+(.+)$", body, re.M))
    sections: list[tuple[int, str]] = []
    excluded_level: int | None = None
    for index, match in enumerate(headings):
        level = len(match.group(1))
        if excluded_level is not None and level <= excluded_level:
            excluded_level = None
        if match.group(2).strip() in _EXCLUDED_HEADINGS:
            excluded_level = level
        if excluded_level is not None:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        prose = body[match.end():end].strip()
        if prose:
            sections.append((index + 1, prose))
    return sections


def ready_corpus_signals(text: str) -> dict:
    """Detect repeated habits observed in actual Ready manuscripts.

    Each signal must occur in at least two separate sections. Repair is still
    recommended only when two independent habit classes repeat together.
    """
    dramatic_sections: list[int] = []
    abstract_closing_sections: list[int] = []

    dramatic_patterns = (
        r"今回(?:注目すべき|重要なの|の変化|のポイント)",
        r"単なる[^。！？\n]{0,60}(?:だけではありません|ではありません|ではない)",
        r"単に[^。！？\n]{0,60}(?:という話ではありません|という話ではない)",
        r"ここで(?:一つの)?(?:緊張感|重要なの|重要な|ポイント|問題|境界線)",
    )
    abstract_closing_pattern = re.compile(
        r"(?:ことを示唆しています|ことを示しています|証左(?:だ|です|と言えます)|"
        r"フェーズに入ったと言えます|スタンダード[^。！？\n]{0,35}(?:近道|と言えます)|"
        r"へと変質し始めていることを示唆しています)[。！？!?]?$"
    )

    for number, prose in _article_sections(text):
        if sum(bool(re.search(pattern, prose)) for pattern in dramatic_patterns) >= 1:
            dramatic_sections.append(number)
        sentences = [s.strip() for s in re.split(r"(?<=[。！？!?])|\n", prose) if s.strip()]
        closing = sentences[-1] if sentences else ""
        if abstract_closing_pattern.search(closing):
            abstract_closing_sections.append(number)

    signals = {
        "repeated_dramatic_scaffolding": dramatic_sections if len(dramatic_sections) >= 2 else [],
        "repeated_abstract_closings": abstract_closing_sections if len(abstract_closing_sections) >= 2 else [],
    }
    signals["repair_recommended"] = sum(bool(value) for value in signals.values()) >= 2
    return signals


def build_naturalness_retry_contract(article: str) -> str:
    """Combine v2 base advice with Ready-corpus advice without adding a retry."""
    base = _base_retry_contract(article)
    signals = ready_corpus_signals(article)
    if not signals["repair_recommended"]:
        return base

    advice = [
        "[naturalness-v2｜実Ready稿由来の補助指示]",
        "検出は編集上の目安であり、新しい不合格理由ではない。",
    ]
    if signals["repeated_dramatic_scaffolding"]:
        sections = ", ".join(map(str, signals["repeated_dramatic_scaffolding"]))
        advice.append(
            f"・節 {sections}: 『今回注目すべき』『単なるAではなくB』『ここで〜』のようなドラマ化したメタ説明を減らし、事実を直接置く。"
        )
    if signals["repeated_abstract_closings"]:
        sections = ", ".join(map(str, signals["repeated_abstract_closings"]))
        advice.append(
            f"・節 {sections}: 『示唆する』『証左と言える』など抽象的な節末総括の反復を減らし、根拠のある具体判断だけを残す。"
        )
    advice.extend([
        "自然な単発表現は残す。Fact / Evidence / Decision・数値・URL・条件・制約・情報量を維持し、文章の運びだけを直す。",
        "既存Gateの修正を優先する。追加生成や再試行を要求しない。",
    ])
    supplement = "\n".join(advice)
    return base + ("\n\n" if base else "") + supplement
