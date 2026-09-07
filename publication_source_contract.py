"""Canonical public-source contract for note publication surfaces.

Run281 centralizes the active source set, reader-facing labels, and rights notes so source
acquisition migrations cannot leave Note Ready eligibility and public manuscript attribution on
different generations of the contract. This module is deterministic and zero-network.
"""
from __future__ import annotations

ACTIVE_PUBLIC_SOURCES = ("GitHub", "HackerNews", "ArXiv", "OfficialVendor")

READER_SOURCE_LABELS = {
    "GitHub": "GitHub",
    "HackerNews": "Hacker News",
    "ArXiv": "arXiv",
    "OfficialVendor": "公式ベンダー",
}

SOURCE_RIGHTS_NOTE = {
    "HackerNews": (
        "- **出典について**: Hacker Newsは発見経路として利用し、本文の技術的な事実・数値は、"
        "上記の主一次情報および参考情報で確認できる範囲を独自に分析・要約したものです。"
        "リンク先記事本文の著作権は原著作者に帰属します。\n"
    ),
    "ArXiv": (
        "- **出典について**: 本記事はarXivで公開されている論文の要旨・情報を基に"
        "独自に分析・要約したものです。論文本文の著作権は著者に帰属します。\n"
    ),
    "OfficialVendor": (
        "- **出典について**: 本記事は各ベンダーが公式に公開した一次情報を基に"
        "独自に分析・要約したものです。製品名・商標・公開資料等の権利は各権利者に帰属します。\n"
    ),
}


def validate_source_contract() -> None:
    active = set(ACTIVE_PUBLIC_SOURCES)
    if set(READER_SOURCE_LABELS) != active:
        raise RuntimeError("reader source labels must exactly match ACTIVE_PUBLIC_SOURCES")
    if set(SOURCE_RIGHTS_NOTE) != active - {"GitHub"}:
        raise RuntimeError("non-GitHub rights notes must exactly match active public sources")
    if "ProductHunt" in active or "ProductHunt" in READER_SOURCE_LABELS or "ProductHunt" in SOURCE_RIGHTS_NOTE:
        raise RuntimeError("retired ProductHunt source cannot remain in the public source contract")


validate_source_contract()
