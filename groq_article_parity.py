"""Read-only Groq article-generation parity harness.

This module deliberately reuses the current Production article prompt builder and
publication gate. It never writes to Notion or note. The live Groq call remains in
``groq_validation`` so the same persistent reservation ledger protects all provider
experiments.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ARTICLE_STAGE = "article"


def load_input(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = ("candidate_id", "source", "name", "url", "description", "source_context")
    missing = [key for key in required if not str(data.get(key) or "").strip()]
    if missing:
        raise ValueError("article parity fixture missing: " + ",".join(missing))
    return data


def build_production_article_fixture(pipeline, input_path: str, output_path: str) -> dict[str, Any]:
    """Materialize the *current* Production article prompt for one saved candidate."""
    row = load_input(input_path)
    prompt = pipeline.build_decision_prompt(
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
    payload = {
        "stage": ARTICLE_STAGE,
        "prompt": prompt,
        "max_output_tokens": int(row.get("max_output_tokens") or 8000),
        "reasoning_effort": row.get("reasoning_effort") or "medium",
        "provenance": {
            **(row.get("provenance") or {}),
            "candidate_id": row["candidate_id"],
            "source": row["source"],
            "source_context": row["source_context"],
            "screening_score": int(row.get("screening_score") or 0),
            "business_writes": 0,
            "production_prompt_builder": "pipeline.build_decision_prompt",
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
    article = str(parsed.get("note_draft") or "")
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
        "gate_issues": list(gate_issues or []),
        "business_writes": 0,
        "persist_results": False,
        "quality_validated": True,
    }
    Path(output_path).write_text(json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return evaluation
