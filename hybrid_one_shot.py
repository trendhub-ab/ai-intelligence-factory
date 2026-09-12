"""Read-only Hybrid ONE-SHOT: saved Groq Decision Plan -> bounded Gemini writer -> Production gates.

This module never persists to Notion/note. The first live validation intentionally reuses
a previously validated Groq Decision Plan so Gemini writer quality can be isolated before
spending another Groq request in the same run.
"""
from __future__ import annotations

import json
from pathlib import Path

from groq_article_parity import load_input, _production_like_source_info
from hybrid_groq_plan import load_hybrid_plan_report
from hybrid_gemini_writer import (
    build_gemini_writer_prompt,
    deterministic_management_data,
    parse_gemini_writer_output,
)

PRIMARY_GEMINI_WRITER_MODEL = "gemini-3.7-flash"
SECONDARY_GEMINI_WRITER_MODEL = "gemini-3.8-flash"
HYBRID_GEMINI_WRITER_MODELS = (PRIMARY_GEMINI_WRITER_MODEL, SECONDARY_GEMINI_WRITER_MODEL)
HYBRID_KIND = "hybrid_final_writer"


def build_writer_fixture(input_path: str, plan_report_path: str, output_path: str) -> dict:
    item = load_input(input_path)
    plan = load_hybrid_plan_report(plan_report_path)
    prompt = build_gemini_writer_prompt(item, plan)
    fixture = {
        "candidate_id": item["candidate_id"],
        "provider_mode": "hybrid_groq_gemini",
        "plan_provider": "groq",
        "plan_source": "saved_validated_report",
        "decision_package": {
            "version": 1,
            "input": item,
            "plan_report": json.loads(Path(plan_report_path).read_text(encoding="utf-8")),
        },
        "writer_provider": "gemini",
        "writer_model": PRIMARY_GEMINI_WRITER_MODEL,
        "writer_models": list(HYBRID_GEMINI_WRITER_MODELS),
        "writer_prompt": prompt,
        "writer_max_output_tokens": 5000,
        "provider_calls_expected": {"groq_live": 0, "gemini_live_max": 2},
        "fallback_contract": "3.7 -> 3.8 only on 503/404; no quality retry; no model-pool fanout",
        "business_writes": 0,
        "persist_results": False,
    }
    Path(output_path).write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return fixture


def _management_surface(plan: dict) -> str:
    m = deterministic_management_data(plan)
    s = m["decision_score"]
    reasons = " / ".join(m["decision_reason"])
    return "\n".join([
        "=== MANAGEMENT DATA ===",
        f"・Source Summary: {m['source_summary']}",
        f"・What: {m['what']}",
        f"・Why Important: {m['why_important']}",
        f"・Decision: {m['decision']}",
        f"・Decision Reason: {reasons}",
        "・Decision Score: "
        f"Business Impact {s['business_impact']}/25; Technical Impact {s['technical_impact']}/25; "
        f"Urgency {s['urgency']}/20; Market Impact {s['market_impact']}/15; "
        f"Reliability {s['reliability']}/15; 合計 {s['total']}/100",
        f"・Action: {m['action']}",
        f"・Article Value: {m['article_value']}",
    ])


def assemble_canonical_response(pipeline, input_path: str, plan_report_path: str, writer_text: str) -> tuple[str, str, str]:
    """Assemble the exact parser-facing surface without asking Gemini to regenerate management data."""
    _ = load_input(input_path)
    plan = load_hybrid_plan_report(plan_report_path)
    title, article = parse_gemini_writer_output(writer_text)
    split_token = getattr(pipeline, "SECTION_SPLIT_TOKEN", None)
    if not isinstance(split_token, str) or not split_token.strip():
        raise RuntimeError("pipeline_section_split_token_missing")
    canonical = _management_surface(plan) + "\n" + split_token + "\n" + title + "\n\n" + article
    return canonical, title, article


