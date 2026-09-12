"""Single saved-prompt validation through production_pipeline.py; no business writes.

Default is offline. Live mode requires a key and explicit live flag. Model selection is
fixture-declared and restricted to the Factory's approved Groq Free Plan policies.
Pre-send reservations are reconciled to provider-reported usage after every successful
response so tokenizer approximation never discards valid output or understates usage.
"""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import urllib.error
import urllib.request

from ai_provider import GenerationRequest, GroqProvider, ProviderError
from groq_rate_policy import (
    GPT_OSS_120B,
    ROLLING_DAY_SECONDS,
    ROLLING_MINUTE_SECONDS,
    policy_for_model,
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _ensure_local_schema(db):
    db.execute("CREATE TABLE IF NOT EXISTS attempts (stamp REAL NOT NULL, tokens INTEGER NOT NULL, profile TEXT NOT NULL DEFAULT 'gpt_oss_120b')")
    columns = {row[1] for row in db.execute("PRAGMA table_info(attempts)")}
    if "profile" not in columns:
        db.execute("ALTER TABLE attempts ADD COLUMN profile TEXT NOT NULL DEFAULT 'gpt_oss_120b'")


def reserve_attempt(path: str, tokens: int, now: float | None = None,
                    profile: str = GPT_OSS_120B.name) -> None:
    """Atomic reserve before send; failures/timeouts stay counted. Never auto-delete."""
    now = time.time() if now is None else now
    from groq_rate_policy import policy_for_name
    try:
        policy = policy_for_name(profile)
    except ValueError:
        raise ProviderError("invalid_token_reservation") from None
    if type(tokens) is not int or not 1 <= tokens <= policy.safe_tpm:
        raise ProviderError("invalid_token_reservation")
    with sqlite3.connect(path, timeout=10) as db:
        _ensure_local_schema(db)
        db.execute("BEGIN IMMEDIATE")
        day_count, day_tokens = db.execute(
            "SELECT COUNT(*), COALESCE(SUM(tokens),0) FROM attempts WHERE profile = ? AND stamp > ?",
            (profile, now - ROLLING_DAY_SECONDS),
        ).fetchone()
        minute_count, minute_tokens = db.execute(
            "SELECT COUNT(*), COALESCE(SUM(tokens),0) FROM attempts WHERE profile = ? AND stamp > ?",
            (profile, now - ROLLING_MINUTE_SECONDS),
        ).fetchone()
        if day_count >= policy.safe_rpd:
            raise ProviderError("persistent_validation_daily_budget_exceeded")
        if policy.safe_tpd is not None and day_tokens + tokens > policy.safe_tpd:
            raise ProviderError("persistent_validation_daily_budget_exceeded")
        if minute_count >= policy.safe_rpm or minute_tokens + tokens > policy.safe_tpm:
            raise ProviderError("persistent_validation_minute_budget_exceeded")
        db.execute("INSERT INTO attempts (stamp, tokens, profile) VALUES (?, ?, ?)", (now, tokens, profile))


def reconcile_attempt(path: str, actual_tokens: int, profile: str = GPT_OSS_120B.name) -> None:
    """Reconcile the latest serialized local reservation upward to actual usage."""
    from groq_rate_policy import policy_for_name
    try:
        policy = policy_for_name(profile)
    except ValueError:
        raise ProviderError("invalid_token_reconciliation") from None
    if type(actual_tokens) is not int or not 1 <= actual_tokens <= policy.official_tpm:
        raise ProviderError("invalid_token_reconciliation")
    with sqlite3.connect(path, timeout=10) as db:
        _ensure_local_schema(db)
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT rowid, tokens FROM attempts WHERE profile = ? ORDER BY rowid DESC LIMIT 1",
            (profile,),
        ).fetchone()
        if not row:
            raise ProviderError("local_reconciliation_reservation_missing")
        rowid, reserved = row
        db.execute("UPDATE attempts SET tokens = ? WHERE rowid = ?", (max(int(reserved), actual_tokens), rowid))


def schema_validator(schema: dict | None):
    if schema is None:
        return None
    from jsonschema import Draft202012Validator
    Draft202012Validator.check_schema(schema)
    def reject_remote_refs(value):
        if isinstance(value, dict):
            if "$ref" in value and not str(value["$ref"]).startswith("#"):
                raise ProviderError("external_schema_ref_forbidden")
            for child in value.values():
                reject_remote_refs(child)
        elif isinstance(value, list):
            for child in value:
                reject_remote_refs(child)
    reject_remote_refs(schema)
    validator = Draft202012Validator(schema)
    return lambda data, _: validator.validate(data)


def _sanitize_provider_error_message(message: object) -> str:
    """Return a tiny diagnostic string without prompts, generations, URLs or credentials."""
    value = str(message or "")
    if not value:
        return ""
    value = re.sub(r"https?://\S+", "[URL]", value, flags=re.IGNORECASE)
    value = re.sub(r"(?i)\b(?:bearer|authorization|api[_ -]?key|token)\b\s*[:=]?\s*\S+", "[REDACTED]", value)
    value = re.sub(r"(?i)gsk_[A-Za-z0-9_-]+", "[REDACTED]", value)
    value = re.sub(r"[\r\n\t]+", " ", value)
    value = re.sub(r"\s{2,}", " ", value).strip()
    return value[:300]


