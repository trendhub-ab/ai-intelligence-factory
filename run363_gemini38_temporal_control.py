"""Run363: Gemini 3.8 same-run temporal control around one Production-shaped request.

Sequence is exactly A1 lightweight -> B Production-shaped -> A2 lightweight.
This removes the main temporal confound left by Run362 without touching Gemini 3.7.

Safety:
- model is fixed to gemini-3.8-flash;
- exactly three logical sends at most;
- SDK attempts=1, no hidden retry;
- no Factory retry/fallback in this diagnostic;
- no Notion, note, persistence, publication, discovery, or GitHub writes;
- provider errors are measurements and do not trigger retries.
"""
from __future__ import annotations

import json
import time
from typing import Any

import pipeline
import gemini_provider_resilience

MODEL = "gemini-3.8-flash"
LIGHT_PROMPT = "Transport diagnostic only. Reply exactly RUN363_OK."
LIGHT_MAX_OUTPUT_TOKENS = 64
PRODUCTION_CONTEXT_CHARS = 3000
PRODUCTION_MAX_OUTPUT_TOKENS = 3000


def _status_code(exc: Exception) -> int | None:
    for attr in ("code", "status_code"):
        value = getattr(exc, attr, None)
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            pass
    text = str(exc)
    for code in (503, 429, 404, 500, 502, 504):
        if str(code) in text:
            return code
    return None


def _make_context(target_chars: int) -> str:
    line = (
        "Primary-source evidence: official documentation states that the system exposes a provider API, "
        "documents configuration constraints, and requires validation before production adoption. "
        "No comparative superiority, ROI, cost saving, or production SLA is claimed by this evidence.\n"
    )
    return (line * ((target_chars // len(line)) + 2))[:target_chars]


def _production_prompt() -> str:
    source_context = _make_context(PRODUCTION_CONTEXT_CHARS)
    evidence_metadata: dict[str, Any] = {
        "primary_source_count": 1,
        "source_types": ["official_documentation"],
        "context_chars": len(source_context),
    }
    evidence_result: dict[str, Any] = {
        "status": "sufficient",
        "primary_sources": [
            {"url": "https://example.com/official-docs", "authority": "primary", "summary": "official documentation"}
        ],
    }
    return pipeline.build_decision_prompt(
        "Run363 Gemini 3.8 Temporal Control",
        "https://example.com/official-docs",
        0,
        "A deterministic diagnostic candidate used only to measure Gemini request-shape transport behavior.",
        source="GitHub",
        source_context=source_context,
        grounding_status_hint=getattr(pipeline, "GROUNDING_SOURCE_NATIVE", "source_native"),
        evidence_metadata=evidence_metadata,
        freshness={"status": "current", "checked_at": "2026-09-12"},
        evidence_result=evidence_result,
    )


def _run_case(label: str, prompt: str, max_output_tokens: int) -> dict[str, Any]:
    started = time.monotonic()
    result: dict[str, Any] = {
        "case": label,
        "model": MODEL,
        "prompt_chars": len(prompt),
        "prompt_bytes": len(prompt.encode("utf-8")),
        "max_output_tokens": max_output_tokens,
        "sdk_attempts": getattr(pipeline, "GEMINI_SDK_RETRY_ATTEMPTS", None),
        "retry_owner": getattr(pipeline, "GEMINI_RETRY_OWNER", None),
        "logical_calls": 1,
    }
    try:
        chat = pipeline.client.chats.create(
            model=MODEL,
            config={"max_output_tokens": max_output_tokens, "temperature": 0},
        )
        response = chat.send_message(prompt)
        result.update({
            "transport": "success",
            "http_status": 200,
            "response_text_chars": len(str(getattr(response, "text", "") or "")),
        })
    except Exception as exc:
        result.update({
            "transport": "error",
            "http_status": _status_code(exc),
            "error_type": type(exc).__name__,
            "error": str(exc)[:400],
        })
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    print(json.dumps(result, ensure_ascii=False))
    return result


def classify(a1: dict[str, Any], b: dict[str, Any], a2: dict[str, Any]) -> str:
    triple = (a1.get("http_status"), b.get("http_status"), a2.get("http_status"))
    if triple == (200, 503, 200):
        return "request_shape_strongly_implicated"
    if triple == (200, 200, 200):
        return "no_503_reproduction_on_gemini38"
    if triple == (503, 503, 503):
        return "provider_high_demand_confounded"
    return "mixed_or_inconclusive"


def main() -> None:
    if not str(getattr(pipeline, "GEMINI_API_KEY", "") or "").strip():
        raise SystemExit("GEMINI_API_KEY is required")

    gemini_provider_resilience.install(pipeline)
    retry_owner = getattr(pipeline, "GEMINI_RETRY_OWNER", None)
    sdk_attempts = getattr(pipeline, "GEMINI_SDK_RETRY_ATTEMPTS", None)
    if retry_owner != "factory" or sdk_attempts != 1:
        raise SystemExit(f"Run360 retry contract not active: owner={retry_owner!r}, sdk_attempts={sdk_attempts!r}")

    production_prompt = _production_prompt()
    print(json.dumps({
        "run": 363,
        "model": MODEL,
        "sequence": ["A1_light", "B_production_shape", "A2_light"],
        "live_calls_planned": 3,
        "gemini_37_calls": 0,
        "persist": False,
        "notion_write": False,
        "note_write": False,
        "publication": False,
    }, ensure_ascii=False))

    a1 = _run_case("A1_light", LIGHT_PROMPT, LIGHT_MAX_OUTPUT_TOKENS)
    time.sleep(2.0)
    b = _run_case("B_production_shape", production_prompt, PRODUCTION_MAX_OUTPUT_TOKENS)
    time.sleep(2.0)
    a2 = _run_case("A2_light", LIGHT_PROMPT, LIGHT_MAX_OUTPUT_TOKENS)

    summary = {
        "run": 363,
        "status": "completed",
        "model": MODEL,
        "A1_http": a1.get("http_status"),
        "B_http": b.get("http_status"),
        "A2_http": a2.get("http_status"),
        "A1_elapsed_seconds": a1.get("elapsed_seconds"),
        "B_elapsed_seconds": b.get("elapsed_seconds"),
        "A2_elapsed_seconds": a2.get("elapsed_seconds"),
        "B_prompt_chars": b.get("prompt_chars"),
        "classification": classify(a1, b, a2),
        "sdk_attempts_each": 1,
        "live_calls": 3,
        "gemini_37_calls": 0,
        "persist": False,
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
