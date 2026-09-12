"""Run361: one-request Gemini live transport validation.

Safety contract:
- exactly one logical Gemini send_message call;
- google-genai SDK retries must already be disabled by Run360 (attempts=1);
- no candidate discovery, Notion, note, GitHub persistence, or publication side effects;
- small output cap and fixed prompt;
- fail closed if retry ownership is not Factory-only.
"""
from __future__ import annotations

import json
import os
import time

import pipeline
import gemini_provider_resilience

ALLOWED_MODELS = {
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
}


def main() -> None:
    model = os.environ.get("RUN361_MODEL", "gemini-3.7-flash").strip()
    if model not in ALLOWED_MODELS:
        raise SystemExit(f"RUN361_MODEL not allowed: {model}")
    if not str(getattr(pipeline, "GEMINI_API_KEY", "") or "").strip():
        raise SystemExit("GEMINI_API_KEY is required")

    gemini_provider_resilience.install(pipeline)

    retry_owner = getattr(pipeline, "GEMINI_RETRY_OWNER", None)
    sdk_attempts = getattr(pipeline, "GEMINI_SDK_RETRY_ATTEMPTS", None)
    if retry_owner != "factory" or sdk_attempts != 1:
        raise SystemExit(
            f"Run360 retry contract not active: owner={retry_owner!r}, sdk_attempts={sdk_attempts!r}"
        )

    prompt = "Reply with exactly RUN361_OK and nothing else."
    started = time.monotonic()
    status = "success"
    error_type = ""
    response_text = ""
    try:
        chat = pipeline.client.chats.create(
            model=model,
            config={"max_output_tokens": 16, "temperature": 0},
        )
        response = chat.send_message(prompt)
        response_text = str(getattr(response, "text", "") or "").strip()
        if response_text != "RUN361_OK":
            raise RuntimeError(f"unexpected response text: {response_text!r}")
    except Exception as exc:
        status = "error"
        error_type = type(exc).__name__
        elapsed = round(time.monotonic() - started, 3)
        print(json.dumps({
            "run": 361,
            "status": status,
            "model": model,
            "retry_owner": retry_owner,
            "sdk_attempts": sdk_attempts,
            "logical_calls": 1,
            "persist": False,
            "notion_write": False,
            "note_write": False,
            "elapsed_seconds": elapsed,
            "error_type": error_type,
            "error": str(exc)[:500],
        }, ensure_ascii=False))
        raise

    elapsed = round(time.monotonic() - started, 3)
    print(json.dumps({
        "run": 361,
        "status": status,
        "model": model,
        "retry_owner": retry_owner,
        "sdk_attempts": sdk_attempts,
        "logical_calls": 1,
        "persist": False,
        "notion_write": False,
        "note_write": False,
        "elapsed_seconds": elapsed,
        "response": response_text,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
