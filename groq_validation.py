"""Single saved-prompt validation through production_pipeline.py; no business writes.

Default is offline. Live mode requires a key and explicit live flag. Model selection is
fixture-declared and restricted to the Factory's approved Groq Free Plan policies.
Local and GitHub ledgers enforce the matching model-specific safety envelope.
"""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import urllib.error
import urllib.request

from ai_provider import GenerationRequest, GroqProvider, ProviderError
from groq_rate_policy import (
    GPT_OSS_120B,
    MAX_RESERVED_TOKENS_PER_REQUEST,
    ROLLING_DAY_SECONDS,
    ROLLING_MINUTE_SECONDS,
    policy_for_model,
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


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
        db.execute("CREATE TABLE IF NOT EXISTS attempts (stamp REAL NOT NULL, tokens INTEGER NOT NULL, profile TEXT NOT NULL DEFAULT 'gpt_oss_120b')")
        columns = {row[1] for row in db.execute("PRAGMA table_info(attempts)")}
        if "profile" not in columns:
            db.execute("ALTER TABLE attempts ADD COLUMN profile TEXT NOT NULL DEFAULT 'gpt_oss_120b'")
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
    provider = GroqProvider(
        lambda _: None,
        validate_schema=validator,
        token_budget=policy.safe_tpm,
        model=model,
    )
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
                return exc.code, dict(exc.headers), {}
        provider.transport = transport
        try:
            result = provider.generate(request)
        except ProviderError as exc:
            report.update(
                live=True,
                provider_calls=provider.attempts,
                error={"kind": exc.kind, "status": exc.status, "retry_after": exc.retry_after},
            )
            _write_report(output, report)
            print(json.dumps({k: v for k, v in report.items() if k != "result"}, ensure_ascii=False))
            raise
        report.update(live=True, provider_calls=provider.attempts, result=asdict(result))
    _write_report(output, report)
    print(json.dumps({k: v for k, v in report.items() if k != "result"}, ensure_ascii=False))
    return report
