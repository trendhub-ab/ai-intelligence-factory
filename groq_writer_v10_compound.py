"""Groq-only v10 Compound writer refinement.

Keeps GPT-OSS for the safe Decision Plan and Compound Mini for prose. V10 expands only
verified evidence already present in the B0049 ledger; it must not invent access or
operational details to satisfy article length. Gemini Production remains untouched.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from groq_quality_contract_sync import GROQ_READER_EXECUTION_CONTRACT
from groq_writer_v9_compound import (
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
- ExploitBenchは「既知脆弱性からexploitを開発する評価」と必ず説明する。benchmarkという語だけで済ませず、100%を一般性能へ広げない。
- 「限定された脆弱性リスト」「そのリスト全体を網羅」など、LedgerにないExploitBenchの内部構成を追加しない。
- 「認証プロセス」「申請手順」「取得方法」「参加方法」など、Ledgerにないアクセス手続きを追加しない。
- Daybreak Blueを「限定された環境」と言い換えない。確認済みなのはDaybreak Blue access条件で得た結果であり、一般利用条件はこの資料から確認できない、までに留める。
- 安全策はLedgerにある名称と「複数の安全策を適用する」という範囲を超えない。classifierやmonitoring等の名称から実装機能・効果・自動性を推測しない。
- 「高度な能力自体がリスクと見なされた」「未知のリスクが潜在する」など、一次資料にない因果・評価を事実化しない。
- 比喩は最大1つ。比喩は技術的事実ではなく理解補助だと分かる自然な書き方にする。
- Decision Scoreは管理データの合計値と矛盾させない。記事本文では内部スコアや内部Decisionコードを出さず、WATCH相当の慎重な判断にする。低〜中程度のスコアなのに「極めて高い」「非常に高い緊急性・市場影響」などと誇張しない。
- 最終段落は、現時点では導入判断を急がず一次情報で利用条件を確認する、というWATCH相当の判断で閉じる。
返答前に、8段落・3見出し・1500字以上を自己確認する。
"""


def route_compound_writer_v10(path: str) -> dict:
    data = route_compound_writer(path)
    p = Path(path)
    prompt = data["prompt"]
    if "V10 EVIDENCE-DENSE PROSE" not in prompt:
        prompt = prompt.rstrip() + V10_CONTRACT
    if "Gemini Run359同期" not in prompt:
        prompt = prompt.rstrip() + "\n\n" + GROQ_READER_EXECUTION_CONTRACT + "\n"
    data["prompt"] = prompt
    data["max_output_tokens"] = 4400
    data["writer_route"] = "compound_mini_two_pass_v10_evidence_dense"
    data["contract_version_v10"] = "groq_writer_v10_evidence_dense+gemini_run359_provider_neutral"
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
        (r"Daybreak\s*Blue[^。！？\n]{0,60}(?:限定された環境|限定環境|限られた環境)", "daybreak_environment_rewrite"),
        (r"(?:名称が示す通り|名称どおり)[^。！？\n]{0,80}(?:機能|組み込)", "safeguard_name_to_function_inference"),
        (r"(?:classifier|monitoring|misalignment\s*detection)[^。！？\n]{0,100}(?:検知する|判定する|自動的|リアルタイム|介入する|停止する)", "safeguard_name_to_function_inference"),
        (r"(?:高度な|高い)[^。！？\n]{0,60}(?:サイバー)?能力[^。！？\n]{0,80}(?:自体が)?リスクと見な", "unsupported_capability_risk_causality"),
        (r"未知のリスク[^。！？\n]{0,60}(?:潜在|存在|ある)", "unsupported_unknown_risk"),
        (r"(?:緊急性|市場(?:への)?影響)[^。！？\n]{0,50}(?:極めて高|非常に高)", "score_narrative_overstatement"),
    )
    for pattern, code in patterns:
        if re.search(pattern, article, re.I):
            issues.append(code)
    # The Production Fact Gate expects benchmark claims to carry their verified scope.
    if ("ExploitBench" in article or "100%" in article) and not re.search(r"既知脆弱性[^。！？\n]{0,80}(?:exploit|エクスプロイト)[^。！？\n]{0,40}(?:開発|作成)", article, re.I):
        issues.append("exploitbench_scope_missing")
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