def evaluate_writer_text(
    pipeline,
    input_path: str,
    plan_report_path: str,
    writer_text: str,
    output_path: str,
    *,
    writer_model: str = PRIMARY_GEMINI_WRITER_MODEL,
    gemini_live_calls: int = 1,
) -> dict:
    row = load_input(input_path)
    canonical, title, article = assemble_canonical_response(pipeline, input_path, plan_report_path, writer_text)
    parsed = pipeline._parse_gemini_response(canonical)
    if not parsed:
        raise RuntimeError("hybrid_parser_failed")
    parsed, polish_changes = pipeline._apply_final_japanese_polish(parsed)
    parsed, structure_changes = pipeline._apply_deterministic_structure_polish(parsed)
    source_info, evidence_result = _production_like_source_info(pipeline, row)
    context = source_info["verification_context"]
    freshness = row.get("freshness") or {}

    fact_ok, fact_failures = pipeline.validate_fact_gate(
        parsed, row["name"], source_context=context, source=row["source"],
        evidence_metadata=source_info["evidence_metadata"], source_info=source_info,
        freshness=freshness, output_truncated=False,
    )
    editorial_ok, editorial_warnings = pipeline.validate_editorial_gate(parsed, row["name"])
    publication_state, publication_issues = pipeline.validate_publication_readiness_gate(parsed, context, source_info)
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
    publishable = {pipeline.GATE_DISPOSITION_PASS, pipeline.GATE_DISPOSITION_PASS_WITH_WARNINGS}
    final_article = str(parsed.get("note_draft") or "")
    result = {
        "candidate_id": row["candidate_id"],
        "provider_mode": "hybrid_groq_gemini",
        "plan_provider": "groq",
        "plan_live_calls": 0,
        "writer_provider": "gemini",
        "writer_model": writer_model,
        "gemini_live_calls": int(gemini_live_calls),
        "title": title,
        "raw_article_chars": len(article),
        "article_chars": len(final_article),
        "decision": parsed.get("decision_text"),
        "decision_score": parsed.get("score"),
        "evidence_state": evidence_result.get("state"),
        "evidence_sufficient": source_info["sufficient"],
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
        "quality_validated": bool(final_article.strip()) and disposition in publishable,
        "polish_changes": list(polish_changes or []),
        "structure_changes": list(structure_changes or []),
        "business_writes": 0,
        "persist_results": False,
    }
    Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _provider_status_code(exc: BaseException) -> int | None:
    for value in (getattr(exc, "code", None), getattr(getattr(exc, "response", None), "status_code", None)):
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            pass
    return None


def _direct_writer_call(pipeline, fixture: dict, model: str):
    return pipeline._generate_via_chat(
        model,
        str(fixture["writer_prompt"]),
        config={"thinking_config": {"thinking_level": "medium"}, "max_output_tokens": int(fixture["writer_max_output_tokens"])},
        request_kind=HYBRID_KIND,
        reserve=0,
        request_context=f"hybrid-one-shot:{fixture['candidate_id']}",
        count_as_deep_dive=True,
        request_origin="hybrid_validation",
    )


def run_one_gemini_writer_call(pipeline, fixture_path: str, report_path: str) -> dict:
    """Compatibility helper: exactly one direct Gemini writer attempt."""
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    model = str(fixture["writer_model"])
    response = _direct_writer_call(pipeline, fixture, model)
    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        raise RuntimeError("hybrid_gemini_empty_output")
    report = {
        "candidate_id": fixture["candidate_id"], "provider": "gemini", "model": model,
        "provider_calls": 1, "attempts": [{"model": model, "status": "success"}],
        "business_writes": 0, "persist_results": False, "text": text,
    }
    Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def run_bounded_gemini_writer_calls(pipeline, fixture_path: str, report_path: str) -> dict:
    """Try 3.7 once, then 3.8 once only when 3.7 returns provider availability 503/404.

    No quality retry, no same-model retry, and no four-model Production pool fanout is
    allowed here. Any non-availability error fails closed immediately.
    """
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    models = tuple(fixture.get("writer_models") or HYBRID_GEMINI_WRITER_MODELS)
    if models != HYBRID_GEMINI_WRITER_MODELS:
        raise RuntimeError("hybrid_writer_model_contract_invalid")
    attempts: list[dict] = []
    last_error: BaseException | None = None
    for index, model in enumerate(models):
        try:
            response = _direct_writer_call(pipeline, fixture, model)
            text = str(getattr(response, "text", "") or "").strip()
            if not text:
                raise RuntimeError("hybrid_gemini_empty_output")
            attempts.append({"model": model, "status": "success"})
            report = {
                "candidate_id": fixture["candidate_id"], "provider": "gemini", "model": model,
                "provider_calls": len(attempts), "attempts": attempts,
                "business_writes": 0, "persist_results": False, "text": text,
            }
            Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return report
        except Exception as exc:
            last_error = exc
            status = _provider_status_code(exc)
            attempts.append({"model": model, "status": "error", "http_status": status})
            if status not in {503, 404} or index >= len(models) - 1:
                break
    failure = {
        "candidate_id": fixture["candidate_id"], "provider": "gemini", "model": None,
        "provider_calls": len(attempts), "attempts": attempts,
        "business_writes": 0, "persist_results": False, "error": type(last_error).__name__ if last_error else "unknown",
    }
    Path(report_path).write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise RuntimeError("hybrid_gemini_writer_unavailable") from last_error