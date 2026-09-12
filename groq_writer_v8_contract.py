"""Groq-only writer v8: explicit prose structure and final source-boundary tightening."""
from __future__ import annotations

import json
from pathlib import Path
import re

from groq_writer_v7_contract import inspect_writer_report


class GroqWriterV8Error(RuntimeError):
    pass


V8_CONTRACT = r"""

【V8 OUTPUT SHAPE — 厳守】
- ARTICLEは10段落、1500〜2000日本語文字。
- `## ` 見出しを3本。導入2段落後、5段落目前、8段落目前に置く。
- 見出しはAstra/100%/利用条件など記事固有語を使い、汎用ラベルは禁止。
- 各段落140〜210字を目安にし、短文で段落数を稼がない。
- 「導入には別途のアクセス権・運用条件が必要」と断定しない。「この一次資料から一般利用条件は確認できない」まで。
- TITLE末尾は「。」または「？」。
返答前に10段落・3見出し・1500字以上を確認する。
"""


def harden_writer_fixture_v8(path: str) -> dict:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("provider") != "groq" or data.get("stage") != "article":
        raise GroqWriterV8Error("writer_fixture_contract_invalid")
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise GroqWriterV8Error("writer_fixture_prompt_missing")
    if "V8 OUTPUT SHAPE" not in prompt:
        data["prompt"] = prompt.rstrip() + V8_CONTRACT
    data["max_output_tokens"] = 2800
    data["contract_version_v8"] = "groq_writer_v8_explicit_structure"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def inspect_writer_report_v8(path: str) -> dict:
    inspected = inspect_writer_report(path)
    article = inspected["article"]
    issues = list(inspected["issues"])
    if inspected["paragraphs"] != 10:
        issues.append(f"v8_paragraph_count:{inspected['paragraphs']}")
    if len(inspected["headings"]) != 3:
        issues.append(f"v8_heading_count:{len(inspected['headings'])}")
    if len(article) < 1500:
        issues.append(f"v8_article_too_short:{len(article)}")
    if re.search(r"導入(?:に|するには)[^。！？\n]{0,80}(?:アクセス権|アクセス条件|運用条件)[^。！？\n]{0,60}(?:必要|要する)", article):
        issues.append("unconfirmed_access_requirement_assertion")
    if re.search(r"(?:別途|追加の)[^。！？\n]{0,40}(?:アクセス権|運用条件)[^。！？\n]{0,50}(?:必要|要する)", article):
        issues.append("unconfirmed_access_requirement_assertion")
    inspected["issues"] = sorted(set(issues))
    return inspected


def validate_writer_report_v8(path: str) -> dict:
    inspected = inspect_writer_report_v8(path)
    if inspected["issues"]:
        raise GroqWriterV8Error("writer_v8_contract:" + "|".join(inspected["issues"]))
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["v8_contract_validated"] = True
    data["v8_article_chars"] = inspected["article_chars"]
    data["v8_headings"] = len(inspected["headings"])
    data["v8_paragraphs"] = inspected["paragraphs"]
    return data
