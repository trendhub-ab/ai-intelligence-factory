"""Single saved-prompt validation through production_pipeline.py; no business writes.

Default is offline. Live mode requires a key and explicit live flag. Its SQLite
ledger is a conservative rolling 24h validation cap (3 requests / 24000 reserved
tokens), not a claim to know an organization's remaining Free Plan allowance.
Keep the ledger on durable shared storage and serialize all validation runs.
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


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def reserve_attempt(path: str, tokens: int, now: float | None = None) -> None:
    """Atomic reserve before send; failures/timeouts stay counted. Never auto-delete."""
    now = time.time() if now is None else now
    if type(tokens) is not int or not 1 <= tokens <= 8000:
        raise ProviderError("invalid_token_reservation")
    with sqlite3.connect(path, timeout=10) as db:
        db.execute("CREATE TABLE IF NOT EXISTS attempts (stamp REAL NOT NULL, tokens INTEGER NOT NULL)")
        db.execute("BEGIN IMMEDIATE")
        count, total, last = db.execute(
            "SELECT COUNT(*), COALESCE(SUM(tokens),0), MAX(stamp) FROM attempts WHERE stamp > ?",
            (now - 86400,)).fetchone()
        if count >= 3 or total + tokens > 24000:
            raise ProviderError("persistent_validation_budget_exceeded")
        if last is not None and now - last < 65:
            raise ProviderError("validation_pacing_required")
        db.execute("INSERT INTO attempts VALUES (?, ?)", (now, tokens))


def schema_validator(schema: dict | None):
    if schema is None:
        return None
    # Dedicated validation dependency. Not imported by the existing Gemini path.
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


def run_saved_prompt_validation() -> dict:
    fixture_path = os.environ.get("AIIF_GROQ_FIXTURE", "")
    if not fixture_path:
        raise ProviderError("saved_prompt_fixture_required")
    raw = Path(fixture_path).read_bytes()
    fixture = json.loads(raw)
    if fixture.get("stage") not in {"screening", "calibration", "article", "quality_gate", "product_review"}:
        raise ProviderError("invalid_fixture_stage")
    request = GenerationRequest(fixture["prompt"], fixture["max_output_tokens"],
                                fixture.get("schema"), fixture.get("reasoning_effort", "low"))
    validator = schema_validator(request.schema)
    provider = GroqProvider(lambda _: None, validate_schema=validator)
    _, estimate = provider.prepare(request)
    report = {"mode": "groq_saved_prompt_validation", "provider": "groq", "model": provider.model,
              "stage": fixture["stage"], "fixture_sha256": hashlib.sha256(raw).hexdigest(),
              "reserved_token_estimate": estimate, "live": False, "provider_calls": 0,
              "business_writes": 0, "quality_validated": False}
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
                reserve_remote(github_token, experiment, estimate, opener)
            else:
                reserve_attempt(ledger, estimate)
            req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                         "User-Agent": "AI-Intelligence-Factory/1.0", "Accept": "application/json"}, method="POST")
            try:
                with opener.open(req, timeout=60) as response:
                    return response.status, dict(response.headers), json.load(response)
            except urllib.error.HTTPError as exc:
                return exc.code, dict(exc.headers), {}  # Never echo provider error body.
        provider.transport = transport
        result = provider.generate(request)
        report.update(live=True, provider_calls=provider.attempts, result=asdict(result))
    if output:
        Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    # Generated content stays in the explicitly selected report, not CI console.
    print(json.dumps({k: v for k, v in report.items() if k != "result"}, ensure_ascii=False))
    return report
