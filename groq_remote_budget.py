"""GitHub-backed atomic reservation for serialized, bounded Groq experiments.

The pre-existing ledger is never initialized, deleted, or reset by this code.
GitHub's file SHA is the compare-and-swap token. A conflict aborts before Groq.
An experiment ID may be sent once, even after the rolling window expires.

The local envelope intentionally stays below Groq's published Free Plan limits for
openai/gpt-oss-120b. It protects both rolling minute and rolling 24-hour request/token
usage without imposing the old artificial 3-request development ceiling.
"""
import base64
import json
import time
import urllib.request
from ai_provider import ProviderError
from groq_rate_policy import (
    MAX_RESERVED_TOKENS_PER_REQUEST,
    ROLLING_DAY_SECONDS,
    ROLLING_MINUTE_SECONDS,
    SAFE_RPD,
    SAFE_RPM,
    SAFE_TPD,
    SAFE_TPM,
)

REPOSITORY = "trendhub-ab/ai-intelligence-factory"
BRANCH = "runtime/groq-validation"
PATH = ".runtime/groq_validation_ledger.json"


def reserve_state(state, experiment, tokens, now):
    if not isinstance(state, dict) or state.get("version") != 1 or not isinstance(state.get("attempts"), list):
        raise ProviderError("invalid_remote_ledger")
    if (
        not isinstance(experiment, str)
        or not experiment
        or type(tokens) is not int
        or not 1 <= tokens <= MAX_RESERVED_TOKENS_PER_REQUEST
    ):
        raise ProviderError("invalid_remote_reservation")

    recent_day = []
    recent_minute = []
    for row in state["attempts"]:
        if not isinstance(row, dict) or not isinstance(row.get("experiment"), str):
            raise ProviderError("invalid_remote_ledger")
        if type(row.get("tokens")) is not int or not 1 <= row["tokens"] <= MAX_RESERVED_TOKENS_PER_REQUEST:
            raise ProviderError("invalid_remote_ledger")
        if type(row.get("stamp")) not in {int, float} or not 0 <= row["stamp"] <= now:
            raise ProviderError("invalid_remote_ledger")
        if row["experiment"] == experiment:
            raise ProviderError("experiment_already_reserved")
        if row["stamp"] > now - ROLLING_DAY_SECONDS:
            recent_day.append(row)
        if row["stamp"] > now - ROLLING_MINUTE_SECONDS:
            recent_minute.append(row)

    if len(recent_day) >= SAFE_RPD or sum(row["tokens"] for row in recent_day) + tokens > SAFE_TPD:
        raise ProviderError("persistent_validation_daily_budget_exceeded")
    if len(recent_minute) >= SAFE_RPM or sum(row["tokens"] for row in recent_minute) + tokens > SAFE_TPM:
        raise ProviderError("persistent_validation_minute_budget_exceeded")

    return {
        "version": 1,
        "attempts": state["attempts"] + [
            {"experiment": experiment, "stamp": now, "tokens": tokens}
        ],
    }


def reserve_remote(token, experiment, tokens, opener):
    endpoint = f"https://api.github.com/repos/{REPOSITORY}/contents/{PATH}"
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "User-Agent": "AI-Intelligence-Factory/1.0", "Content-Type": "application/json"}
    req = urllib.request.Request(endpoint + "?ref=" + BRANCH, headers=headers)
    with opener.open(req, timeout=30) as response:
        file = json.load(response)
    state = json.loads(base64.b64decode(file["content"]))
    updated = reserve_state(state, experiment, tokens, time.time())
    data = {"message": "Reserve bounded Groq experiment before provider call", "branch": BRANCH,
            "sha": file["sha"], "content": base64.b64encode(json.dumps(updated).encode()).decode()}
    req = urllib.request.Request(endpoint, headers=headers, data=json.dumps(data).encode(), method="PUT")
    with opener.open(req, timeout=30) as response:
        if response.status != 200:
            raise ProviderError("remote_reservation_failed")
