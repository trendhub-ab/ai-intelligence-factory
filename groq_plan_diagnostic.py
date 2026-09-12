"""One-call Groq Plan diagnostic with no business writes and no raw failed-generation persistence.

The provider's failed_generation is parsed only in runner memory, reduced to structural
reason codes, and discarded. Raw model output, prompts, credentials and HTTP bodies are
never written to the diagnostic report. Supports both strict-schema and the Hybrid Plan
JSON Object transport so provider failures can be compared safely.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from ai_provider import GenerationRequest, GroqProvider, ProviderError
from groq_rate_policy import policy_for_model
from groq_remote_budget import reconcile_remote, reserve_remote
from groq_validation import NoRedirect, _safe_http_error_diagnostic, schema_validator


def _json_type(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "other"


def _path_text(parts) -> str:
    out = "$"
    for part in parts:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += "." + str(part)
    return out


def failed_generation_schema_diagnostic(failed_generation, validation_schema: dict) -> dict:
    """Summarize schema failures without retaining generated values or raw text."""
    result = {
        "present": failed_generation is not None,
        "json_parseable": False,
        "top_level_type": _json_type(failed_generation),
    }
    if failed_generation is None:
        return result
    candidate = failed_generation
    if isinstance(candidate, str):
        result["raw_char_count"] = len(candidate)
        try:
            candidate = json.loads(candidate)
        except Exception as exc:
            result["json_parse_error"] = type(exc).__name__
            return result
    if not isinstance(candidate, (dict, list)):
        return result

    result["json_parseable"] = True
    result["top_level_type"] = _json_type(candidate)
    from jsonschema import Draft202012Validator
    validator = Draft202012Validator(validation_schema)
    errors = sorted(validator.iter_errors(candidate), key=lambda e: (list(e.path), list(e.schema_path)))
    result["schema_error_count"] = len(errors)
    issues = []
    for error in errors[:12]:
        issue = {"path": _path_text(error.path), "validator": str(error.validator)}
        if error.validator == "required" and isinstance(error.instance, dict):
            required = list(error.validator_value or [])
            issue["missing_required"] = [name for name in required if name not in error.instance]
        elif error.validator == "additionalProperties" and isinstance(error.instance, dict):
            allowed = set((error.schema or {}).get("properties", {}))
            issue["extra_property_count"] = len(set(error.instance) - allowed)
        elif error.validator == "type":
            issue["expected_type"] = error.validator_value
            issue["actual_type"] = _json_type(error.instance)
        elif error.validator == "enum":
            issue["allowed_enum"] = list(error.validator_value or [])
        elif error.validator in {"minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems"}:
            issue["constraint"] = error.validator_value
        issues.append(issue)
    result["issues"] = issues
    return result


def run_probe(fixture_path: str, output_path: str) -> dict:
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    model = str(fixture["model"])
    policy = policy_for_model(model)
    mode = str(fixture.get("structured_output_mode") or "strict_schema")
    request = GenerationRequest(
        fixture["prompt"], fixture["max_output_tokens"], fixture.get("schema"),
        fixture.get("reasoning_effort", "low"), mode,
    )
    validate = schema_validator(request.schema)
    provider = GroqProvider(lambda _: None, validate_schema=validate, token_budget=policy.safe_tpm, model=model)
    payload, estimate = provider.prepare(request)
    validation_schema = request.schema
    if not isinstance(validation_schema, dict):
        raise ProviderError("schema_validator_required")

    key = os.environ.get("GROQ_API_KEY", "").strip()
    token = os.environ.get("GROQ_LEDGER_GITHUB_TOKEN", "").strip()
    experiment = os.environ.get("AIIF_GROQ_EXPERIMENT", "").strip()
    if not key or not token or not experiment:
        raise ProviderError("groq_key_and_persistent_ledger_required")
    opener = urllib.request.build_opener(NoRedirect())
    reserve_remote(token, experiment, estimate, opener, policy.name)
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "User-Agent": "AI-Intelligence-Factory/1.0",
            "Accept": "application/json",
        },
        method="POST",
    )
    report = {
        "mode": "groq_plan_transport_diagnostic",
        "structured_output_mode": mode,
        "response_format_type": payload.get("response_format", {}).get("type"),
        "reasoning_format": payload.get("reasoning_format"),
        "model": model,
        "reserved_token_estimate": estimate,
        "provider_calls": 1,
        "business_writes": 0,
        "gemini_calls": 0,
        "raw_failed_generation_persisted": False,
    }
    try:
        with opener.open(req, timeout=60) as response:
            body = json.load(response)
        choice = body["choices"][0]
        content = choice["message"]["content"]
        parsed = json.loads(content)
        validate(parsed, request.schema)
        usage = body["usage"]
        actual = int(usage["prompt_tokens"]) + int(usage["completion_tokens"])
        reconcile_remote(token, experiment, actual, opener, policy.name)
        report.update(status="SUCCESS", actual_tokens=actual, ledger_reconciled=True)
    except urllib.error.HTTPError as exc:
        try:
            raw_body = exc.read(131072)
            body = json.loads(raw_body.decode("utf-8", errors="replace"))
        except Exception:
            body = {}
        error = body.get("error") if isinstance(body, dict) else None
        failed = error.get("failed_generation") if isinstance(error, dict) else None
        report.update(
            status="HTTP_ERROR",
            http_status=exc.code,
            provider_diagnostic=_safe_http_error_diagnostic(body),
            generation_schema_diagnostic=failed_generation_schema_diagnostic(failed, validation_schema),
        )
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    for forbidden in ("\"failed_generation\"", "GROQ_API_KEY", "Authorization: Bearer", "gsk_"):
        if forbidden in serialized:
            raise RuntimeError("diagnostic_secret_surface_detected")
    Path(output_path).write_text(serialized, encoding="utf-8")
    return report
