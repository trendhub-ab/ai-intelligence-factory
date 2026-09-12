"""Run362: bounded Gemini request-shape A/B/C validation.

A is the already-observed Run361 lightweight control and is not re-sent.
This script sends exactly two live Gemini requests:
- B: compressed Production-shaped decision prompt
- C: fuller Production-shaped decision prompt

Safety:
- exactly two logical Gemini sends;
- Run360 must own retries (SDK attempts=1, no hidden retry);
- no candidate discovery, Notion, note, persistence, publication, or GitHub writes;
- same model for B/C;
- request metadata only is logged; prompt text is never logged.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

import pipeline
import gemini_provider_resilience

MODEL = os.environ.get("RUN362_MODEL", "gemini-3.7-flash").strip()
ALLOWED_MODELS = {"gemini-3.7-flash", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash"}


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


def _prompt(context_chars: int) -> str:
    source_context = _make_context(context_chars)
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
        "Run362 Request Shape Diagnostic",
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
        chat = pipeline.client.chats.create(model=MODEL, config={"max_output_tokens": max_output_tokens, "temperature": 0})
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


def main() -> None:
    if MODEL not in ALLOWED_MODELS:
        raise SystemExit(f"RUN362_MODEL not allowed: {MODEL}")
    if not str(getattr(pipeline, "GEMINI_API_KEY", "") or "").strip():
        raise SystemExit("GEMINI_API_KEY is required")

    gemini_provider_resilience.install(pipeline)
    retry_owner = getattr(pipeline, "GEMINI_RETRY_OWNER", None)
    sdk_attempts = getattr(pipeline, "GEMINI_SDK_RETRY_ATTEMPTS", None)
    if retry_owner != "factory" or sdk_attempts != 1:
        raise SystemExit(f"Run360 retry contract not active: owner={retry_owner!r}, sdk_attempts={sdk_attempts!r}")

    b_prompt = _prompt(3000)
    c_prompt = _prompt(18000)

    print(json.dumps({
        "run": 362,
        "control_A": {"source": "Run361 observed", "http_status": 200, "elapsed_seconds": 1.356, "sdk_attempts": 1},
        "persist": False,
        "notion_write": False,
        "note_write": False,
        "live_calls_planned": 2,
    }, ensure_ascii=False))

    b = _run_case("B_compressed_production_shape", b_prompt, 3000)
    time.sleep(2.0)
    c = _run_case("C_fuller_production_shape", c_prompt, int(getattr(pipeline, "GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS", 9000)))

    summary = {
        "run": 362,
        "status": "completed",
        "A_http": 200,
        "B_http": b.get("http_status"),
        "C_http": c.get("http_status"),
        "B_prompt_chars": b.get("prompt_chars"),
        "C_prompt_chars": c.get("prompt_chars"),
        "B_elapsed_seconds": b.get("elapsed_seconds"),
        "C_elapsed_seconds": c.get("elapsed_seconds"),
        "sdk_attempts_each": 1,
        "live_calls": 2,
        "persist": False,
    }
    print(json.dumps(summary, ensure_ascii=False))

    # Diagnostic completes even when B/C returns a provider error; the error itself is the measurement.
    # Only local contract/setup failures fail the workflow.


if __name__ == "__main__":
    main()
