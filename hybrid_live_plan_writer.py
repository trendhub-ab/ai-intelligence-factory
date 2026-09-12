"""Live Hybrid validation adapter: one Groq Decision Plan -> bounded Gemini Writer.

This module is intentionally provider-free and persistence-free. It only corrects
validation metadata so artifacts distinguish a live Groq Plan from saved-plan tests.
Notion/note writes are never performed here.
"""
from __future__ import annotations

import json
from pathlib import Path

from hybrid_one_shot import build_writer_fixture, evaluate_writer_text


def build_live_writer_fixture(input_path: str, plan_report_path: str, output_path: str) -> dict:
    fixture = build_writer_fixture(input_path, plan_report_path, output_path)
    fixture["plan_source"] = "live_groq_report"
    fixture["provider_calls_expected"] = {"groq_live": 1, "gemini_live_max": 2}
    fixture["validation_scope"] = "live_groq_plan_to_bounded_gemini_writer"
    fixture["business_writes"] = 0
    fixture["persist_results"] = False
    Path(output_path).write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return fixture


def evaluate_live_writer_text(
    pipeline,
    input_path: str,
    plan_report_path: str,
    writer_text: str,
    output_path: str,
    *,
    writer_model: str,
    gemini_live_calls: int,
) -> dict:
    result = evaluate_writer_text(
        pipeline,
        input_path,
        plan_report_path,
        writer_text,
        output_path,
        writer_model=writer_model,
        gemini_live_calls=gemini_live_calls,
    )
    result["plan_source"] = "live_groq_report"
    result["plan_live_calls"] = 1
    result["total_live_provider_calls"] = 1 + int(gemini_live_calls)
    result["business_writes"] = 0
    result["persist_results"] = False
    Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
