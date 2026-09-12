"""Groq writer v6 route: use GPT-OSS 120B for the compact article-only pass.

The original full Production prompt cannot fit the GPT-OSS Free Plan 8K TPM lane, but the
new two-pass writer prompt is small enough after planning is separated. This module changes
only the isolated Groq validation fixture; Gemini Production remains untouched.
"""
from __future__ import annotations

import json
from pathlib import Path

from ai_provider import GenerationRequest, GroqProvider
from groq_rate_policy import GPT_OSS_120B


class GroqWriterV6RouteError(RuntimeError):
    pass


WRITER_MAX_OUTPUT_TOKENS = 2600
WRITER_SAFE_TPM = 7000


def route_writer_fixture(path: str) -> dict:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("provider") != "groq" or data.get("stage") != "article":
        raise GroqWriterV6RouteError("writer_fixture_contract_invalid")
    if data.get("schema") is not None:
        raise GroqWriterV6RouteError("writer_schema_must_be_none")
    data["model"] = GPT_OSS_120B.model
    data["rate_policy"] = GPT_OSS_120B.name
    data["max_output_tokens"] = WRITER_MAX_OUTPUT_TOKENS
    data["reasoning_effort"] = "medium"
    data["writer_route"] = "gpt_oss_120b_compact_writer_v6"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def preflight_writer_fixture(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    provider = GroqProvider(lambda _: None, token_budget=WRITER_SAFE_TPM, model=data["model"])
    payload, estimate = provider.prepare(GenerationRequest(
        data["prompt"], data["max_output_tokens"], data.get("schema"), data["reasoning_effort"]
    ))
    if estimate > WRITER_SAFE_TPM:
        raise GroqWriterV6RouteError("writer_tpm_budget_exceeded")
    if payload.get("model") != GPT_OSS_120B.model:
        raise GroqWriterV6RouteError("writer_model_route_mismatch")
    if "compound_custom" in payload or "citation_options" in payload:
        raise GroqWriterV6RouteError("compound_controls_leaked_into_gpt_writer")
    return {
        "model": data["model"],
        "rate_policy": data["rate_policy"],
        "max_output_tokens": data["max_output_tokens"],
        "reserved_estimate": estimate,
        "safe_tpm": WRITER_SAFE_TPM,
        "headroom": WRITER_SAFE_TPM - estimate,
        "writer_route": data["writer_route"],
    }
