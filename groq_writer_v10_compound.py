"""Groq-only v10 Compound writer refinement.

Keeps GPT-OSS for the safe Decision Plan and Compound Mini for prose. V10 expands only
verified evidence already present in the B0049 ledger; it must not invent access or
operational details to satisfy article length.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from groq_writer_v9_compound import (
    GroqWriterV9Error,
    route_compound_writer,
    preflight_compound_writer,
    inspect_compound_writer_v9,
)


class GroqWriterV10Error(RuntimeError):
    pass


V10_CONTRACT = r"""

【V10 EVIDENCE-DENSE PROSE — 最終優先】
- ARTICLE本文は8段落。各段落はおおむね190〜240日本語文字とし、本文全体を1500〜2000字にする。
- `## `見出しはちょうど3本。見出しは段落数に数えない。
- 長さは新しいFactで埋めない。次の一次Evidenceを、条件を保ったまま「何を意味するか」「何を意味しないか」「読者判断がどう変わるか」で説明して厚くする：ExploitBench 100%、2026年6〜8月の高深刻度V8脆弱性20件、評価中に発見したzero-day 2件、結果はdefault production configurationではなくDaybreak Blue access条件、能力向上に伴う一部開発・公開の遅延、安全策の強化。
- 「限定された脆弱性リスト」「そのリスト全体を網羅」など、LedgerにないExploitBenchの内部構成を追加しない。
- 「認証プロセス」「申請手順」「取得方法」「参加方法」など、Ledgerにないアクセス手続きを追加しない。
- Daybreak Blueについては「この資料から一般利用条件は確認できない」まで。取得・申請・一般提供を推測しない。
- 安全策はLedgerにある名称と「複数の安全策を適用する」という範囲を超えて、具体動作・効果・保証を追加しない。
- 比喩は最大1つ。比喩は技術的事実ではなく理解補助だと分かる自然な書き方にする。
- 最終段落は、現時点では導入判断を急がず一次情報で利用条件を確認する、というWATCH相当の判断で閉じる。
返答前に、8段落・3見出し・1500字以上を自己確認する。
"""


def route_compound_writer_v10(path: str) -> dict:
    data = route_compound_writer(path)
    p = Path(path)
    prompt = data["prompt"]
    if "V10 EVIDENCE-DENSE PROSE" not in prompt:
        data["prompt"] = prompt.rstrip() + V10_CONTRACT
    data["max_output_tokens"] = 4400
    data["writer_route"] = "compound_mini_two_pass_v10_evidence_dense"
    data["contract_version_v10"] = "groq_writer_v10_evidence_dense"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def preflight_compound_writer_v10(path: str) -> dict:
    return preflight_compound_writer(path)


def inspect_compound_writer_v10(path: str) -> dict:
    inspected = inspect_compound_writer_v9(path)
    article = inspected["article"]
    issues = [x for x in inspected["issues"] if not x.startswith("v9_paragraph_count:") and not x.startswith("v9_article_chars:") and not x.startswith("article_too_short:")]
    if not 1500 <= len(article) <= 2000:
        issues.append(f"v10_article_chars:{len(article)}")
    if inspected["paragraphs"] != 8:
        issues.append(f"v10_paragraph_count:{inspected['paragraphs']}")
    if len(inspected["headings"]) != 3:
        issues.append(f"v10_heading_count:{len(inspected['headings'])}")
    patterns = (
        (r"限定された脆弱性リスト|限られた脆弱性リスト|リスト全体を網羅", "unsupported_exploitbench_structure"),
        (r"認証プロセス|申請手順|取得方法|参加方法", "unsupported_access_procedure"),
        (r"Daybreak\s*Blue[^。！？\n]{0,120}(?:申請|取得|参加|一般提供|利用開始)", "daybreak_access_expansion"),
    )
    for pattern, code in patterns:
        if re.search(pattern, article, re.I):
            issues.append(code)
    inspected["issues"] = sorted(set(issues))
    return inspected


def validate_compound_writer_v10(path: str) -> dict:
    inspected = inspect_compound_writer_v10(path)
    if inspected["issues"]:
        raise GroqWriterV10Error("writer_v10_contract:" + "|".join(inspected["issues"]))
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["v10_contract_validated"] = True
    data["v10_article_chars"] = inspected["article_chars"]
    data["v10_headings"] = len(inspected["headings"])
    data["v10_paragraphs"] = inspected["paragraphs"]
    return data
