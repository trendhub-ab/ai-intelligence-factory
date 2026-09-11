"""Read-only Groq article-generation parity harness.

The canonical Production prompt remains the source of truth. A deterministic transport
compiler shortens only duplicated editorial meta-guidance so Groq can accept the request;
evidence and publication contracts remain unchanged. This module never writes to Notion
or note.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_provider import GenerationRequest, GroqProvider, ProviderError
from groq_prompt_compiler import compile_article_prompt
from groq_rate_policy import COMPOUND_MINI


ARTICLE_STAGE = "article"
ARTICLE_MODEL = COMPOUND_MINI.model
MIN_ARTICLE_OUTPUT_TOKENS = 2000


def load_input(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = ("candidate_id", "source", "name", "url", "description", "source_context")
    missing = [key for key in required if not str(data.get(key) or "").strip()]
    if missing:
        raise ValueError("article parity fixture missing: " + ",".join(missing))
    return data


def _fit_output_budget(prompt: str, requested_output_tokens: int, reasoning_effort: str) -> tuple[int, int, int]:
    """Fit one article request inside Compound Mini's conservative Free Plan envelope."""
    if type(requested_output_tokens) is not int or requested_output_tokens <= 0:
        raise ProviderError("invalid_output_limit")
    estimator = GroqProvider(
        lambda _: None,
        token_budget=COMPOUND_MINI.safe_tpm,
        model=ARTICLE_MODEL,
    )
    _, minimum_request_estimate = estimator.prepare(
        GenerationRequest(prompt, 1, None, reasoning_effort)
    )
    fixed_input_and_framing = minimum_request_estimate - 1
    available_output = COMPOUND_MINI.safe_tpm - fixed_input_and_framing
    selected_output = min(requested_output_tokens, available_output, 8192)
    if selected_output < MIN_ARTICLE_OUTPUT_TOKENS:
        raise ProviderError("article_prompt_too_large_for_free_plan")
    total_estimate = fixed_input_and_framing + selected_output
    return selected_output, fixed_input_and_framing, total_estimate


def build_production_article_fixture(pipeline, input_path: str, output_path: str) -> dict[str, Any]:
    """Build canonical Production prompt, then compile only its editorial meta-guidance."""
    row = load_input(input_path)
    canonical_prompt = pipeline.build_decision_prompt(
        row["name"],
        row["url"],
        int(row.get("stars") or 0),
        row["description"],
        "",
        row["source"],
        source_context=row["source_context"],
        grounding_status_hint=row.get("grounding_status_hint") or "PRIMARY_SOURCE",
        evidence_metadata=row.get("evidence_metadata") or {},
        freshness=row.get("freshness") or {},
        previous_article="",
        evidence_result=row.get("evidence_result") or {},
    )
    compiled = compile_article_prompt(canonical_prompt)
    prompt = compiled.prompt
    reasoning_effort = row.get("reasoning_effort") or "medium"
    requested_output = int(row.get("max_output_tokens") or 4000)
    selected_output, fixed_estimate, total_estimate = _fit_output_budget(
        prompt, requested_output, reasoning_effort
    )
    payload = {
        "stage": ARTICLE_STAGE,
        "model": ARTICLE_MODEL,
        "rate_policy": COMPOUND_MINI.name,
        "prompt": prompt,
        "max_output_tokens": selected_output,
        "reasoning_effort": reasoning_effort,
        "provenance": {
            **(row.get("provenance") or {}),
            "candidate_id": row["candidate_id"],
            "source": row["source"],
            "source_context": row["source_context"],
            "screening_score": int(row.get("screening_score") or 0),
            "business_writes": 0,
            "production_prompt_builder": "pipeline.build_decision_prompt",
            "transport_compiler": "groq_prompt_compiler.compile_article_prompt",
            "canonical_prompt_sha256": compiled.source_sha256,
            "compiled_prompt_sha256": compiled.compiled_sha256,
            "canonical_prompt_bytes": compiled.source_bytes,
            "compiled_prompt_bytes": compiled.compiled_bytes,
            "compiled_replaced_sections": list(compiled.replaced_sections),
            "groq_model": ARTICLE_MODEL,
            "groq_safe_tpm": COMPOUND_MINI.safe_tpm,
            "requested_output_tokens": requested_output,
            "selected_output_tokens": selected_output,
            "estimated_input_and_framing_tokens": fixed_estimate,
            "estimated_total_tokens": total_estimate,
            "estimated_tpm_headroom": COMPOUND_MINI.safe_tpm - total_estimate,
            "external_tools": "disabled",
        },
    }
    Path(output_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def evaluate_groq_article_output(pipeline, groq_report_path: str, input_path: str, output_path: str) -> dict[str, Any]:
    """Parse Groq text with the canonical parser and run the current publication gate."""
    row = load_input(input_path)
    report = json.loads(Path(groq_report_path).read_text(encoding="utf-8"))
    result = report.get("result") or {}
    text = str(result.get("text") or "")
    if not text:
        raise ValueError("Groq article result text missing")
    parsed = pipeline._parse_gemini_response(text)
    source_info = {
        "context": row["source_context"],
        "method": row.get("grounding_status_hint") or "PRIMARY_SOURCE",
        "evidence_metadata": row.get("evidence_metadata") or {},
    }
    gate_state, gate_issues = pipeline.validate_publication_readiness_gate(
        parsed,
        row["source_context"],
        source_info,
    )
    gate_issues = list(gate_issues or [])
    article = str(parsed.get("note_draft") or "")
    quality_validated = gate_state == "PASS" and not gate_issues and bool(article.strip())
    evaluation = {
        "candidate_id": row["candidate_id"],
        "provider": report.get("provider"),
        "model": report.get("model"),
        "provider_calls": int(report.get("provider_calls") or 0),
        "prompt_tokens": int(result.get("prompt_tokens") or 0),
        "completion_tokens": int(result.get("completion_tokens") or 0),
        "parsed": bool(parsed),
        "article_chars": len(article),
        "decision_score": parsed.get("score"),
        "decision": parsed.get("decision"),
        "gate_state": gate_state,
        "gate_issues": gate_issues,
        "business_writes": 0,
        "persist_results": False,
        "quality_validated": quality_validated,
    }
    Path(output_path).write_text(json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return evaluation
