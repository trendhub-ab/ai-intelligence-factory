"""Provider-free structural naturalness diagnostics for AIIF public articles.

The v2 detector deliberately has no Ready-blocking authority.  It only describes
repetitive editorial structure so an already-authorized quality retry can receive
more specific repair guidance.
"""
from __future__ import annotations

from collections import Counter
import re
from typing import Any


_META_SUMMARY_PHRASES = ("つまり", "要するに", "重要なのは", "ポイントは", "結局")
_SPEAKER_PHRASES = ("私なら", "私であれば")
_ABSTRACT_CLOSING_TERMS = ("重要", "判断", "選択肢", "岐路", "競争力", "未来", "本質", "鍵")


def _sections(text: str) -> list[dict[str, Any]]:
    body = text or ""
    matches = list(re.finditer(r"^#{2,3}\s+(.+)$", body, re.MULTILINE))
    result: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        section_body = body[match.end():end].strip()
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[。！？!?])\s*", section_body)
            if sentence.strip()
        ]
        result.append(
            {
                "index": index + 1,
                "heading": match.group(1).strip(),
                "body": section_body,
                "sentences": sentences,
            }
        )
    return result


def _speaker_position(sentences: list[str]) -> str:
    for index, sentence in enumerate(sentences):
        if not any(phrase in sentence for phrase in _SPEAKER_PHRASES):
            continue
        if index == len(sentences) - 1:
            return "final"
        if index >= max(0, len(sentences) - 2):
            return "late"
        return "early"
    return "none"


def editorial_naturalness_v2_diagnostics(text: str) -> dict[str, Any]:
    """Describe repetitive section-level writing habits without blocking Ready.

    P2 signals are suitable as targeted hints when a quality retry is already
    happening.  P3 is advisory.  This function never creates a P0 factual gate
    and never returns blocking authority.
    """
    sections = _sections(text)
    fingerprints: list[tuple[str, bool, str, bool]] = []
    meta_close_sections: list[int] = []
    speaker_final_sections: list[int] = []
    abstract_close_sections: list[int] = []

    for section in sections:
        sentences = list(section["sentences"])
        ending_window = "".join(sentences[-2:]) if sentences else ""
        meta_close = any(phrase in ending_window for phrase in _META_SUMMARY_PHRASES)
        speaker_position = _speaker_position(sentences)
        abstract_close = bool(
            any(term in ending_window for term in _ABSTRACT_CLOSING_TERMS)
            and not re.search(r"\d|https?://|[A-Za-z]{2,}", ending_window)
        )
        sentence_bucket = "1" if len(sentences) <= 1 else "2" if len(sentences) == 2 else "3+"
        fingerprints.append((sentence_bucket, meta_close, speaker_position, abstract_close))

        if meta_close:
            meta_close_sections.append(int(section["index"]))
        if speaker_position == "final":
            speaker_final_sections.append(int(section["index"]))
        if abstract_close:
            abstract_close_sections.append(int(section["index"]))

    signals: list[dict[str, Any]] = []
    repeated_fingerprints = [
        (fingerprint, count)
        for fingerprint, count in Counter(fingerprints).items()
        if count >= 3 and (fingerprint[1] or fingerprint[2] != "none" or fingerprint[3])
    ]
    if repeated_fingerprints:
        signals.append(
            {
                "code": "section_structure_repetition",
                "severity": "P2",
                "sections": [int(section["index"]) for section in sections],
                "detail": "3つ以上の節で同じ終わり方・話者位置・文数帯が反復しています。",
            }
        )
    if len(meta_close_sections) >= 3:
        signals.append(
            {
                "code": "uniform_conclusion_cadence",
                "severity": "P2",
                "sections": meta_close_sections,
                "detail": "3つ以上の節末でメタ要約から結論へ進む同じリズムが反復しています。",
            }
        )
    if len(speaker_final_sections) >= 3:
        signals.append(
            {
                "code": "speaker_voice_position_repetition",
                "severity": "P2",
                "sections": speaker_final_sections,
                "detail": "3つ以上の節で話者判断が最終文の同じ位置に置かれています。",
            }
        )
    if len(abstract_close_sections) >= 3:
        signals.append(
            {
                "code": "abstract_closing_cluster",
                "severity": "P3",
                "sections": abstract_close_sections,
                "detail": "複数節が抽象的な判断語で閉じています。",
            }
        )

    repair_required = any(row["severity"] in {"P1", "P2"} for row in signals)
    return {
        "signals": signals,
        "repair_required": repair_required,
        "advisory_only": bool(signals) and not repair_required,
        "hard_block": False,
        "blocking_authority": "none",
    }
