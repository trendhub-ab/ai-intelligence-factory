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
    estimator = GroqProvider(lambda _: None, token_budget=COMPOUND_MINI.safe_tpm, model=ARTICLE_MODEL)
    _, minimum_request_estimate = estimator.prepare(GenerationRequest(prompt, 1, None, reasoning_effort))
    fixed_input_and_framing = minimum_request_estimate - 1
    available_output = COMPOUND_MINI.safe_tpm - fixed_input_and_framing
    selected_output = min(requested_output_tokens, available_output, 8192)
    if selected_output < MIN_ARTICLE_OUTPUT_TOKENS:
        raise ProviderError("article_prompt_too_large_for_free_plan")
    total_estimate = fixed_input_and_framing + selected_output
    return selected_output, fixed_input_and_framing, total_estimate


def _production_like_source_info(pipeline, row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reconstruct the zero-network evidence state Production establishes before generation.

    Parity uses a saved, already-resolved primary source, so it must not run URL/network
    acquisition again.  It does, however, run the exact current evidence sufficiency policy and
    expose the same compatibility field (``sufficient``) consumed by Publication Readiness.
    """
    context = str(row["source_context"])
    explicit_metadata = row.get("evidence_metadata") or {}
    build_metadata = getattr(pipeline, "_build_evidence_metadata", None)
    evidence_metadata = explicit_metadata
    if not evidence_metadata and callable(build_metadata):
        evidence_metadata = build_metadata(context, False)
    freshness = row.get("freshness") or {}
    source_info = {
        "source": row["source"],
        "primary_url": row["url"],
        "primary_source_resolved": True,
        "context": context,
        "verification_context": context,
        "verification_context_length": len(context),
        "method": row.get("grounding_status_hint") or "PRIMARY_SOURCE",
        "deep_source_scanned": False,
        "freshness_status_available": bool(freshness.get("context")) or bool((row.get("provenance") or {}).get("primary_source_date")),
        "evidence_metadata": evidence_metadata,
        "evidence_documents": [{"url": row["url"], "kind": "primary", "text": context}],
        "checked_urls": {row["url"]},
        "supplement_candidates": [],
        "source_details": row.get("source_details") or {},
        "requested_action_risk_tier": "LOW",
    }
    evidence_result = pipeline.assess_evidence_sufficiency(source_info)
    source_info["evidence_sufficiency"] = evidence_result["state"]
    source_info["evidence_sufficient"] = evidence_result["state"] == pipeline.EVIDENCE_SUFFICIENT
    source_info["decision_scope_safe"] = bool(evidence_result.get("decision_scope_safe"))
    source_info["evidence_result"] = evidence_result
    source_info["sufficient"] = source_info["evidence_sufficient"]
    return source_info, evidence_result


def build_production_article_fixture(pipeline, input_path: str, output_path: str) -> dict[str, Any]:
    """Build canonical Production prompt, then compile only its editorial meta-guidance."""
    row = load_input(input_path)
    source_info, evidence_result = _production_like_source_info(pipeline, row)
    evidence_metadata = source_info["evidence_metadata"]
    canonical_prompt = pipeline.build_decision_prompt(
        row["name"], row["url"], int(row.get("stars") or 0), row["description"], "", row["source"],
        source_context=row["source_context"],
        grounding_status_hint=row.get("grounding_status_hint") or "PRIMARY_SOURCE",
        evidence_metadata=evidence_metadata,
        freshness=row.get("freshness") or {},
        previous_article="",
        evidence_result=evidence_result,
    )
    compiled = compile_article_prompt(canonical_prompt)
    prompt = compiled.prompt
    reasoning_effort = row.get("reasoning_effort") or "medium"
    requested_output = int(row.get("max_output_tokens") or 4000)
    selected_output, fixed_estimate, total_estimate = _fit_output_budget(prompt, requested_output, reasoning_effort)
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
            "evidence_state": evidence_result.get("state"),
            "evidence_sufficient": source_info["sufficient"],
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
    """Run the saved Groq output through Production evidence policy and all four quality gates."""
    row = load_input(input_path)
    report = json.loads(Path(groq_report_path).read_text(encoding="utf-8"))
    result = report.get("result") or {}
    text = str(result.get("text") or "")
    if not text:
        raise ValueError("Groq article result text missing")
    parsed = pipeline._parse_gemini_response(text)
    source_info, evidence_result = _production_like_source_info(pipeline, row)
    verification_context = source_info["verification_context"]
    freshness = row.get("freshness") or {}

    fact_ok, fact_failures = pipeline.validate_fact_gate(
        parsed,
        row["name"],
        source_context=verification_context,
        source=row["source"],
        evidence_metadata=source_info["evidence_metadata"],
        source_info=source_info,
        freshness=freshness,
        output_truncated=False,
    )
    editorial_ok, editorial_warnings = pipeline.validate_editorial_gate(parsed, row["name"])
    publication_state, publication_issues = pipeline.validate_publication_readiness_gate(
        parsed, verification_context, source_info
    )
    human_state, human_issues = pipeline.validate_human_appeal_gate(parsed, [])

    fact_failures = list(fact_failures or [])
    editorial_warnings = list(editorial_warnings or [])
    publication_issues = list(publication_issues or [])
    human_issues = list(human_issues or [])
    reason_rows = (
        pipeline.map_gate_reasons("fact", fact_failures)
        + pipeline.map_gate_reasons("editorial", editorial_warnings)
        + pipeline.map_gate_reasons("publication", publication_issues)
        + pipeline.map_gate_reasons("human_appeal", human_issues)
    )
    disposition = pipeline.gate_reason_disposition(reason_rows)
    publishable_dispositions = {pipeline.GATE_DISPOSITION_PASS, pipeline.GATE_DISPOSITION_PASS_WITH_WARNINGS}
    article = str(parsed.get("note_draft") or "")
    quality_validated = bool(article.strip()) and disposition in publishable_dispositions

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
        "evidence_state": evidence_result.get("state"),
        "evidence_sufficient": source_info["sufficient"],
        "evidence_checks": evidence_result.get("checks") or {},
        "fact_ok": bool(fact_ok),
        "fact_failures": fact_failures,
        "editorial_ok": bool(editorial_ok),
        "editorial_warnings": editorial_warnings,
        "publication_state": publication_state,
        "publication_issues": publication_issues,
        "human_appeal_state": human_state,
        "human_appeal_issues": human_issues,
        "gate_disposition": disposition,
        "reason_rows": reason_rows,
        # Backward-compatible aliases used by the existing live workflow summary.
        "gate_state": publication_state,
        "gate_issues": publication_issues,
        "business_writes": 0,
        "persist_results": False,
        "quality_validated": quality_validated,
    }
    Path(output_path).write_text(json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return evaluation
