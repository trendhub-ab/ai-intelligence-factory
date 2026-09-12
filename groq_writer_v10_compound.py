"""Groq-only Compound writer refinement.

Keeps GPT-OSS for the safe Decision Plan and Compound Mini for prose. This isolated Groq
lane expands only verified evidence already present in the ledger; it must not invent access,
benchmark structure, safeguard behavior, or operational details to satisfy article length.
Gemini Production remains untouched.
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

【V13 EVIDENCE-SLOTTED PROSE — 最終優先】
ARTICLEは必ず次の順序で、本文8段落＋`## `見出し3本にする。見出しは段落数に数えない。各段落はおおむね180〜230日本語文字、本文全体1500〜2000字。段落を省略してはいけない。

段落1：ExploitBenchの100%を驚きとして提示する。ただし同じ段落で「既知脆弱性からexploitを開発する評価」と範囲を説明する。100%を一般性能へ広げない。比喩を使うならここだけ。
段落2：2026年6〜8月の高深刻度V8脆弱性20件の評価と、評価中にzero-day 2件を発見してexploit chainの一部として利用した事実を書く。Ledgerにない検証方法・網羅性・詳細さを足さない。
見出し1：100%の意味を記事固有の日本語で示す。
段落3：ExploitBench 100%が「何を意味するか」と「何を意味しないか」を説明する。脆弱性リストの全件・全体・網羅という内部構成は書かない。
段落4：結果はdefault production configurationではなくDaybreak Blue access条件を反映する、とだけ書く。一般利用条件は一次資料から確認できない。別環境で再現する／しない、利用できる／できないは推測しない。
見出し2：Daybreak Blue条件と利用判断の違いを記事固有の日本語で示す。
段落5：能力向上を理由に一部の開発・公開を遅らせ、安全策を強化した事実を書く。その理由を新しい因果へ拡張しない。
段落6：アクセス制限、拒否訓練、system safety classifier、監視、misalignment detectionなど複数の安全策を適用するとLedgerにある範囲だけを書く。名称から機能・効果・自動性を説明しない。
見出し3：能力と安全策をどう読むかを記事固有の日本語で示す。
段落7：ここまでの確認済み事実を、非エンジニアの読者判断へつなぐ。新Fact・新しいリスク・新しい提供条件は追加しない。
段落8：必ず「私なら」で始める。今すぐ導入判断はせず、一次情報で利用条件を確認し、新しい一次情報が出た時点で再評価するというWATCH相当の判断で閉じる。申請・PoC・試用・アクセス取得を勧めない。

【V12実出力から追加した禁止事項】
- 「評価対象の脆弱性リスト全体」「その全リスト」「全リストで成功」「網羅した」など、ExploitBenchの内部構成を推測しない。
- 「OpenAI内部で詳細に検証」など、Ledgerにない検証の詳細度を足さない。
- Daybreak Blue以外の環境について「再現されない可能性」「同様に検出されるか不明」など、Ledgerにない比較・反実仮想を書かない。
- 「安全策は名称が示す通り」「名称どおり」など、名称から機能を推測する導入句自体を使わない。
- 「Astraが高度な脆弱性分析能力を持つことを示す」のように、測定結果をLedgerにない一般能力ラベルへ言い換えない。

【品質不変条件】
- 長さは新Factで埋めず、確認済みEvidenceについて「意味すること／意味しないこと／読者判断」の3層で展開する。
- 専門語密度はGemini Run359同期の契約に従い、Decisionに不要な名称は削除・意味カテゴリへ圧縮する。
- TITLE末尾は「。」または「？」。
- 箇条書き・番号リストは禁止。
- 最後の本文段落は必ず文末「。」または「？」まで完結させる。途中で文を切った状態で返してはいけない。
返答前に、本文8段落・見出し3本・1500字以上・最終文完結を自己確認する。
"""


def route_compound_writer_v10(path: str) -> dict:
    data = route_compound_writer(path)
    p = Path(path)
    prompt = data["prompt"]
    if "V13 EVIDENCE-SLOTTED PROSE" not in prompt:
        prompt = prompt.rstrip() + V10_CONTRACT
    if "Gemini Run359同期" not in prompt:
        prompt = prompt.rstrip() + "\n\n" + GROQ_READER_EXECUTION_CONTRACT + "\n"
    data["prompt"] = prompt
    # v12 returned finish_reason=stop but only 912 visible Japanese chars while spending
    # 3,593 completion tokens. Compound can consume substantial hidden/internal budget, so
    # reserve enough output space while staying far below the 60k Factory TPM envelope.
    data["max_output_tokens"] = 7800
    data["writer_route"] = "compound_mini_two_pass_v13_evidence_slotted"
    data["contract_version_v10"] = "groq_writer_v13_evidence_slotted+gemini_run359_provider_neutral"
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
    if article.rstrip() and not article.rstrip().endswith(("。", "？", "！")):
        issues.append("article_terminal_punctuation_missing")
    patterns = (
        (r"限定された脆弱性リスト|限られた脆弱性リスト|(?:脆弱性)?リスト全体|全リスト|網羅(?:した|する)", "unsupported_exploitbench_structure"),
        (r"OpenAI[^。！？\n]{0,40}(?:内部で)?詳細に検証|詳細な検証", "unsupported_validation_detail"),
        (r"認証プロセス|申請手順|取得方法|参加方法", "unsupported_access_procedure"),
        (r"Daybreak\s*Blue[^。！？\n]{0,120}(?:申請|取得|参加|一般提供|利用開始)", "daybreak_access_expansion"),
        (r"Daybreak\s*Blue[^。！？\n]{0,60}(?:限定された環境|限定環境|限られた環境)", "daybreak_environment_rewrite"),
        (r"(?:他|別)の環境[^。！？\n]{0,100}(?:再現|検出)[^。！？\n]{0,80}(?:不明|可能性)|再現されない可能性", "unsupported_environment_counterfactual"),
        (r"名称が示す通り|名称どおり", "safeguard_name_to_function_inference"),
        (r"(?:classifier|monitoring|misalignment\s*detection)[^。！？\n]{0,100}(?:検知する|判定する|自動的|リアルタイム|介入する|停止する)", "safeguard_name_to_function_inference"),
        (r"Astra[^。！？\n]{0,80}(?:高度な)?脆弱性分析能力[^。！？\n]{0,60}(?:持つ|有する|示す)", "unsupported_generalized_capability_label"),
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
