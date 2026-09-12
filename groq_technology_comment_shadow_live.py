"""One-call Groq live validator for Technology comment Shadow output.

This script has no Notion credentials or mutation code. It reads a public/synthetic
fixture, calls Groq once with strict JSON schema output, validates the challenger, and
writes a local report. The report may contain generated synthetic text; production DB
content is never used here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

from technology_comment_shadow import (
    SHADOW_SCHEMA,
    build_shadow_prompt,
    compare_shadow_to_baseline,
    parse_shadow_output,
)


API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"


def _post(payload: dict) -> tuple[dict, dict]:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required")
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ai-intelligence-factory-shadow-validation/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
            headers = {k.lower(): v for k, v in response.headers.items()}
            return body, headers
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"Groq HTTP {exc.code}: {detail}") from None


def run(fixture_path: str, report_path: str) -> dict:
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    if fixture.get("source") != "synthetic_public_validation":
        raise RuntimeError("live_shadow_requires_public_synthetic_fixture")
    prompt = build_shadow_prompt(fixture)
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": 1200,
        "reasoning_effort": "low",
        "reasoning_format": "hidden",
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "technology_comment_shadow",
                "strict": True,
                "schema": SHADOW_SCHEMA,
            },
        },
    }
    body, headers = _post(payload)
    try:
        choice = body["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise RuntimeError(f"Groq incomplete output: {choice.get('finish_reason')}")
        raw = choice["message"]["content"]
        usage = body.get("usage") or {}
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Groq malformed response") from None

    challenger = parse_shadow_output(raw)
    comparison = compare_shadow_to_baseline(fixture["baseline"], challenger, fixture)
    report = {
        "mode": "technology_comment_shadow_live",
        "candidate_id": fixture["candidate_id"],
        "provider": "groq",
        "model": MODEL,
        "challenger": challenger,
        "comparison": comparison,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        "rate_headers": {
            key: value for key, value in headers.items()
            if key.startswith("x-ratelimit-") or key == "retry-after"
        },
        "persist_allowed": False,
        "business_writes": 0,
        "automatic_promotion_allowed": False,
    }
    Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    fixture_path = os.environ.get(
        "AIIF_TECH_COMMENT_SHADOW_FIXTURE",
        "tests/fixtures/technology_comment_shadow_live.json",
    )
    report_path = os.environ.get("AIIF_TECH_COMMENT_SHADOW_REPORT", "technology-comment-shadow-live.json")
    report = run(fixture_path, report_path)
    comparison = report["comparison"]
    # Intentionally do not print generated prose. Keep logs aggregate-only.
    print(json.dumps({
        "mode": report["mode"],
        "candidate_id": report["candidate_id"],
        "provider": report["provider"],
        "model": report["model"],
        "challenger_scores": comparison["challenger_scores"],
        "baseline_scores": comparison["baseline_scores"],
        "margin": comparison["margin"],
        "deterministic_gate_passed": comparison["deterministic_gate_passed"],
        "automatic_promotion_allowed": False,
        "business_writes": 0,
        "usage": report["usage"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
