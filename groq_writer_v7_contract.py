"""Groq-only writer v7 contract.

Aggregates reader and source-boundary failures so one saved output reveals every known
problem before another provider call. This module is isolated from Gemini Production.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from groq_writer_v5_contract import FORBIDDEN_PHRASES


class GroqWriterV7Error(RuntimeError):
    pass


V7_CONTRACT = r"""

【V7 COMPLETE READER + SOURCE BOUNDARY CONTRACT — 最優先】
返答前に次をすべて満たしているか自己点検してください。1つでも不足したまま返してはいけません。
- TITLEは日本語で、末尾を「。」または「？」にする。
- ARTICLE本文は1500〜2100日本語文字。新Factを足して長くせず、既存Evidenceの意味・条件・読者判断を自然文で展開する。
- 導入の後に `## ` で始まる記事固有の見出しをちょうど3個置く。見出しは「なぜ重要」「仕組み」「リスク」「次にすべきこと」等の汎用ラベルを使わない。
- 本文は8〜11段落。箇条書き・番号リストは禁止。
- 100%はExploitBenchの測定対象・条件から切り離さない。「全般に100%」「何でもできる」へ拡張しない。
- Daybreak Blueは評価条件としてのみ扱う。アクセスの取得方法、申請、参加方法、将来利用可否を推測しない。確認できなければ「この一次資料から利用条件は確認できない」と書く。
- 「Daybreak Blueに限られた環境でのみ確認」「限定環境でのみ提供」「高度に制御された環境だと裏付ける」のように、一次資料を越えて環境・提供範囲を断定しない。
- 安全策は名称以上の機能・効果を推測しない。
- 最後はWATCHに沿い、「私なら、今すぐ導入判断はせず、一次情報で利用条件を確認する」と同等の判断で閉じる。未確認のアクセス取得・申請を次の行動にしない。
"""

NEW_FORBIDDEN = (
    "Daybreak Blueアクセスがどのように取得",
    "Daybreak Blueのアクセスがどのように取得",
    "Daybreak Blueを申請",
    "Daybreak Blueへの申請",
    "限られた環境でのみ確認",
    "限定された環境でのみ確認",
    "高度に制御されたものであることを裏付け",
    "高度に制御された環境であることを裏付け",
)


def harden_writer_fixture_v7(path: str) -> dict:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("provider") != "groq" or data.get("stage") != "article":
        raise GroqWriterV7Error("writer_fixture_contract_invalid")
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise GroqWriterV7Error("writer_fixture_prompt_missing")
    if "V7 COMPLETE READER + SOURCE BOUNDARY CONTRACT" not in prompt:
        data["prompt"] = prompt.rstrip() + V7_CONTRACT
    data["contract_version_v7"] = "groq_writer_v7_aggregate_reader_boundary"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def _extract(text: str) -> tuple[str, str]:
    match = re.fullmatch(r"\s*===TITLE===\s*\n(.+?)\n===ARTICLE===\s*\n(.+)\s*", text or "", re.S)
    if not match:
        raise GroqWriterV7Error("writer_output_format_invalid")
    return match.group(1).strip(), match.group(2).strip()


def _prose_paragraphs(article: str) -> list[str]:
    """Count prose even when a markdown heading and its following prose share one block."""
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", article):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        if lines and re.match(r"^##\s+", lines[0]):
            block = "\n".join(lines[1:]).strip()
        if block:
            paragraphs.append(block)
    return paragraphs


def inspect_writer_report(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        text = data["result"]["text"]
    except (KeyError, TypeError):
        raise GroqWriterV7Error("writer_result_missing") from None
    title, article = _extract(text)
    issues: list[str] = []

    for phrase in FORBIDDEN_PHRASES + NEW_FORBIDDEN:
        if phrase in article:
            issues.append("source_boundary:" + phrase)

    patterns = (
        (r"Daybreak\s*Blue[^。！？\n]{0,120}(?:取得|申請|参加|利用開始)", "daybreak_access_assumption"),
        (r"(?:取得|申請|参加)[^。！？\n]{0,80}Daybreak\s*Blue", "daybreak_access_assumption"),
        (r"(?:評価環境|環境)[^。！？\n]{0,100}(?:高度に制御|厳格に制御)[^。！？\n]{0,100}(?:裏付|示して)", "controlled_environment_inference"),
        (r"Preparedness\s*Framework[^。！？\n]{0,90}防御力", "preparedness_mistranslation"),
        (r"system\s*safety\s*classifier[^。！？\n]{0,90}(?:リアルタイム|自動|判定|評価)", "safeguard_function_inference"),
        (r"misalignment\s*detection[^。！？\n]{0,100}(?:自動|介入|停止|修正)", "safeguard_function_inference"),
    )
    for pattern, code in patterns:
        if re.search(pattern, article, re.I):
            issues.append(code)

    if len(article) < 1500:
        issues.append(f"article_too_short:{len(article)}")
    if len(article) > 2100:
        issues.append(f"article_too_long:{len(article)}")

    headings = re.findall(r"(?m)^##\s+\S.+$", article)
    if len(headings) != 3:
        issues.append(f"heading_count:{len(headings)}")
    generic_heading = re.compile(r"^##\s*(?:なぜ重要|仕組み|リスク|次にすべきこと|最終判断|何が起きた)[？?]?$", re.M)
    if generic_heading.search(article):
        issues.append("generic_heading")

    if re.search(r"(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+)", article):
        issues.append("list_output")
    paragraphs = _prose_paragraphs(article)
    if not 8 <= len(paragraphs) <= 11:
        issues.append(f"paragraph_count:{len(paragraphs)}")
    if not re.search(r"(?:たとえば|例えば|簡単に言えば|使う側から見ると|似ています|ようなもの)", article[:1000]):
        issues.append("reader_bridge_missing")
    if not re.search(r"(?:私なら|私たちなら)", article[-700:]):
        issues.append("decision_voice_missing")
    if not title.endswith(("。", "？")):
        issues.append("title_punctuation")

    return {
        "title": title,
        "article": article,
        "article_chars": len(article),
        "headings": headings,
        "paragraphs": len(paragraphs),
        "issues": sorted(set(issues)),
    }


def validate_writer_report_v7(path: str) -> dict:
    inspected = inspect_writer_report(path)
    if inspected["issues"]:
        raise GroqWriterV7Error("writer_v7_contract:" + "|".join(inspected["issues"]))
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["v7_source_boundary_validated"] = True
    data["v7_reader_contract_validated"] = True
    data["v7_article_chars"] = inspected["article_chars"]
    data["v7_headings"] = len(inspected["headings"])
    data["v7_paragraphs"] = inspected["paragraphs"]
    return data
