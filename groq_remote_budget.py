"""GitHub-backed atomic reservation and usage reconciliation for Groq experiments.

Reservations happen before send and are never deleted. After a successful provider
response, the same experiment row is atomically reconciled upward to Groq-reported
actual usage. Experiment IDs remain one-shot forever; reconciliation never creates a
second request record. GitHub ledger CAS conflicts may be retried; provider calls are not.
"""
import base64
import json
import time
import urllib.error
import urllib.request
from ai_provider import ProviderError
from groq_rate_policy import (
    GPT_OSS_120B,
    MAX_RESERVED_TOKENS_PER_REQUEST,
    ROLLING_DAY_SECONDS,
    ROLLING_MINUTE_SECONDS,
    policy_for_name,
)

REPOSITORY = "trendhub-ab/ai-intelligence-factory"
BRANCH = "runtime/groq-validation"
PATH = ".runtime/groq_validation_ledger.json"
CAS_RETRIES = 3
CAS_RETRY_SECONDS = 0.15


def _validate_state(state, now):
    if not isinstance(state, dict) or state.get("version") != 1 or not isinstance(state.get("attempts"), list):
        raise ProviderError("invalid_remote_ledger")
    for row in state["attempts"]:
        if not isinstance(row, dict) or not isinstance(row.get("experiment"), str):
            raise ProviderError("invalid_remote_ledger")
        if type(row.get("tokens")) is not int or not 1 <= row["tokens"] <= MAX_RESERVED_TOKENS_PER_REQUEST:
            raise ProviderError("invalid_remote_ledger")
        if type(row.get("stamp")) not in {int, float} or not 0 <= row["stamp"] <= now:
            raise ProviderError("invalid_remote_ledger")
        try:
            policy_for_name(str(row.get("profile") or GPT_OSS_120B.name))
        except ValueError:
            raise ProviderError("invalid_remote_ledger") from None


def reserve_state(state, experiment, tokens, now, profile: str = GPT_OSS_120B.name):
    try:
        policy = policy_for_name(profile)
    except ValueError:
        raise ProviderError("invalid_remote_reservation") from None
    _validate_state(state, now)
    if not isinstance(experiment, str) or not experiment or type(tokens) is not int or not 1 <= tokens <= policy.safe_tpm:
        raise ProviderError("invalid_remote_reservation")

    recent_day = []
    recent_minute = []
    for row in state["attempts"]:
        if row["experiment"] == experiment:
            raise ProviderError("experiment_already_reserved")
        row_profile = str(row.get("profile") or GPT_OSS_120B.name)
        if row_profile != profile:
            continue
        if row["stamp"] > now - ROLLING_DAY_SECONDS:
            recent_day.append(row)
        if row["stamp"] > now - ROLLING_MINUTE_SECONDS:
            recent_minute.append(row)

    if len(recent_day) >= policy.safe_rpd:
        raise ProviderError("persistent_validation_daily_budget_exceeded")
    if policy.safe_tpd is not None and sum(row["tokens"] for row in recent_day) + tokens > policy.safe_tpd:
        raise ProviderError("persistent_validation_daily_budget_exceeded")
    if len(recent_minute) >= policy.safe_rpm or sum(row["tokens"] for row in recent_minute) + tokens > policy.safe_tpm:
        raise ProviderError("persistent_validation_minute_budget_exceeded")

    return {"version": 1, "attempts": state["attempts"] + [
        {"experiment": experiment, "profile": profile, "stamp": now, "tokens": tokens}
    ]}


def reconcile_state(state, experiment, actual_tokens, now, profile: str = GPT_OSS_120B.name):
    """Replace one reservation with actual usage; never reduce consumed tokens."""
    try:
        policy = policy_for_name(profile)
    except ValueError:
        raise ProviderError("invalid_remote_reconciliation") from None
    _validate_state(state, now)
    if not isinstance(experiment, str) or not experiment or type(actual_tokens) is not int or actual_tokens <= 0:
        raise ProviderError("invalid_remote_reconciliation")

    matches = [i for i, row in enumerate(state["attempts"]) if row["experiment"] == experiment]
    if len(matches) != 1:
        raise ProviderError("reconciliation_experiment_not_unique")
    idx = matches[0]
    row = state["attempts"][idx]
    row_profile = str(row.get("profile") or GPT_OSS_120B.name)
    if row_profile != profile:
        raise ProviderError("reconciliation_profile_mismatch")
    reconciled = max(int(row["tokens"]), actual_tokens)
    if reconciled > policy.official_tpm:
        raise ProviderError("provider_usage_exceeds_official_tpm")

    attempts = [dict(item) for item in state["attempts"]]
    attempts[idx]["tokens"] = reconciled
    attempts[idx]["actual_tokens"] = actual_tokens
    attempts[idx]["reconciled"] = True
    return {"version": 1, "attempts": attempts}


def _read_remote(token, opener):
    endpoint = f"https://api.github.com/repos/{REPOSITORY}/contents/{PATH}"
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "User-Agent": "AI-Intelligence-Factory/1.0", "Content-Type": "application/json"}
    req = urllib.request.Request(endpoint + "?ref=" + BRANCH, headers=headers)
    with opener.open(req, timeout=30) as response:
        file = json.load(response)
    state = json.loads(base64.b64decode(file["content"]))
    return endpoint, headers, file, state


def _write_remote(endpoint, headers, file, state, message, opener):
    data = {"message": message, "branch": BRANCH, "sha": file["sha"],
            "content": base64.b64encode(json.dumps(state).encode()).decode()}
    req = urllib.request.Request(endpoint, headers=headers, data=json.dumps(data).encode(), method="PUT")
    with opener.open(req, timeout=30) as response:
        if response.status != 200:
            raise ProviderError("remote_reservation_failed")


def _cas_mutate(token, opener, mutate, message):
    """Retry only stale-SHA/CAS conflicts. Never retries a Groq provider request."""
    last_conflict = None
    for attempt in range(CAS_RETRIES):
        endpoint, headers, file, state = _read_remote(token, opener)
        updated = mutate(state)
        try:
            _write_remote(endpoint, headers, file, updated, message, opener)
            return
        except urllib.error.HTTPError as exc:
            if exc.code not in {409, 422}:
                raise
            last_conflict = exc
            if attempt + 1 < CAS_RETRIES:
                time.sleep(CAS_RETRY_SECONDS * (attempt + 1))
    raise ProviderError("remote_ledger_cas_conflict", getattr(last_conflict, "code", None)) from None


def reserve_remote(token, experiment, tokens, opener, profile: str = GPT_OSS_120B.name):
    _cas_mutate(
        token,
        opener,
        lambda state: reserve_state(state, experiment, tokens, time.time(), profile),
        "Reserve bounded Groq experiment before provider call",
    )


def reconcile_remote(token, experiment, actual_tokens, opener, profile: str = GPT_OSS_120B.name):
    _cas_mutate(
        token,
        opener,
        lambda state: reconcile_state(state, experiment, actual_tokens, time.time(), profile),
        "Reconcile Groq reservation to provider-reported usage",
    )