def _safe_http_error_diagnostic(payload: object) -> dict[str, object]:
    """Whitelist only low-risk Groq error metadata; ignore failed_generation and extras."""
    if not isinstance(payload, dict):
        return {}
    error = payload.get("error")
    if not isinstance(error, dict):
        return {}
    diagnostic: dict[str, object] = {}
    for key in ("type", "code", "param"):
        value = error.get(key)
        if isinstance(value, (str, int, float, bool)) and str(value):
            diagnostic[key] = value
    message = _sanitize_provider_error_message(error.get("message"))
    if message:
        diagnostic["message"] = message
    return diagnostic


def _write_report(path: str, report: dict) -> None:
    if path:
        Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


def run_saved_prompt_validation() -> dict:
    fixture_path = os.environ.get("AIIF_GROQ_FIXTURE", "")
    if not fixture_path:
        raise ProviderError("saved_prompt_fixture_required")
    raw = Path(fixture_path).read_bytes()
    fixture = json.loads(raw)
    if fixture.get("stage") not in {"screening", "calibration", "article", "quality_gate", "product_review"}:
        raise ProviderError("invalid_fixture_stage")
    model = str(fixture.get("model") or GPT_OSS_120B.model)
    try:
        policy = policy_for_model(model)
    except ValueError:
        raise ProviderError("unsupported_model") from None
    declared_policy = str(fixture.get("rate_policy") or policy.name)
    if declared_policy != policy.name:
        raise ProviderError("rate_policy_model_mismatch")
    request = GenerationRequest(fixture["prompt"], fixture["max_output_tokens"],
                                fixture.get("schema"), fixture.get("reasoning_effort", "low"))
    validator = schema_validator(request.schema)
    provider = GroqProvider(lambda _: None, validate_schema=validator,
                            token_budget=policy.safe_tpm, model=model)
    _, estimate = provider.prepare(request)
    report = {"mode": "groq_saved_prompt_validation", "provider": "groq", "model": provider.model,
              "rate_policy": policy.name, "stage": fixture["stage"],
              "fixture_sha256": hashlib.sha256(raw).hexdigest(),
              "reserved_token_estimate": estimate, "live": False, "provider_calls": 0,
              "business_writes": 0, "quality_validated": False,
              "safety_budget": {"rpm": policy.safe_rpm, "rpd": policy.safe_rpd,
                                "tpm": policy.safe_tpm, "tpd": policy.safe_tpd}}
    output = os.environ.get("AIIF_GROQ_REPORT", "").strip()
    if output and Path(output).resolve() == Path(fixture_path).resolve():
        raise ProviderError("report_must_not_overwrite_fixture")
    live = os.environ.get("AIIF_GROQ_LIVE", "false").lower()
    if live not in {"false", "true"}:
        raise ProviderError("invalid_live_flag")
    diagnostic_enabled = os.environ.get("AIIF_GROQ_ERROR_DIAGNOSTIC", "false").lower() == "true"
    last_http_error_diagnostic: dict[str, object] = {}
    if live == "true":
        key = os.environ.get("GROQ_API_KEY", "").strip()
        ledger = os.environ.get("AIIF_GROQ_LEDGER", "").strip()
        backend = os.environ.get("AIIF_GROQ_BUDGET_BACKEND", "sqlite")
        if backend not in {"sqlite", "github"}:
            raise ProviderError("invalid_budget_backend")
        github_token = os.environ.get("GROQ_LEDGER_GITHUB_TOKEN", "")
        experiment = os.environ.get("AIIF_GROQ_EXPERIMENT", "")
        if not key or (backend == "sqlite" and not ledger) or (backend == "github" and (not github_token or not experiment)):
            raise ProviderError("groq_key_and_persistent_ledger_required")
        opener = urllib.request.build_opener(NoRedirect())
        def transport(payload):
            nonlocal last_http_error_diagnostic
            if backend == "github":
                from groq_remote_budget import reserve_remote
                reserve_remote(github_token, experiment, estimate, opener, policy.name)
            else:
                reserve_attempt(ledger, estimate, profile=policy.name)
            req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                         "User-Agent": "AI-Intelligence-Factory/1.0", "Accept": "application/json"}, method="POST")
            try:
                with opener.open(req, timeout=60) as response:
                    return response.status, dict(response.headers), json.load(response)
            except urllib.error.HTTPError as exc:
                body: object = {}
                if diagnostic_enabled:
                    try:
                        raw_error = exc.read(32768)
                        body = json.loads(raw_error.decode("utf-8", errors="replace"))
                        last_http_error_diagnostic = _safe_http_error_diagnostic(body)
                    except Exception:
                        last_http_error_diagnostic = {}
                return exc.code, dict(exc.headers), {}
        provider.transport = transport
        try:
            result = provider.generate(request)
            actual_tokens = result.prompt_tokens + result.completion_tokens
            if backend == "github":
                from groq_remote_budget import reconcile_remote
                reconcile_remote(github_token, experiment, actual_tokens, opener, policy.name)
            else:
                reconcile_attempt(ledger, actual_tokens, profile=policy.name)
        except ProviderError as exc:
            error = {"kind": exc.kind, "status": exc.status, "retry_after": exc.retry_after}
            if diagnostic_enabled and last_http_error_diagnostic:
                error["provider_diagnostic"] = last_http_error_diagnostic
            report.update(live=True, provider_calls=provider.attempts, error=error)
            _write_report(output, report)
            print(json.dumps({k: v for k, v in report.items() if k != "result"}, ensure_ascii=False))
            raise
        report.update(
            live=True,
            provider_calls=provider.attempts,
            actual_tokens=actual_tokens,
            estimate_delta_tokens=actual_tokens - estimate,
            ledger_reconciled=True,
            result=asdict(result),
        )
    _write_report(output, report)
    print(json.dumps({k: v for k, v in report.items() if k != "result"}, ensure_ascii=False))
    return report
