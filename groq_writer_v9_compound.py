"""Groq-only v9 Writer route: GPT-OSS plans, Compound Mini writes prose.

This route exists only on the Groq validation branch. Gemini Production is untouched.
Compound tools are disabled by ai_provider and the resulting article is still required to
pass the same local Source Boundary checks and Production quality gates.
"""
from __future__ import annotations

import json
from pathlib import Path

from ai_provider import GenerationRequest, GroqProvider
from groq_rate_policy import COMPOUND_MINI, policy_for_model


class GroqWriterV9Error(RuntimeError):
    pass


V9_CONTRACT = r"""

【V9 COMPOUND WRITER CONTRACT — 読み物品質と事実境界】
- ARTICLEは1500〜2200日本語文字、8〜10段落。Markdown箇条書き・番号リストは禁止。
- 導入2〜3段落は発表要約から始めず、Ledgerにある具体的な数字・意外性から入り、「簡単に言えば／たとえば／使う側から見ると」に相当する自然な橋渡しを置く。
- `## `で始まる記事固有の見出しをちょうど3本。Astra、100%、zero-day、利用条件など本文固有の語を使い、汎用ラベルをそのまま見出しにしない。
- 専門語は初出時に普通の言葉で説明し、その後は正確な技術的意味へ戻す。
- 100%はExploitBenchの既知脆弱性からexploitを開発する評価結果としてのみ書き、一般性能へ広げない。
- Daybreak Blueは一次資料に記載された評価・アクセス文脈を超えて、取得方法、申請可否、一般提供、限定環境の証明へ拡張しない。この資料だけで不明な点は「確認できない」とする。
- 「実務利用には別途条件が必要」「未知のリスクが潜在する」など、Ledgerにない因果・条件・リスクを事実として追加しない。
- system safety classifier、misalignment detection等はLedgerにある範囲を超えて機能や効果を推測しない。
- 最終段落は内部Decisionコードを出さず、読者が今どう判断するかを人間の言葉で閉じる。未確認の申請・PoC・導入を勧めない。
- TITLE末尾は「。」または「？」。
"""


def route_compound_writer(path: str) -> dict:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("provider") != "groq" or data.get("stage") != "article":
        raise GroqWriterV9Error("writer_fixture_contract_invalid")
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise GroqWriterV9Error("writer_fixture_prompt_missing")
    if "V9 COMPOUND WRITER CONTRACT" not in prompt:
        data["prompt"] = prompt.rstrip() + V9_CONTRACT
    policy = policy_for_model(COMPOUND_MINI.model)
    data["model"] = COMPOUND_MINI.model
    data["rate_policy"] = policy.name
    data["max_output_tokens"] = 4200
    data["reasoning_effort"] = "low"  # ignored by Compound transport; kept for common request schema
    data["writer_route"] = "compound_mini_two_pass_v9"
    data["contract_version_v9"] = "groq_writer_v9_compound_reader_boundary"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def preflight_compound_writer(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("model") != COMPOUND_MINI.model:
        raise GroqWriterV9Error("writer_model_not_compound")
    policy = policy_for_model(COMPOUND_MINI.model)
    provider = GroqProvider(lambda _: None, token_budget=policy.safe_tpm, model=COMPOUND_MINI.model)
    payload, estimate = provider.prepare(GenerationRequest(
        data["prompt"], data["max_output_tokens"], None, data.get("reasoning_effort", "low")
    ))
    if estimate > policy.safe_tpm:
        raise GroqWriterV9Error("writer_preflight_tpm_exceeded")
    if payload.get("compound_custom", {}).get("tools", {}).get("enabled_tools") != []:
        raise GroqWriterV9Error("compound_tools_not_disabled")
    if payload.get("citation_options") != "disabled":
        raise GroqWriterV9Error("compound_citations_not_disabled")
    request_bytes = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return {
        "model": data["model"],
        "rate_policy": data["rate_policy"],
        "max_output_tokens": data["max_output_tokens"],
        "reserved_estimate": estimate,
        "safe_tpm": policy.safe_tpm,
        "headroom": policy.safe_tpm - estimate,
        "request_bytes": request_bytes,
        "external_tools": "disabled",
        "writer_route": data["writer_route"],
    }
