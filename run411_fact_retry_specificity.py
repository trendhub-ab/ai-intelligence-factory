"""Run411: make approved-lane Fact retry instructions explicit for proven residuals.

Real approved Run #15 showed that the canonical HARD quality retry could still leave two
Fact blockers after one model repair: an unsupported vague quantified duration (for example
``数日``) and ``LIMITATION_DROPPED``. Both blockers are valid; this overlay does not relax
them. It only makes the existing single quality-retry instruction concrete enough to repair
them in one pass.

Scope is intentionally narrow: install only in the exact owner-approved Run399 lane. No
extra model call, no request-budget increase, no Gate change, no normal Daily or X change.
If an isolated test fixture does not expose the canonical retry builder, this optional
quality overlay is a no-op; the underlying Fact Gate remains fail-closed.
"""
from __future__ import annotations

import re
from typing import Any

_INSTALLED_ATTR = "_run411_fact_retry_specificity_installed"


def _messages(reason_rows: list[dict]) -> str:
    return "\n".join(str((row or {}).get("message") or "") for row in (reason_rows or []))


def install(pipeline_module: Any) -> Any:
    if bool(getattr(pipeline_module, _INSTALLED_ATTR, False)):
        return pipeline_module

    original = getattr(pipeline_module, "build_dynamic_retry_instruction", None)
    if not callable(original):
        # Run411 strengthens an existing retry prompt; it is not itself a safety Gate.
        # Minimal unit fixtures that do not model generation/retry behavior may omit the
        # builder. Production always exposes it through the canonical runtime stack.
        return pipeline_module

    def build_dynamic_retry_instruction_with_fact_specificity(reason_rows: list[dict]):
        instruction, sections = original(reason_rows)
        messages = _messages(reason_rows)
        additions: list[str] = []

        vague_tokens = list(dict.fromkeys(re.findall(r"unsupported vague quantified claim:\s*([^,\n]+)", messages)))
        if vague_tokens:
            quoted = "、".join(f"『{token.strip()}』" for token in vague_tokens if token.strip())
            additions.append(
                f"・未裏付けの曖昧な数量表現 {quoted} は、この修復で必ず解消してください。"
                "一次Evidenceに同義の数量表現が明示されていない場合は、その数量語を削除し、"
                "数量を含まない事実範囲の表現へ局所置換してください。推測で別の期間・件数へ置き換えないでください。"
            )

        if "LIMITATION_DROPPED" in messages:
            additions.append(
                "・LIMITATION_DROPPED は、一次Evidenceに明示された limitation / issue / challenge / 制約 / 限界 / 課題が"
                "記事から消えている状態です。一次Evidenceに実在する制約を1つだけ短く復元してください。"
                "新しい制約を創作せず、一般論の『注意が必要』だけで済ませず、Evidenceにある対象・条件・限界が分かる文にしてください。"
            )

        if vague_tokens and "LIMITATION_DROPPED" in messages:
            additions.append(
                "・この2件は同じ1回のHARD quality retryで両方修正してください。片方を直して片方を残さないでください。"
                "修正後も既存Evidence・Decision・Score・固有名詞・根拠のある数値は保持してください。"
            )

        if additions:
            instruction = instruction.rstrip() + "\n\n【Run411 Fact Patch Precision】\n" + "\n".join(additions) + "\n"
        return instruction, sections

    pipeline_module.build_dynamic_retry_instruction = build_dynamic_retry_instruction_with_fact_specificity
    pipeline_module.RUN411_FACT_RETRY_SPECIFICITY = True
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
