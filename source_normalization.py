"""Pure source normalization and multilingual display compatibility layer.

Run235 Stage3A extracts the zero-API source-normalization surface from the large
``pipeline.py`` module without changing its external contract.  The legacy
functions remain in ``pipeline.py`` during the strangler-parity phase, while
Production explicitly installs these implementations before the historical runtime
wrapper stack.

This module must stay free of provider, Notion, network, model, quota, Evidence, and
Decision logic.
"""
from __future__ import annotations

import re
import unicodedata


def _detect_title_language(title: str) -> str:
    """追加APIなしでDB表示用の大まかな原文言語を判定する。

    Entity ResolutionやDedupには使わない。日本語かなを含む場合はja、
    Hanのみはzh-CN、Hangulはko、Cyrillicはru系として扱い、英数字中心はen。
    """
    text = unicodedata.normalize("NFKC", title or "")
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", text):
        return "ko"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh-CN"
    if re.search(r"[\u0400-\u04ff]", text):
        return "ru"
    if re.search(r"[A-Za-z]", text):
        return "en"
    return "und"


def _japanese_product_descriptor(description: str, source: str) -> str:
    """英語tagline/descriptionから0 APIで短い日本語カテゴリ名を付ける。

    翻訳を捏造せず、十分なキーワードがある場合だけ具体化する。
    """
    text = unicodedata.normalize("NFKC", description or "").casefold()
    rules = [
        (("ecommerce", "e-commerce", "product photo", "product image", "listing image"), "EC商品画像生成ツール"),
        (("image generator", "generate images", "image generation", "photo generator"), "AI画像生成ツール"),
        (("video generator", "video generation", "generate videos"), "AI動画生成ツール"),
        (("agent", "agentic", "multi-agent", "ai agent"), "AIエージェントツール"),
        (("developer tool", "devtool", "coding", "code generation", "api"), "開発支援ツール"),
        (("analytics", "analysis", "dashboard", "business intelligence"), "データ分析ツール"),
        (("voice", "speech", "text-to-speech", "tts"), "音声AIツール"),
    ]
    for keywords, label in rules:
        if any(k in text for k in keywords):
            return label
    return "海外プロダクト" if source == "ProductHunt" else "海外技術情報"


def _multilingual_display_name(original_title: str, description: str = "", source: str = "") -> tuple[str, str]:
    """原題を壊さず、人間がDB一覧で判別しやすい表示名を返す。

    英語・日本語タイトルは従来表示を維持する。中国語/韓国語/Cyrillic等だけ、
    日本語カテゴリ + 原題の形にするため、誤訳によるEntity誤マージを防ぐ。
    """
    original = unicodedata.normalize("NFKC", (original_title or "無題").strip()) or "無題"
    lang = _detect_title_language(original)
    if lang in {"ja", "en"} or lang == "und":
        return original, lang
    descriptor = _japanese_product_descriptor(description, source)
    return f"{descriptor}「{original}」", lang


def _notion_display_name(repo: dict) -> str:
    return (repo.get("displayName") or repo.get("nameWithOwner") or "無題").strip() or "無題"


def _source_summary_with_original(repo: dict, summary: str) -> str:
    """非英語タイトルの原題・言語を既存Source Summaryへ非破壊で残す。"""
    original = (repo.get("originalTitle") or repo.get("nameWithOwner") or "").strip()
    lang = (repo.get("sourceLanguage") or _detect_title_language(original)).strip()
    body = (summary or "").strip()
    if lang in {"ja", "en", "und", ""}:
        return body
    prefix = f"Original Title: {original}\nLanguage: {lang}"
    return (prefix + ("\n" + body if body else ""))[:2000]


def normalize_item(source: str, name: str, url: str, description: str,
                   engagement: int, license_info: dict | None = None,
                   published_at: str | None = None, source_context: str = "",
                   primary_url: str | None = None, source_details: dict | None = None) -> dict:
    """各ソースを既存互換キーへ正規化し、Deep Dive用一次コンテキストも保持する。

    nameWithOwnerは原題のまま保持し、Entity Resolution/Dedupの正本とする。
    displayNameだけをNotion等の人間向け表示に利用する。
    """
    original = unicodedata.normalize("NFKC", (name or "無題").strip()) or "無題"
    desc = (description or "説明なし").strip() or "説明なし"
    display_name, language = _multilingual_display_name(original, desc, source)
    return {
        "source": source,
        "nameWithOwner": original,
        "originalTitle": original,
        "displayName": display_name,
        "sourceLanguage": language,
        "url": (url or "").strip(),
        "description": desc,
        "stargazerCount": engagement or 0,
        "licenseInfo": license_info,
        "publishedAt": published_at,
        "sourceContext": (source_context or "").strip(),
        "primaryUrl": (primary_url or url or "").strip(),
        "sourceDetails": source_details or {},
    }


_EXPORTED_NAMES = (
    "_detect_title_language",
    "_japanese_product_descriptor",
    "_multilingual_display_name",
    "_notion_display_name",
    "_source_summary_with_original",
    "normalize_item",
)


def install(pipeline_module):
    """Install the extracted pure functions onto the historical pipeline namespace."""
    for name in _EXPORTED_NAMES:
        setattr(pipeline_module, name, globals()[name])
    return pipeline_module
